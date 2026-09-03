import pytest

from app.infrastructure.news import NewsProviderError, NewsProviderRegistry, default_news_provider_registry


def test_news_provider_registry_supports_aliases() -> None:
    provider = object()
    registry = NewsProviderRegistry()
    registry.register("html", provider, aliases=("url",))

    assert registry.get("html") is provider
    assert registry.get("url") is provider


def test_default_news_provider_registry_includes_rss_and_html() -> None:
    registry = default_news_provider_registry()

    assert "rss" in registry.supported_kinds()
    assert "html" in registry.supported_kinds()
    assert registry.get("url") is registry.get("html")


def test_news_provider_registry_rejects_unknown_kind() -> None:
    with pytest.raises(NewsProviderError, match="unsupported news provider kind"):
        default_news_provider_registry().get("api")
