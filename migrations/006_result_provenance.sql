ALTER TABLE backtest_runs
    ADD COLUMN result_hash CHAR(64),
    ADD CONSTRAINT backtest_runs_result_hash_format
        CHECK (result_hash IS NULL OR result_hash ~ '^[0-9a-f]{64}$'),
    ADD CONSTRAINT backtest_runs_completed_hash
        CHECK (status <> 'completed' OR result_hash IS NOT NULL) NOT VALID;

CREATE INDEX idx_backtest_runs_result_hash
    ON backtest_runs(result_hash) WHERE result_hash IS NOT NULL;

DROP VIEW read.experiment_summary_v1;
CREATE VIEW read.experiment_summary_v1 AS
SELECT e.id AS experiment_id, e.owner_id, e.candidate_hash, e.market_dataset_id,
       d.dataset_version, d.provider, d.symbol, d.timeframe, d.content_hash,
       d.bbo_content_hash, e.created_at, r.id AS run_id,
       COALESCE(r.status, 'queued'::run_status) AS status,
       r.started_at, r.finished_at, r.candles_read, r.signals_count, r.error_code,
       r.result_hash, v.strategy_id, v.version AS strategy_version,
       v.code_fingerprint, e.evaluator_version
FROM experiments e
JOIN market_datasets d ON d.id = e.market_dataset_id
JOIN strategy_versions v ON v.id = e.strategy_version_id
LEFT JOIN backtest_runs r ON r.experiment_id = e.id;

GRANT SELECT ON read.experiment_summary_v1 TO api_runtime,api_reader;
