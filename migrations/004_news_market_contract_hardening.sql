-- Contract hardening for production news/sentiment and market ingestion.

ALTER TABLE news_items
    ADD COLUMN extraction_version VARCHAR(32) NOT NULL DEFAULT 'rss-v1',
    ADD COLUMN tagging_version VARCHAR(32) NOT NULL DEFAULT 'aliases-v1';

ALTER TABLE experiments
    ADD COLUMN sentiment_model VARCHAR(80) NOT NULL DEFAULT 'sentiment-v1',
    ADD COLUMN sentiment_model_version VARCHAR(80) NOT NULL DEFAULT '2026-08-01',
    ADD COLUMN sentiment_window_sec INT NOT NULL DEFAULT 3600
        CHECK (sentiment_window_sec BETWEEN 60 AND 604800),
    ADD COLUMN analysis_lag_sec INT NOT NULL DEFAULT 300
        CHECK (analysis_lag_sec BETWEEN 0 AND 86400);

ALTER TABLE search_runs
    ADD COLUMN non_improving INT NOT NULL DEFAULT 0 CHECK (non_improving >= 0),
    ADD COLUMN dedup_hits INT NOT NULL DEFAULT 0 CHECK (dedup_hits >= 0);

ALTER TABLE market_datasets
    ADD COLUMN bbo_content_hash CHAR(64);

ALTER TABLE sentiment_results DROP CONSTRAINT sentiment_results_score_check;
ALTER TABLE sentiment_results
    ADD CONSTRAINT sentiment_results_score_check CHECK (score BETWEEN 0 AND 1);

CREATE INDEX idx_news_related_coins ON news_items USING GIN(related_coins);
CREATE INDEX idx_sentiment_news_model
    ON sentiment_results(news_item_id, model, model_version, analyzed_at DESC);
CREATE INDEX idx_news_jobs_source_time
    ON news_collection_jobs(source_id, created_at DESC);
CREATE UNIQUE INDEX uq_news_job_running_per_source
    ON news_collection_jobs(source_id) WHERE status = 'running';

ALTER TABLE news_sources
    ADD CONSTRAINT news_sources_https_origin_check
    CHECK (allowed_origin ~ '^https://[a-z0-9.-]+$'),
    ADD CONSTRAINT news_sources_template_https_check
    CHECK (url_template ~ '^https://');

CREATE INDEX idx_event_consumptions_consumer
    ON event_consumptions(consumer_id, consumed_at DESC);

CREATE OR REPLACE VIEW read.news_v1 AS
SELECT n.id,n.source_id,n.canonical_url,n.url_hash,n.title,n.content_hash,
       n.content,n.published_at,n.related_coins,n.created_at,
       s.source_key,s.display_name,
       sr.label AS sentiment_label,sr.score AS sentiment_score,
       sr.model AS sentiment_model,sr.model_version AS sentiment_model_version,
       sr.analyzed_at AS sentiment_analyzed_at,
       n.extraction_version,n.tagging_version
FROM news_items n
JOIN news_sources s ON s.id = n.source_id
LEFT JOIN LATERAL (
    SELECT * FROM sentiment_results candidate
    WHERE candidate.news_item_id = n.id
    ORDER BY candidate.analyzed_at DESC, candidate.id DESC LIMIT 1
) sr ON TRUE;

GRANT SELECT ON read.news_v1 TO api_reader;
