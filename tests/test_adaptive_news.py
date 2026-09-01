from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.domain.news import ApprovedSource, CollectedItem
from app.infrastructure.ai import NewsExtractionUnavailable
from app.infrastructure.news import HtmlQualityGateFailed
from app.services.news import NewsService


SOURCE = ApprovedSource(
    id=uuid4(),
    source_key="example_html",
    display_name="Example HTML",
    kind="url",
    allowed_origin="https://example.com",
    url_template="https://example.com/article",
)
DOCUMENT = "Bitcoin market update. Bitcoin liquidity improved after a broad market recovery and spot demand increased."


class _Store:
    def __init__(self) -> None:
        self.items = []
        self.failed = []
        self.documents = []
        self.attempts = []
        self.cached = None

    def begin_news_collection(self, _source_id):
        return uuid4()

    def latest_news_collection(self, _source_id):
        return None

    def complete_news_collection(self, _job_id, _source, items, _correlation_id):
        self.items.extend(items)
        return len(items), [uuid4() for _ in items]

    def fail_news_collection(self, _job_id, reason):
        self.failed.append(reason)

    def persist_news_document(self, source, failure):
        self.documents.append((source, failure))
        return uuid4()

    def find_news_extraction(self, *_):
        return self.cached

    def persist_news_extraction(self, **kwargs):
        self.attempts.append(kwargs)


class _QualityFailingProvider:
    def collect(self, _source, _since):
        raise HtmlQualityGateFailed(
            page_url="https://example.com/article",
            document_text=DOCUMENT,
            title_hint="Bitcoin market update",
            published_at=datetime(2026, 8, 31, tzinfo=UTC),
            reason="body_too_short",
        )


class _Extractor:
    def __init__(self) -> None:
        self.inputs = []

    def extract(self, document_text, _request_id=None):
        self.inputs.append(document_text)
        return SimpleNamespace(
            title="Bitcoin market update",
            body="Bitcoin liquidity improved after a broad market recovery and spot demand increased.",
            model="openai/gpt-oss-120b",
            model_version="test",
        )


def test_quality_failure_uses_sanitized_document_fallback_and_persists_provenance():
    store = _Store()
    extractor = _Extractor()
    service = NewsService(store, {"url": _QualityFailingProvider()}, object(), extractor=extractor)

    result = service.collect_source(SOURCE, "request-1")

    assert result.status == "completed"
    assert extractor.inputs == [DOCUMENT]
    assert len(store.items) == 1
    assert store.items[0].extraction_version == "llm-fallback/v1"
    assert len(store.documents) == len(store.attempts) == 1


def test_unavailable_fallback_fails_collection_without_fake_item():
    class UnavailableExtractor:
        def extract(self, _document_text, _request_id=None):
            raise NewsExtractionUnavailable("down")

    store = _Store()
    service = NewsService(store, {"url": _QualityFailingProvider()}, object(), extractor=UnavailableExtractor())

    result = service.collect_source(SOURCE)

    assert result.status == "failed"
    assert result.error_code == "news_extraction_unavailable"
    assert store.items == []


def test_cached_fallback_is_reused_without_another_ai_request():
    store = _Store()
    extractor = _Extractor()
    store.cached = CollectedItem(
        source_id=SOURCE.id,
        canonical_url="https://example.com/article",
        url_hash="a" * 64,
        title="Bitcoin market update",
        content="Bitcoin liquidity improved after a broad market recovery and spot demand increased.",
        content_hash="b" * 64,
        published_at=datetime(2026, 8, 31, tzinfo=UTC),
        extraction_version="llm-fallback/v1",
    )

    result = NewsService(store, {"url": _QualityFailingProvider()}, object(), extractor=extractor).collect_source(SOURCE)

    assert result.status == "completed"
    assert extractor.inputs == []
