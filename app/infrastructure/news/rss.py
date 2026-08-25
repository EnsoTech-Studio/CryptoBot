"""Bounded RSS/Atom adapter with pinned-address HTTPS transport."""

from __future__ import annotations

import email.utils
import http.client
import socket
import ssl
from collections.abc import Callable
from datetime import UTC, datetime
from urllib.parse import urljoin, urlsplit

from defusedxml import ElementTree

from ...domain.news import ApprovedSource, CollectedItem
from .security import (
    Resolver,
    _default_resolver,
    assert_public_https,
    canonical_url,
    related_coins,
    sanitize_text,
    sha256_text,
)

MAX_RESPONSE_BYTES = 2 << 20
MAX_ITEMS = 200
MAX_REDIRECTS = 3
_ALLOWED_CONTENT_TYPES = {
    "application/atom+xml",
    "application/json",
    "application/rss+xml",
    "application/xml",
    "text/html",
    "text/xml",
}


class NewsProviderError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


Fetcher = Callable[[str, str, tuple[str, ...]], tuple[int, dict[str, str], bytes]]


def _pinned_https_get(url: str, host: str, addresses: tuple[str, ...]) -> tuple[int, dict[str, str], bytes]:
    parsed = urlsplit(url)
    last_error: OSError | None = None
    for address in addresses:
        raw_socket: socket.socket | None = None
        tls_socket: ssl.SSLSocket | None = None
        try:
            raw_socket = socket.create_connection((address, 443), timeout=3)
            tls_socket = ssl.create_default_context().wrap_socket(raw_socket, server_hostname=host)
            tls_socket.settimeout(10)
            path = parsed.path or "/"
            if parsed.query:
                path += "?" + parsed.query
            request = (
                f"GET {path} HTTP/1.1\r\nHost: {host}\r\n"
                "User-Agent: CryptoBot-Research/1.0\r\nAccept: application/rss+xml, "
                "application/atom+xml, application/xml, text/xml, text/html\r\n"
                "Accept-Encoding: identity\r\nConnection: close\r\n\r\n"
            )
            tls_socket.sendall(request.encode("ascii"))
            response = http.client.HTTPResponse(tls_socket)
            response.begin()
            headers = {key.lower(): value for key, value in response.getheaders()}
            body = bytearray()
            while chunk := response.read(min(65_536, MAX_RESPONSE_BYTES + 1 - len(body))):
                body.extend(chunk)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise NewsProviderError("response_too_large", "news response exceeded 2 MiB")
            return response.status, headers, bytes(body)
        except NewsProviderError:
            raise
        except OSError as exc:
            last_error = exc
        finally:
            if tls_socket is not None:
                tls_socket.close()
            elif raw_socket is not None:
                raw_socket.close()
    raise NewsProviderError("upstream_unavailable", "approved news source is unavailable") from last_error


class RssNewsProvider:
    def __init__(
        self,
        *,
        resolver: Resolver = _default_resolver,
        fetcher: Fetcher = _pinned_https_get,
    ) -> None:
        self._resolver = resolver
        self._fetcher = fetcher

    def collect(self, source: ApprovedSource, since: datetime | None) -> list[CollectedItem]:
        if not source.is_active or source.kind != "rss":
            raise NewsProviderError("unsupported_source", "source is not an active RSS feed")
        current = source.url_template
        for redirect in range(MAX_REDIRECTS + 1):
            host, addresses = assert_public_https(current, source.allowed_origin, self._resolver)
            status, headers, payload = self._fetcher(current, host, addresses)
            if status in {301, 302, 303, 307, 308}:
                if redirect == MAX_REDIRECTS:
                    raise NewsProviderError("too_many_redirects", "news source redirected too often")
                location = headers.get("location", "")
                if not location:
                    raise NewsProviderError("invalid_redirect", "news redirect has no location")
                current = urljoin(current, location)
                continue
            if status >= 500:
                raise NewsProviderError("upstream_5xx", "news source returned a server error")
            if status < 200 or status >= 300:
                raise NewsProviderError("upstream_status", f"news source returned HTTP {status}")
            content_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if content_type not in _ALLOWED_CONTENT_TYPES:
                raise NewsProviderError("invalid_content_type", "news source returned unsupported content")
            return self._parse(source, payload, since)
        raise AssertionError("redirect loop must return or raise")

    def _parse(
        self, source: ApprovedSource, payload: bytes, since: datetime | None
    ) -> list[CollectedItem]:
        try:
            root = ElementTree.fromstring(payload)
        except ElementTree.ParseError as exc:
            raise NewsProviderError("parse_error", "news feed is not valid XML") from exc

        elements = list(root.findall(".//item"))
        if not elements:
            elements = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1] == "entry"]
        result: list[CollectedItem] = []
        for element in elements[:MAX_ITEMS]:
            item = self._parse_item(source, element)
            if item is not None and (since is None or item.published_at > since):
                result.append(item)
        return result

    def _parse_item(self, source: ApprovedSource, element: ElementTree.Element) -> CollectedItem | None:
        values: dict[str, str] = {}
        link = ""
        for child in element:
            tag = child.tag.rsplit("}", 1)[-1].lower()
            if tag == "link":
                link = (child.attrib.get("href") or child.text or "").strip()
            elif tag in {"title", "description", "summary", "content", "pubdate", "published", "updated"}:
                values[tag] = "".join(child.itertext()).strip()
        title = sanitize_text(values.get("title"), 512)
        content = sanitize_text(
            values.get("content") or values.get("description") or values.get("summary"),
            20_000,
        )
        if not title or not link:
            return None
        try:
            normalized_url = canonical_url(urljoin(source.url_template, link))
            if urlsplit(normalized_url).hostname != urlsplit(source.allowed_origin).hostname:
                return None
        except ValueError:
            return None
        published = _parse_date(
            values.get("pubdate") or values.get("published") or values.get("updated") or ""
        )
        return CollectedItem(
            source_id=source.id,
            canonical_url=normalized_url,
            url_hash=sha256_text(normalized_url),
            title=title,
            content=content,
            content_hash=sha256_text(f"{title}\n{content}"),
            published_at=published,
            related_coins=related_coins(title, content),
        )


def _parse_date(value: str) -> datetime:
    try:
        parsed = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        parsed = None
    if parsed is None:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            parsed = datetime.now(tz=UTC)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
