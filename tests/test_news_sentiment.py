from __future__ import annotations

from uuid import uuid4

import httpx
import pytest

from app.domain.news import ApprovedSource
from app.infrastructure.news import RssNewsProvider, SsrfBlocked, assert_public_https, canonical_url
from app.infrastructure.news.security import sanitize_text
from app.infrastructure.ai import NewsExtractionHTTPAdapter
from app.infrastructure.sentiment import ContractViolation, SentimentHTTPAdapter, SentimentUnavailable
from app.services.news import NewsService


def _source() -> ApprovedSource:
    return ApprovedSource(
        id=uuid4(),
        source_key="example_rss",
        display_name="Example",
        kind="rss",
        allowed_origin="https://news.example.com",
        url_template="https://news.example.com/feed.xml",
    )


def test_ssrf_guard_rejects_non_public_address() -> None:
    with pytest.raises(SsrfBlocked) as raised:
        assert_public_https(
            "https://news.example.com/feed.xml",
            "https://news.example.com",
            resolver=lambda _host, _port: ["127.0.0.1"],
        )
    assert raised.value.reason == "non_public_ip"


def test_ssrf_guard_rejects_redirect_to_another_origin() -> None:
    with pytest.raises(SsrfBlocked) as raised:
        assert_public_https(
            "https://attacker.example/feed.xml",
            "https://news.example.com",
            resolver=lambda _host, _port: ["93.184.216.34"],
        )
    assert raised.value.reason == "origin_mismatch"


def test_canonical_url_removes_tracking_and_fragment() -> None:
    assert canonical_url(
        "https://News.Example.com//story?utm_source=rss&id=7&fbclid=x#part"
    ) == "https://news.example.com/story?id=7"


def test_sanitize_text_drops_executable_markup() -> None:
    value = sanitize_text("<p>Hello &amp; safe</p><script>alert(1)</script>", 100)
    assert value == "Hello & safe"


def test_rss_provider_normalizes_and_bounds_items() -> None:
    payload = b"""<?xml version="1.0"?>
    <rss><channel><item>
      <title>Bitcoin &amp; Ethereum rally</title>
      <link>https://news.example.com/story?id=7&amp;utm_source=rss</link>
      <description><![CDATA[<p>BTC and ETH gain.</p><script>bad()</script>]]></description>
      <pubDate>Tue, 25 Aug 2026 10:00:00 GMT</pubDate>
    </item></channel></rss>"""
    provider = RssNewsProvider(
        resolver=lambda _host, _port: ["93.184.216.34"],
        fetcher=lambda _url, _host, _addresses: (
            200,
            {"content-type": "application/rss+xml; charset=utf-8"},
            payload,
        ),
    )
    items = provider.collect(_source(), None)
    assert len(items) == 1
    assert items[0].canonical_url == "https://news.example.com/story?id=7"
    assert items[0].related_coins == ("BTC", "ETH")
    assert "bad()" not in items[0].content


def _client(payload: dict[str, object], status: int = 200) -> httpx.Client:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=payload)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_sentiment_adapter_validates_contract() -> None:
    adapter = SentimentHTTPAdapter(
        "http://ai",
        client=_client(
            {
                "label": "POSITIVE",
                "score": 0.82,
                "model": "sentiment-v1",
                "model_version": "2026-08-01",
            }
        ),
    )
    result = adapter.analyze("Market rally")
    assert result.label == "POSITIVE"
    assert result.score == pytest.approx(0.82)


@pytest.mark.parametrize(
    "payload",
    [
        {"label": "mixed", "score": 0.8, "model": "m", "model_version": "v1"},
        {"label": "POSITIVE", "score": 1.7, "model": "m", "model_version": "v1"},
    ],
)
def test_sentiment_adapter_rejects_bad_model_output(payload: dict[str, object]) -> None:
    adapter = SentimentHTTPAdapter("http://ai", client=_client(payload))
    with pytest.raises(ContractViolation):
        adapter.analyze("Market rally")


def test_sentiment_adapter_maps_failure_without_fallback() -> None:
    adapter = SentimentHTTPAdapter("http://ai", client=_client({}, 503))
    with pytest.raises(SentimentUnavailable):
        adapter.analyze("Market rally")


def test_news_extraction_adapter_validates_source_excerpt_contract() -> None:
    adapter = NewsExtractionHTTPAdapter(
        "http://ai",
        client=_client({"title": "Bitcoin update", "body": "Bitcoin liquidity improved after sustained spot demand.", "model": "m", "model_version": "v1"}),
    )

    result = adapter.extract("Bitcoin update. Bitcoin liquidity improved after sustained spot demand.")

    assert result.title == "Bitcoin update"
    assert result.model == "m"


def test_news_extraction_cache_key_changes_with_model_or_document() -> None:
    adapter = NewsExtractionHTTPAdapter("http://ai", model="model-a", model_version="v1", client=_client({}))

    first = adapter.cache_key("sanitized document")
    second = adapter.cache_key("different document")
    changed_model = NewsExtractionHTTPAdapter("http://ai", model="model-b", model_version="v1", client=_client({}))

    assert first != second
    assert first != changed_model.cache_key("sanitized document")


class _Store:
    def __init__(self) -> None:
        self.persisted = []

    def pending_sentiment_items(self, _model: str, _version: str, _limit: int):
        return [{"id": uuid4(), "title": "Bitcoin rally", "content": "Strong demand"}]

    def persist_sentiment(self, item_id, result):
        self.persisted.append((item_id, result))
        return True


class _UnavailableAnalyzer:
    def analyze(self, _text: str, _request_id: str | None = None):
        raise SentimentUnavailable("down")


def test_ai_unavailable_persists_no_placeholder() -> None:
    store = _Store()
    service = NewsService(store, object(), _UnavailableAnalyzer())
    result = service.analyze_pending(model="sentiment-v1", model_version="v1")
    assert result.unavailable == 1
    assert store.persisted == []
