from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.news import ApprovedSource
from app.infrastructure.news import HtmlNewsProvider, NewsProviderError


SOURCE = ApprovedSource(
    id=uuid4(),
    source_key="example",
    display_name="Example",
    kind="url",
    allowed_origin="https://example.com",
    url_template="https://example.com/article",
)


def test_html_provider_extracts_one_sanitized_article():
    payload = b"""
    <html><head><title>Ignored page title</title><script>alert(1)</script></head>
    <body><article><h1>Bitcoin market update</h1>
    <p>Bitcoin liquidity improved after a broad market recovery and spot demand increased.</p>
    <p>Traders continued to watch volatility and risk management levels during the session.</p>
    </article></body></html>
    """
    items = HtmlNewsProvider._parse(SOURCE, SOURCE.url_template, payload, None)
    assert len(items) == 1
    assert items[0].title == "Bitcoin market update"
    assert "alert" not in items[0].content
    assert items[0].extraction_version == "html-v1"


def test_html_provider_extracts_listing_entries_from_html_source():
    source = ApprovedSource(
        id=uuid4(),
        source_key="example_listing",
        display_name="Example Listing",
        kind="html",
        allowed_origin="https://example.com",
        url_template="https://example.com/articles",
    )
    payload = b"""
    <html><body>
      <article>
        <a href="/bitcoin-rally">Bitcoin rally strengthens</a>
        <time>September 1, 2026</time>
        <p>Bitcoin demand improved as ETF flows increased during the session.</p>
      </article>
      <article>
        <h2><a href="/ethereum-liquidity">Ethereum liquidity steadies</a></h2>
        <time datetime="2026-09-01T12:00:00Z"></time>
        <p>Ethereum liquidity remained stable while traders watched network activity.</p>
      </article>
    </body></html>
    """

    items = HtmlNewsProvider._parse(source, source.url_template, payload, None)

    assert len(items) == 2
    assert items[0].canonical_url == "https://example.com/bitcoin-rally"
    assert items[0].related_coins == ("BTC",)
    assert items[0].extraction_version == "html-list-v1"


def test_html_provider_applies_since_cutoff():
    payload = b"<html><body><h1>Update</h1><p>" + b"enough article text " * 5 + b"</p></body></html>"
    assert HtmlNewsProvider._parse(
        SOURCE,
        SOURCE.url_template,
        payload,
        datetime.now(tz=UTC) + timedelta(minutes=1),
    ) == []


def test_html_provider_quality_gate_is_explicit():
    with pytest.raises(NewsProviderError, match="body_too_short"):
        HtmlNewsProvider._parse(SOURCE, SOURCE.url_template, b"<h1>Empty</h1>", None)
