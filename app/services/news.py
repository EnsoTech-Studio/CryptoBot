"""Research-owned news collection and sentiment orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from ..domain.news import ApprovedSource
from ..infrastructure.news import NewsProviderError
from ..infrastructure.sentiment import ContractViolation, SentimentUnavailable


@dataclass(frozen=True)
class CollectionResult:
    source_id: UUID
    job_id: UUID | None
    status: str
    items_found: int = 0
    items_new: int = 0
    error_code: str | None = None


@dataclass(frozen=True)
class SentimentBatchResult:
    attempted: int
    analyzed: int
    unavailable: int
    contract_violations: int


class NewsService:
    def __init__(self, store: object, provider: object, analyzer: object) -> None:
        self._store = store
        self._provider = provider
        self._analyzer = analyzer

    def close(self) -> None:
        close = getattr(self._analyzer, "close", None)
        if close is not None:
            close()

    def collect_all(
        self, source_id: UUID | None = None, correlation_id: str | None = None
    ) -> list[CollectionResult]:
        sources: list[ApprovedSource] = self._store.list_approved_sources(source_id)
        return [self.collect_source(source, correlation_id) for source in sources]

    def collect_source(
        self, source: ApprovedSource, correlation_id: str | None = None
    ) -> CollectionResult:
        job_id = self._store.begin_news_collection(source.id)
        if job_id is None:
            return CollectionResult(source.id, None, "already_running")
        try:
            since = self._store.latest_news_collection(source.id)
            items = self._provider.collect(source, since)
            found, inserted = self._store.complete_news_collection(
                job_id, source, items, correlation_id
            )
            return CollectionResult(source.id, job_id, "completed", found, len(inserted))
        except NewsProviderError as exc:
            self._store.fail_news_collection(job_id, exc.code)
            return CollectionResult(source.id, job_id, "failed", error_code=exc.code)
        except Exception:
            self._store.fail_news_collection(job_id, "internal_error")
            raise

    def analyze_pending(
        self,
        *,
        model: str,
        model_version: str,
        limit: int = 200,
        correlation_id: str | None = None,
    ) -> SentimentBatchResult:
        rows = self._store.pending_sentiment_items(model, model_version, limit)
        analyzed = unavailable = violations = 0
        for row in rows:
            text = f"{row['title']}\n{row['content'][:2000]}".strip()
            try:
                result = self._analyzer.analyze(text, correlation_id)
                if result.model != model or result.model_version != model_version:
                    raise ContractViolation("AI model identity differs from configured batch")
                if self._store.persist_sentiment(row["id"], result):
                    analyzed += 1
            except SentimentUnavailable:
                unavailable += 1
            except ContractViolation:
                violations += 1
        return SentimentBatchResult(len(rows), analyzed, unavailable, violations)
