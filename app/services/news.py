"""Research-owned news collection and sentiment orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from ..domain.news import ApprovedSource, CollectedItem
from ..infrastructure.ai import NewsExtractionUnavailable
from ..infrastructure.news import NewsProviderError, SsrfBlocked
from ..infrastructure.news.html import HtmlQualityGateFailed
from ..infrastructure.news.security import canonical_url, related_coins, sanitize_text, sha256_text
from ..infrastructure.sentiment import ContractViolation, SentimentUnavailable


_EXTRACTION_METHOD = "llm-fallback/v1"


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
    def __init__(self, store: object, provider: object, analyzer: object, extractor: object | None = None) -> None:
        self._store = store
        self._provider = provider
        self._analyzer = analyzer
        self._extractor = extractor

    def close(self) -> None:
        close = getattr(self._analyzer, "close", None)
        if close is not None:
            close()
        close = getattr(self._extractor, "close", None)
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
            provider = self._provider.get(source.kind) if isinstance(self._provider, dict) else self._provider
            try:
                items = provider.collect(source, since)
            except HtmlQualityGateFailed as failure:
                items = [self._fallback_item(source, failure, correlation_id)]
            found, inserted = self._store.complete_news_collection(
                job_id, source, items, correlation_id
            )
            return CollectionResult(source.id, job_id, "completed", found, len(inserted))
        except NewsExtractionUnavailable:
            self._store.fail_news_collection(job_id, "news_extraction_unavailable")
            return CollectionResult(source.id, job_id, "failed", error_code="news_extraction_unavailable")
        except SsrfBlocked:
            self._store.fail_news_collection(job_id, "news_source_blocked")
            return CollectionResult(source.id, job_id, "failed", error_code="news_source_blocked")
        except NewsProviderError as exc:
            self._store.fail_news_collection(job_id, exc.code)
            return CollectionResult(source.id, job_id, "failed", error_code=exc.code)
        except Exception:
            self._store.fail_news_collection(job_id, "internal_error")
            raise

    def _fallback_item(
        self, source: ApprovedSource, failure: HtmlQualityGateFailed, correlation_id: str | None
    ) -> CollectedItem:
        if self._extractor is None:
            raise NewsExtractionUnavailable("adaptive extraction is not configured")
        document_id = self._store.persist_news_document(source, failure)
        cache_key = self._extractor.cache_key(failure.document_text) if hasattr(self._extractor, "cache_key") else None
        cached = self._store.find_news_extraction(document_id, cache_key)
        if cached is not None:
            return cached
        result = self._extractor.extract(failure.document_text, correlation_id)
        title = sanitize_text(result.title, 512)
        content = sanitize_text(result.body, 20_000)
        document = failure.document_text.casefold()
        if not title or len(content) < 40 or title.casefold() not in document or content.casefold() not in document:
            self._store.persist_news_extraction(
                document_id=document_id, cache_key=cache_key, method=_EXTRACTION_METHOD,
                status="failed", error_code="evidence_invalid"
            )
            raise NewsProviderError("news_extraction_invalid", "fallback output lacks document evidence")
        normalized_url = canonical_url(failure.page_url)
        item = CollectedItem(
            source_id=source.id,
            canonical_url=normalized_url,
            url_hash=sha256_text(normalized_url),
            title=title,
            content=content,
            content_hash=sha256_text(f"{title}\n{content}"),
            published_at=failure.published_at,
            related_coins=related_coins(title, content),
            extraction_version=_EXTRACTION_METHOD,
        )
        self._store.persist_news_extraction(
            document_id=document_id, cache_key=cache_key, method=_EXTRACTION_METHOD, status="completed", item=item,
            model=result.model, model_version=result.model_version,
        )
        return item

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
