"""Seed three safe demo news documents through the real OpenAI-backed extraction pipeline."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import psycopg
from psycopg.rows import dict_row

from app.config import Settings
from app.domain.news import ApprovedSource
from app.infrastructure.ai import NewsExtractionHTTPAdapter
from app.infrastructure.news.html import HtmlNewsProvider
from app.infrastructure.news.security import sanitize_text
from app.infrastructure.postgres.store import Store
from app.infrastructure.sentiment import SentimentHTTPAdapter
from app.services.news import NewsService


@dataclass(frozen=True)
class DemoArticle:
    source_key: str
    display_name: str
    slug: str
    html: str

    @property
    def page_url(self) -> str:
        return f"https://demo.cryptobot.local/{self.slug}"


DEMO_ARTICLES = (
    DemoArticle(
        "demo-news-btc-inflows",
        "CryptoBot Demo: BTC inflows",
        "btc-inflows",
        """<html><head><title>Bitcoin demand improves after fund inflows</title></head>
        <body><h1>Bitcoin demand improves after fund inflows</h1><article>
        Bitcoin spot fund inflows increased during the session while BTC liquidity remained stable.
        Traders reported stronger demand but the article does not make a price prediction.
        </article></body></html>""",
    ),
    DemoArticle(
        "demo-news-eth-network",
        "CryptoBot Demo: ETH network",
        "eth-network",
        """<html><head><title>Ethereum network activity remains steady</title></head>
        <body><h1>Ethereum network activity remains steady</h1><article>
        Ethereum transaction activity and liquidity remained broadly unchanged after a routine update.
        Market participants described the update as operational and did not report a directional catalyst.
        </article></body></html>""",
    ),
    DemoArticle(
        "demo-news-sol-outage",
        "CryptoBot Demo: SOL operations",
        "sol-operations",
        """<html><head><title>Solana traders monitor service disruption report</title></head>
        <body><h1>Solana traders monitor service disruption report</h1><article>
        A service disruption report led some Solana market participants to reduce risk while details were reviewed.
        The report says trading conditions may stay volatile until the operational status is clarified.
        </article></body></html>""",
    ),
)


def _load_local_env() -> None:
    """Make the manual demo command use the repository .env without a new dependency."""
    env_file = Path(__file__).resolve().parents[1] / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key and not key.lstrip().startswith("#"):
            os.environ.setdefault(key.strip(), value.strip())


def parse_demo_html(source: ApprovedSource, article: DemoArticle):
    """Intentionally trip the deterministic quality gate so the LLM extracts raw HTML text."""
    return HtmlNewsProvider._parse(source, article.page_url, article.html.encode("utf-8"), None)


class _DemoHtmlProvider:
    def __init__(self, articles: Iterable[DemoArticle]) -> None:
        self._articles = {article.source_key: article for article in articles}

    def collect(self, source: ApprovedSource, _since: object) -> list[object]:
        return parse_demo_html(source, self._articles[source.source_key])


def _upsert_sources(database_url: str, articles: Iterable[DemoArticle]) -> dict[str, ApprovedSource]:
    sources: dict[str, ApprovedSource] = {}
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        for article in articles:
            row = connection.execute(
                """
                INSERT INTO news_sources(source_key,display_name,kind,allowed_origin,url_template,is_active)
                VALUES (%s,%s,'url','https://demo.cryptobot.local',%s,FALSE)
                ON CONFLICT(source_key) DO UPDATE SET
                  display_name=EXCLUDED.display_name, allowed_origin=EXCLUDED.allowed_origin,
                  url_template=EXCLUDED.url_template, is_active=FALSE
                RETURNING id,source_key,display_name,kind,allowed_origin,url_template,is_active
                """,
                (article.source_key, article.display_name, article.page_url),
            ).fetchone()
            sources[article.source_key] = ApprovedSource(**row)
    return sources


def _digest(articles: Iterable[DemoArticle]) -> str:
    return "\n\n".join(
        f"Source: {article.display_name}\n{sanitize_text(article.html, 3_000)}"
        for article in articles
    )[:10_000]


def main() -> int:
    _load_local_env()
    settings = Settings.from_env()
    sources = _upsert_sources(settings.database_url, DEMO_ARTICLES)
    analyzer = SentimentHTTPAdapter(settings.ai_service_url, settings.ai_timeout_s)
    extractor = NewsExtractionHTTPAdapter(
        settings.ai_service_url,
        settings.ai_timeout_s,
        model=settings.sentiment_model,
        model_version=settings.sentiment_model_version,
    )
    service = NewsService(
        Store(settings.database_url), {"url": _DemoHtmlProvider(DEMO_ARTICLES)}, analyzer, extractor
    )
    try:
        collections = []
        for article in DEMO_ARTICLES:
            collections.append(service.collect_source(sources[article.source_key], f"news-demo-{article.slug}"))
        batch = service.analyze_pending(
            model=settings.sentiment_model,
            model_version=settings.sentiment_model_version,
            correlation_id="news-demo-sentiment",
        )
        aggregate = analyzer.analyze_aggregate(_digest(DEMO_ARTICLES), "news-demo-aggregate")
    finally:
        service.close()
    print(json.dumps({
        "sources": len(sources),
        "collections": [{"status": item.status, "new": item.items_new} for item in collections],
        "sentiment": {"attempted": batch.attempted, "analyzed": batch.analyzed},
        "aggregate_insight": {"label": aggregate.label, "score": aggregate.score, "model": aggregate.model, "model_version": aggregate.model_version},
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
