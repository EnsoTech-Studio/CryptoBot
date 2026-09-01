"""Periodic news collection and sentiment backfill worker."""

from __future__ import annotations

import json
import os
import signal
import sys
import threading
import time
from datetime import UTC, datetime

from .config import Settings
from .infrastructure.ai import NewsExtractionHTTPAdapter
from .infrastructure.news import HtmlNewsProvider, RssNewsProvider
from .infrastructure.postgres.store import Store
from .infrastructure.sentiment import SentimentHTTPAdapter
from .services.news import NewsService


def _log(level: str, operation: str, **fields: object) -> None:
    print(
        json.dumps(
            {
                "timestamp": datetime.now(tz=UTC).isoformat(),
                "level": level,
                "service": "research-news-worker",
                "operation": operation,
                **fields,
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        file=sys.stderr if level == "error" else sys.stdout,
        flush=True,
    )


def _positive_seconds(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


def main() -> int:
    settings = Settings.from_env()
    store = Store(settings.database_url)
    analyzer = SentimentHTTPAdapter(settings.ai_service_url, settings.ai_timeout_s)
    service = NewsService(
        store, {"rss": RssNewsProvider(), "url": HtmlNewsProvider()}, analyzer,
        NewsExtractionHTTPAdapter(
            settings.ai_service_url, settings.ai_timeout_s,
            model=settings.sentiment_model, model_version=settings.sentiment_model_version,
        ),
    )
    stop = threading.Event()

    def shutdown(*_: object) -> None:
        stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, shutdown)

    collection_interval = _positive_seconds("NEWS_COLLECTION_INTERVAL_SECONDS", 900.0)
    sentiment_interval = _positive_seconds("SENTIMENT_BACKFILL_INTERVAL_SECONDS", 60.0)
    next_collection = 0.0
    next_sentiment = 0.0
    try:
        while not stop.is_set():
            now = time.monotonic()
            if now >= next_collection:
                try:
                    results = service.collect_all()
                    _log(
                        "info", "news_collection_completed",
                        source_count=len(results),
                        items_new=sum(item.items_new for item in results),
                    )
                except Exception as exc:  # noqa: BLE001 - scheduler stays alive
                    _log(
                        "error", "news_collection_failed",
                        error_code=type(exc).__name__,
                    )
                next_collection = now + collection_interval
            if now >= next_sentiment:
                try:
                    result = service.analyze_pending(
                        model=settings.sentiment_model,
                        model_version=settings.sentiment_model_version,
                    )
                    _log(
                        "info", "sentiment_backfill_completed",
                        attempted=result.attempted,
                        analyzed=result.analyzed,
                        unavailable=result.unavailable,
                        contract_violations=result.contract_violations,
                    )
                except Exception as exc:  # noqa: BLE001 - scheduler stays alive
                    _log(
                        "error", "sentiment_backfill_failed",
                        error_code=type(exc).__name__,
                    )
                next_sentiment = now + sentiment_interval
            stop.wait(min(1.0, max(0.05, min(next_collection, next_sentiment) - now)))
    finally:
        service.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
