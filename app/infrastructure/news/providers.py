"""Registry for approved news collection providers."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from ...domain.news import ApprovedSource, CollectedItem
from .html import HtmlNewsProvider
from .rss import NewsProviderError, RssNewsProvider


class NewsProviderRegistry:
    """Small dispatch boundary for source kinds.

    Adding a new provider should only require registering a kind here and
    allowing that kind at the API/DB boundary.
    """

    def __init__(self) -> None:
        self._providers: dict[str, object] = {}
        self._aliases: dict[str, str] = {}

    def register(self, kind: str, provider: object, aliases: Iterable[str] = ()) -> None:
        key = _normalize_kind(kind)
        self._providers[key] = provider
        self._aliases[key] = key
        for alias in aliases:
            self._aliases[_normalize_kind(alias)] = key

    def get(self, kind: str) -> object:
        key = self._aliases.get(_normalize_kind(kind))
        if key is None or key not in self._providers:
            raise NewsProviderError("unsupported_source_kind", f"unsupported news provider kind: {kind}")
        return self._providers[key]

    def collect(self, source: ApprovedSource, since: datetime | None) -> list[CollectedItem]:
        provider = self.get(source.kind)
        return provider.collect(source, since)

    def supported_kinds(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))


def default_news_provider_registry() -> NewsProviderRegistry:
    registry = NewsProviderRegistry()
    registry.register("rss", RssNewsProvider())
    registry.register("html", HtmlNewsProvider(), aliases=("url",))
    return registry


def _normalize_kind(value: str) -> str:
    key = value.strip().lower()
    if not key:
        raise ValueError("provider kind must not be blank")
    return key
