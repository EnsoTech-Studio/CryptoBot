"""Bounded HTML-page news adapter for approved sources."""

from __future__ import annotations

import email.utils
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from ...domain.news import ApprovedSource, CollectedItem
from .rss import MAX_REDIRECTS, MAX_RESPONSE_BYTES, NewsProviderError, _pinned_https_get
from .security import assert_public_https, canonical_url, related_coins, sanitize_text, sha256_text

_ALLOWED_CONTENT_TYPES = {"text/html", "application/xhtml+xml"}
_SKIP_TAGS = {"script", "style", "noscript", "svg", "nav", "footer"}
_MONTH_DATE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
    r"\d{1,2},\s+\d{4}\b",
    re.I,
)


class HtmlQualityGateFailed(NewsProviderError):
    def __init__(
        self,
        *,
        page_url: str,
        document_text: str,
        title_hint: str,
        published_at: datetime,
        reason: str,
    ) -> None:
        self.page_url = page_url
        self.document_text = document_text
        self.title_hint = title_hint
        self.published_at = published_at
        super().__init__("quality_gate_failed", reason)


class _ArticleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title: list[str] = []
        self.heading: list[str] = []
        self.paragraphs: list[str] = []
        self.published: str | None = None
        self._tag_stack: list[str] = []
        self._buffer: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attributes = dict(attrs)
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        if tag == "time":
            self.published = attributes.get("datetime") or self.published
        if tag in {"title", "h1", "h2", "p"}:
            self._buffer = []
        self._tag_stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._tag_stack:
            self._tag_stack.pop()
        text = sanitize_text(" ".join(self._buffer), 2_000)
        if self._skip_depth == 0 and text:
            if tag == "title":
                self.title.append(text)
            elif tag in {"h1", "h2"}:
                self.heading.append(text)
            elif tag == "p":
                self.paragraphs.append(text)
        if tag in _SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        if tag in {"title", "h1", "h2", "p"}:
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._buffer.append(data)


@dataclass
class _ListingEntry:
    url: str = ""
    title: str = ""
    summary: list[str] = field(default_factory=list)
    published: str | None = None


class _ListingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.entries: list[_ListingEntry] = []
        self._current: _ListingEntry | None = None
        self._article_depth = 0
        self._skip_depth = 0
        self._capture_tag = ""
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attributes = dict(attrs)
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        if tag == "article":
            if self._current is None:
                self._current = _ListingEntry()
            self._article_depth += 1
        if self._current is None:
            return
        if tag == "a" and not self._current.url:
            self._current.url = attributes.get("href") or ""
        if tag == "time" and not self._current.published:
            self._current.published = attributes.get("datetime")
        if tag in {"a", "h1", "h2", "h3", "p", "time"}:
            self._capture_tag = tag
            self._buffer = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._current is not None and tag == self._capture_tag:
            text = sanitize_text(" ".join(self._buffer), 2_000)
            if self._skip_depth == 0 and text:
                if tag in {"h1", "h2", "h3"} and not self._current.title:
                    self._current.title = text
                elif tag == "a" and not self._current.title and len(text) >= 12:
                    self._current.title = text
                elif tag == "p":
                    self._current.summary.append(text)
                elif tag == "time" and not self._current.published:
                    self._current.published = text
            self._capture_tag = ""
            self._buffer = []
        if tag == "article" and self._current is not None:
            self._article_depth -= 1
            if self._article_depth <= 0:
                if self._current.title and self._current.url:
                    self.entries.append(self._current)
                self._current = None
                self._article_depth = 0
        if tag in _SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._current is not None and self._skip_depth == 0 and self._capture_tag:
            self._buffer.append(data)


class HtmlNewsProvider:
    def collect(self, source: ApprovedSource, since: datetime | None) -> list[CollectedItem]:
        if not source.is_active or source.kind not in {"url", "html"}:
            raise NewsProviderError("unsupported_source", "source is not an active HTML source")
        current = source.url_template
        for redirect in range(MAX_REDIRECTS + 1):
            host, addresses = assert_public_https(current, source.allowed_origin)
            status, headers, payload = _pinned_https_get(current, host, addresses)
            if status in {301, 302, 303, 307, 308}:
                if redirect == MAX_REDIRECTS:
                    raise NewsProviderError("too_many_redirects", "news source redirected too often")
                location = headers.get("location", "")
                if not location:
                    raise NewsProviderError("invalid_redirect", "news redirect has no location")
                current = urljoin(current, location)
                continue
            if status < 200 or status >= 300:
                raise NewsProviderError("upstream_status", f"news source returned HTTP {status}")
            content_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if content_type not in _ALLOWED_CONTENT_TYPES:
                raise NewsProviderError("invalid_content_type", "news source returned unsupported HTML")
            return self._parse(source, current, payload, since)
        raise AssertionError("redirect loop must return or raise")

    @staticmethod
    def _parse(
        source: ApprovedSource, page_url: str, payload: bytes, since: datetime | None
    ) -> list[CollectedItem]:
        if len(payload) > MAX_RESPONSE_BYTES:
            raise NewsProviderError("response_too_large", "news response exceeded 2 MiB")
        listing_items = _parse_listing(source, page_url, payload, since)
        if len(listing_items) >= 2:
            return listing_items
        parser = _ArticleParser()
        try:
            parser.feed(payload.decode("utf-8", "replace"))
            parser.close()
        except Exception as exc:
            raise NewsProviderError("parse_error", "news page is not valid HTML") from exc
        title = sanitize_text((parser.heading or parser.title or [""])[0], 512)
        content = sanitize_text("\n".join(parser.paragraphs), 20_000)
        published = _parse_date(parser.published)
        if since is not None and published <= since:
            return []
        if not title or len(content) < 40:
            raise HtmlQualityGateFailed(
                page_url=page_url,
                document_text=sanitize_text(payload.decode("utf-8", "replace"), 20_000),
                title_hint=title,
                published_at=published,
                reason="body_too_short" if title else "title_missing",
            )
        normalized_url = canonical_url(page_url)
        return [CollectedItem(
            source_id=source.id,
            canonical_url=normalized_url,
            url_hash=sha256_text(normalized_url),
            title=title,
            content=content,
            content_hash=sha256_text(f"{title}\n{content}"),
            published_at=published,
            related_coins=related_coins(title, content),
            extraction_version="html-v1",
        )]


def _parse_date(value: str | None) -> datetime:
    if value:
        candidate = value.strip()
        month_match = _MONTH_DATE.search(candidate)
        if month_match:
            candidate = month_match.group(0)
        try:
            parsed = email.utils.parsedate_to_datetime(candidate)
            return (parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)).astimezone(UTC)
        except (TypeError, ValueError):
            pass
        try:
            parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
            return (parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)).astimezone(UTC)
        except ValueError:
            pass
        for pattern in ("%B %d, %Y", "%b %d, %Y"):
            try:
                return datetime.strptime(candidate, pattern).replace(tzinfo=UTC)
            except ValueError:
                pass
    return datetime.now(tz=UTC)


def _parse_listing(
    source: ApprovedSource, page_url: str, payload: bytes, since: datetime | None
) -> list[CollectedItem]:
    parser = _ListingParser()
    try:
        parser.feed(payload.decode("utf-8", "replace"))
        parser.close()
    except Exception as exc:
        raise NewsProviderError("parse_error", "news page is not valid HTML") from exc

    origin_host = urlsplit(source.allowed_origin).hostname
    result: list[CollectedItem] = []
    seen: set[str] = set()
    for entry in parser.entries[:50]:
        try:
            normalized_url = canonical_url(urljoin(page_url, entry.url))
        except ValueError:
            continue
        if urlsplit(normalized_url).hostname != origin_host or normalized_url in seen:
            continue
        seen.add(normalized_url)
        title = sanitize_text(entry.title, 512)
        summary = sanitize_text("\n".join(entry.summary), 20_000)
        content = summary if len(summary) >= 40 else sanitize_text(f"{title}\n{summary}", 20_000)
        if not title or len(content) < 40:
            continue
        published = _parse_date(entry.published)
        if since is not None and published <= since:
            continue
        result.append(CollectedItem(
            source_id=source.id,
            canonical_url=normalized_url,
            url_hash=sha256_text(normalized_url),
            title=title,
            content=content,
            content_hash=sha256_text(f"{title}\n{content}"),
            published_at=published,
            related_coins=related_coins(title, content),
            extraction_version="html-list-v1",
        ))
    return result
