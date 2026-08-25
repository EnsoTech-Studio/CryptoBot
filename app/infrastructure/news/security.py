"""News egress and content-normalization guards."""

from __future__ import annotations

import hashlib
import html
import ipaddress
import re
import socket
import unicodedata
from collections.abc import Callable, Iterable
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

Resolver = Callable[[str, int], Iterable[str]]
_TRACKING_PARAMETERS = {"fbclid", "gclid", "ref"}
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WHITESPACE = re.compile(r"\s+")


class SsrfBlocked(ValueError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"news URL blocked: {reason}")


def _default_resolver(host: str, port: int) -> Iterable[str]:
    return {record[4][0] for record in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}


def normalized_origin(raw_url: str) -> str:
    parsed = urlsplit(raw_url)
    if parsed.scheme.lower() != "https":
        raise SsrfBlocked("https_required")
    if parsed.username or parsed.password:
        raise SsrfBlocked("userinfo_forbidden")
    if parsed.port not in (None, 443):
        raise SsrfBlocked("port_forbidden")
    hostname = (parsed.hostname or "").rstrip(".").lower()
    if not hostname:
        raise SsrfBlocked("missing_host")
    return f"https://{hostname}"


def assert_public_https(
    raw_url: str,
    allowed_origin: str,
    resolver: Resolver = _default_resolver,
) -> tuple[str, tuple[str, ...]]:
    origin = normalized_origin(raw_url)
    expected = normalized_origin(allowed_origin)
    if origin != expected:
        raise SsrfBlocked("origin_mismatch")
    host = urlsplit(origin).hostname
    assert host is not None
    try:
        addresses = tuple(sorted(set(resolver(host, 443))))
    except OSError as exc:
        raise SsrfBlocked("dns_failure") from exc
    if not addresses:
        raise SsrfBlocked("dns_empty")
    for raw_address in addresses:
        try:
            address = ipaddress.ip_address(raw_address)
        except ValueError as exc:
            raise SsrfBlocked("invalid_ip") from exc
        if not address.is_global:
            raise SsrfBlocked("non_public_ip")
    return host, addresses


def canonical_url(raw_url: str) -> str:
    parsed = urlsplit(raw_url.strip())
    normalized_origin(raw_url)
    hostname = (parsed.hostname or "").rstrip(".").lower()
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in _TRACKING_PARAMETERS
    ]
    query.sort()
    return urlunsplit(("https", hostname, path, urlencode(query, doseq=True), ""))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self.parts.append(data)

    def handle_entityref(self, name: str) -> None:
        if not self._ignored_depth:
            self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if not self._ignored_depth:
            self.parts.append(f"&#{name};")


def sanitize_text(value: str | None, limit: int) -> str:
    parser = _TextExtractor()
    parser.feed(value or "")
    parser.close()
    text = html.unescape(" ".join(parser.parts))
    text = unicodedata.normalize("NFC", text)
    text = _CONTROL.sub("", text)
    return _WHITESPACE.sub(" ", text).strip()[:limit]


def related_coins(title: str, content: str) -> tuple[str, ...]:
    aliases = {
        "BTC": ("bitcoin", "btc", "xbt"),
        "ETH": ("ethereum", "eth", "ether"),
        "SOL": ("solana", "sol"),
        "BNB": ("binance coin", "bnb"),
    }
    haystack = f" {title} {content} ".casefold()
    matched = []
    for coin, names in aliases.items():
        if any(re.search(rf"(?<![\w]){re.escape(name)}(?![\w])", haystack) for name in names):
            matched.append(coin)
    return tuple(matched)
