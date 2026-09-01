-- Provenance and deterministic cache for the HTML quality-gate fallback.
CREATE TABLE news_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES news_sources(id) ON DELETE RESTRICT,
    canonical_url TEXT NOT NULL,
    content_hash CHAR(64) NOT NULL,
    sanitized_document TEXT NOT NULL,
    title_hint TEXT NOT NULL DEFAULT '',
    published_at TIMESTAMPTZ NOT NULL,
    quality_reason VARCHAR(64) NOT NULL,
    sanitizer_version VARCHAR(48) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(source_id, content_hash)
);
CREATE INDEX idx_news_documents_source_created
    ON news_documents(source_id, created_at DESC);

CREATE TABLE news_extraction_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES news_documents(id) ON DELETE CASCADE,
    cache_key CHAR(64) NOT NULL,
    method VARCHAR(48) NOT NULL,
    status VARCHAR(16) NOT NULL CHECK (status IN ('completed','failed')),
    model VARCHAR(120),
    model_version VARCHAR(120),
    prompt_version VARCHAR(48) NOT NULL DEFAULT 'news-extract/v1',
    schema_version VARCHAR(48) NOT NULL DEFAULT 'news-extraction/v1',
    quality_policy_version VARCHAR(48) NOT NULL DEFAULT 'html-quality/v1',
    result_json JSONB,
    error_code VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(document_id, cache_key),
    CHECK (
        (status = 'completed' AND result_json IS NOT NULL AND model IS NOT NULL AND model_version IS NOT NULL)
        OR (status = 'failed' AND error_code IS NOT NULL)
    )
);
CREATE INDEX idx_news_extraction_attempts_document_status
    ON news_extraction_attempts(document_id, status, created_at DESC);

GRANT SELECT, INSERT, UPDATE ON news_documents, news_extraction_attempts TO research_runtime;
