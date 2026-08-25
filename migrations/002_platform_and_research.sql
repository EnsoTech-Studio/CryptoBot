CREATE SCHEMA IF NOT EXISTS read;
CREATE SCHEMA IF NOT EXISTS lab;

ALTER TABLE experiments ADD COLUMN idempotency_key VARCHAR(120);
CREATE UNIQUE INDEX uq_experiments_owner_idempotency
    ON experiments(owner_id, idempotency_key) WHERE idempotency_key IS NOT NULL;

CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash CHAR(64) UNIQUE NOT NULL,
    family_id UUID NOT NULL,
    parent_id UUID REFERENCES refresh_tokens(id) ON DELETE RESTRICT,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_refresh_tokens_user ON refresh_tokens(user_id, created_at DESC);

CREATE TABLE user_quotas (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    max_concurrent_runs INT NOT NULL DEFAULT 2 CHECK (max_concurrent_runs > 0),
    max_candidates_per_run INT NOT NULL DEFAULT 50 CHECK (max_candidates_per_run > 0),
    max_candles_per_experiment INT NOT NULL DEFAULT 20000 CHECK (max_candles_per_experiment > 0)
);

CREATE TABLE candles (
    provider VARCHAR(24) NOT NULL,
    symbol VARCHAR(24) NOT NULL,
    timeframe timeframe_enum NOT NULL,
    open_time TIMESTAMPTZ NOT NULL,
    close_time TIMESTAMPTZ NOT NULL,
    open NUMERIC(24,8) NOT NULL,
    high NUMERIC(24,8) NOT NULL,
    low NUMERIC(24,8) NOT NULL,
    close NUMERIC(24,8) NOT NULL,
    volume NUMERIC(30,8) NOT NULL,
    trade_count INT,
    PRIMARY KEY(provider, symbol, timeframe, open_time),
    CHECK (high >= open AND high >= close AND high >= low),
    CHECK (low <= open AND low <= close),
    CHECK (close_time > open_time),
    CHECK (volume >= 0)
);
CREATE INDEX idx_candles_range ON candles(provider, symbol, timeframe, open_time DESC);

CREATE TABLE stream_checkpoints (
    provider VARCHAR(24) NOT NULL,
    symbol VARCHAR(24) NOT NULL,
    timeframe timeframe_enum NOT NULL,
    last_closed_at TIMESTAMPTZ,
    last_source_sequence BIGINT,
    is_stale BOOLEAN NOT NULL DEFAULT TRUE,
    reconnect_count INT NOT NULL DEFAULT 0,
    source_fetched_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY(provider, symbol, timeframe)
);

CREATE TABLE search_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id UUID NOT NULL REFERENCES users(id),
    generator_id VARCHAR(48) NOT NULL,
    status VARCHAR(24) NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued','running','paused','completed','failed','cancelled')),
    search_space JSONB NOT NULL,
    stop_conditions JSONB NOT NULL,
    market_dataset_id UUID NOT NULL REFERENCES market_datasets(id) ON DELETE RESTRICT,
    seed BIGINT NOT NULL,
    generated INT NOT NULL DEFAULT 0,
    tested INT NOT NULL DEFAULT 0,
    failed INT NOT NULL DEFAULT 0,
    best_score NUMERIC(14,6),
    current_candidate_hash CHAR(64),
    stop_reason VARCHAR(64),
    idempotency_key VARCHAR(120),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(owner_id, idempotency_key)
);
CREATE INDEX idx_search_runs_owner ON search_runs(owner_id, created_at DESC);

CREATE TABLE search_candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    search_run_id UUID NOT NULL REFERENCES search_runs(id) ON DELETE CASCADE,
    ordinal INT NOT NULL,
    candidate_definition JSONB NOT NULL,
    candidate_hash CHAR(64) NOT NULL,
    generated_by VARCHAR(48) NOT NULL,
    generation_meta JSONB NOT NULL DEFAULT '{}',
    experiment_id UUID UNIQUE REFERENCES experiments(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(search_run_id, ordinal),
    UNIQUE(search_run_id, candidate_hash)
);
ALTER TABLE experiments
    ADD CONSTRAINT fk_experiments_search_candidate
    FOREIGN KEY(search_candidate_id) REFERENCES search_candidates(id) ON DELETE RESTRICT;

CREATE TABLE search_actions (
    command_id UUID PRIMARY KEY,
    search_run_id UUID NOT NULL REFERENCES search_runs(id) ON DELETE CASCADE,
    action VARCHAR(16) NOT NULL CHECK (action IN ('pause','resume','cancel')),
    actor_id UUID NOT NULL REFERENCES users(id),
    requested_from VARCHAR(24) NOT NULL,
    resulted_in VARCHAR(24) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE score_policies (
    version VARCHAR(24) PRIMARY KEY,
    min_trades INT NOT NULL CHECK (min_trades >= 0),
    weights JSONB NOT NULL,
    formula TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_score_policy_active ON score_policies(is_active) WHERE is_active;

CREATE TABLE leaderboard_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_id UUID NOT NULL REFERENCES evaluations(id) ON DELETE RESTRICT,
    market_dataset_id UUID NOT NULL REFERENCES market_datasets(id) ON DELETE RESTRICT,
    score_policy_version VARCHAR(24) NOT NULL REFERENCES score_policies(version) ON DELETE RESTRICT,
    score NUMERIC(14,6) NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(evaluation_id, score_policy_version)
);
CREATE INDEX idx_leaderboard_topk
    ON leaderboard_entries(market_dataset_id, score_policy_version, score DESC, observed_at, evaluation_id);

CREATE TABLE news_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_key VARCHAR(64) UNIQUE NOT NULL,
    display_name VARCHAR(120) NOT NULL,
    kind VARCHAR(24) NOT NULL CHECK (kind IN ('rss','url')),
    allowed_origin TEXT NOT NULL,
    url_template TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_collected_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE news_collection_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES news_sources(id) ON DELETE RESTRICT,
    status VARCHAR(24) NOT NULL CHECK (status IN ('queued','running','completed','failed')),
    items_found INT NOT NULL DEFAULT 0,
    items_new INT NOT NULL DEFAULT 0,
    failure_reason TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE news_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES news_sources(id) ON DELETE RESTRICT,
    canonical_url TEXT NOT NULL,
    url_hash CHAR(64) UNIQUE NOT NULL,
    title TEXT NOT NULL,
    content_hash CHAR(64) NOT NULL,
    content TEXT NOT NULL,
    published_at TIMESTAMPTZ NOT NULL,
    related_coins TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(source_id, content_hash)
);
CREATE INDEX idx_news_time ON news_items(published_at DESC);

CREATE TABLE sentiment_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    news_item_id UUID NOT NULL REFERENCES news_items(id) ON DELETE CASCADE,
    label VARCHAR(16) NOT NULL CHECK (label IN ('POSITIVE','NEUTRAL','NEGATIVE')),
    score NUMERIC(8,6) NOT NULL CHECK (score BETWEEN -1 AND 1),
    model VARCHAR(80) NOT NULL,
    model_version VARCHAR(80) NOT NULL,
    analyzed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(news_item_id, model, model_version)
);

CREATE TABLE event_consumptions (
    event_id UUID NOT NULL REFERENCES domain_events(event_id) ON DELETE CASCADE,
    consumer_id VARCHAR(64) NOT NULL,
    consumed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY(event_id, consumer_id)
);

INSERT INTO score_policies(version, min_trades, weights, formula, is_active)
VALUES (
    'v1', 1,
    '{"total_return_pct":0.40,"win_rate_pct":0.20,"max_drawdown_pct":0.20,"profit_factor":0.10,"sharpe_ratio":0.10}',
    'weighted normalized metrics', TRUE
);

CREATE VIEW read.candles_v1 AS SELECT * FROM candles;
CREATE VIEW read.experiment_summary_v1 AS
SELECT e.id AS experiment_id, e.owner_id, e.candidate_hash, e.market_dataset_id,
       d.dataset_version, d.provider, d.symbol, d.timeframe, e.created_at,
       r.id AS run_id, COALESCE(r.status, 'queued'::run_status) AS status,
       r.started_at, r.finished_at, r.candles_read, r.signals_count, r.error_code,
       v.strategy_id, v.version AS strategy_version, e.evaluator_version
FROM experiments e
JOIN market_datasets d ON d.id = e.market_dataset_id
JOIN strategy_versions v ON v.id = e.strategy_version_id
LEFT JOIN backtest_runs r ON r.experiment_id = e.id;

CREATE VIEW read.trades_v1 AS
SELECT r.experiment_id, t.* FROM trades t JOIN backtest_runs r ON r.id = t.backtest_run_id;
CREATE VIEW read.run_signals_v1 AS
SELECT r.experiment_id, s.* FROM run_signals s JOIN backtest_runs r ON r.id = s.backtest_run_id;
CREATE VIEW read.equity_v1 AS
SELECT r.experiment_id, e.* FROM equity_points e JOIN backtest_runs r ON r.id = e.backtest_run_id;
CREATE VIEW read.search_run_v1 AS SELECT * FROM search_runs;
CREATE VIEW read.news_v1 AS
SELECT n.*, s.source_key, s.display_name,
       sr.label AS sentiment_label, sr.score AS sentiment_score,
       sr.model AS sentiment_model, sr.model_version AS sentiment_model_version,
       sr.analyzed_at AS sentiment_analyzed_at
FROM news_items n
JOIN news_sources s ON s.id = n.source_id
LEFT JOIN LATERAL (
    SELECT * FROM sentiment_results candidate
    WHERE candidate.news_item_id = n.id
    ORDER BY candidate.analyzed_at DESC LIMIT 1
) sr ON TRUE;

CREATE VIEW read.leaderboard_v1 AS
SELECT l.id AS entry_id, l.score, l.score_policy_version, l.observed_at,
       l.market_dataset_id, d.dataset_version, d.provider, d.symbol, d.timeframe,
       e.id AS evaluation_id, e.total_return_pct, e.win_rate_pct,
       e.max_drawdown_pct, e.trade_count, e.profit_factor, e.sharpe_ratio,
       x.id AS experiment_id, x.candidate_hash,
       v.strategy_id, v.version AS strategy_version
FROM leaderboard_entries l
JOIN evaluations e ON e.id = l.evaluation_id
JOIN backtest_runs r ON r.id = e.backtest_run_id
JOIN experiments x ON x.id = r.experiment_id
JOIN strategy_versions v ON v.id = x.strategy_version_id
JOIN market_datasets d ON d.id = l.market_dataset_id;
