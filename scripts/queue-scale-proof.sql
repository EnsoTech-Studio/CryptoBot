\set ON_ERROR_STOP on
\timing on

-- Representative 100k-job proof for the production claim query. Everything
-- is rolled back; only query-plan/timing output leaves the session.
BEGIN;

INSERT INTO users(email,password_hash,display_name,role)
VALUES ('queue-scale-proof@local','not-a-login','Queue Scale Proof','RESEARCHER');

INSERT INTO user_quotas(user_id,max_concurrent_runs,max_candidates_per_run)
SELECT id,32,500 FROM users WHERE email='queue-scale-proof@local';

INSERT INTO strategy_definitions(strategy_id,display_name,family,is_composite)
VALUES ('scale-proof','Scale proof','trend',FALSE)
ON CONFLICT(strategy_id) DO NOTHING;

INSERT INTO strategy_versions(
    strategy_id,version,parameters_schema,default_params,input_requirements,
    overlay_types,code_fingerprint
)
VALUES ('scale-proof','v1','{}','{}','[]','[]',repeat('a',64))
ON CONFLICT(strategy_id,version) DO NOTHING;

INSERT INTO market_pairs(symbol,base,quote,provider,is_active)
VALUES ('SCALEUSDT','SCALE','USDT','scale-proof',TRUE)
ON CONFLICT(symbol,provider) DO NOTHING;

INSERT INTO market_datasets(
    dataset_version,provider,symbol,timeframe,range_from,range_to,revision_no,
    candle_count,content_hash,bbo_content_hash
)
VALUES (
    'queue-scale-proof-v1','scale-proof','SCALEUSDT','1m',
    '2026-01-01T00:00:00Z','2026-01-01T00:01:00Z',1,1,repeat('b',64),repeat('c',64)
);

INSERT INTO experiments(
    owner_id,strategy_version_id,candidate_definition,candidate_hash,
    market_dataset_id,bbo_dataset_hash,evaluator_version,correlation_id
)
SELECT
    user_row.id,
    strategy_row.id,
    jsonb_build_object('strategy_id','scale-proof','version','v1','ordinal',series.n),
    lpad(to_hex(series.n),64,'0'),
    dataset_row.id,
    dataset_row.bbo_content_hash,
    'v1',
    'queue-scale-proof'
FROM generate_series(1,100000) AS series(n)
CROSS JOIN LATERAL (
    SELECT id FROM users WHERE email='queue-scale-proof@local'
) AS user_row
CROSS JOIN LATERAL (
    SELECT id FROM strategy_versions WHERE strategy_id='scale-proof' AND version='v1'
) AS strategy_row
CROSS JOIN LATERAL (
    SELECT id,bbo_content_hash FROM market_datasets
    WHERE dataset_version='queue-scale-proof-v1'
) AS dataset_row;

INSERT INTO backtest_jobs(experiment_id,priority)
SELECT id,100 FROM experiments
WHERE owner_id=(SELECT id FROM users WHERE email='queue-scale-proof@local');

ANALYZE experiments;
ANALYZE backtest_jobs;

EXPLAIN (ANALYZE,BUFFERS)
WITH raw_candidates AS MATERIALIZED (
    SELECT queued.id,queued.priority,queued.enqueued_at
    FROM (
        (
            SELECT j.id,j.priority,j.enqueued_at
            FROM backtest_jobs j
            WHERE j.status='queued'
            ORDER BY j.priority,j.enqueued_at
            LIMIT 256
        )
        UNION ALL
        (
            SELECT j.id,j.priority,j.enqueued_at
            FROM backtest_jobs j
            WHERE j.status='leased' AND j.lease_expires_at<now()
            ORDER BY j.lease_expires_at,j.priority,j.enqueued_at
            LIMIT 256
        )
    ) AS queued
    ORDER BY queued.priority,queued.enqueued_at
    LIMIT 256
),
candidate AS (
    SELECT j.id,e.correlation_id
    FROM raw_candidates raw
    JOIN backtest_jobs j ON j.id=raw.id
    JOIN experiments e ON e.id=j.experiment_id
    JOIN users u ON u.id=e.owner_id AND u.is_active
    LEFT JOIN user_quotas q ON q.user_id=u.id
    LEFT JOIN search_candidates c ON c.id=e.search_candidate_id
    LEFT JOIN search_runs s ON s.id=c.search_run_id
    WHERE (s.id IS NULL OR s.status='running')
      AND (
          SELECT count(*) FROM backtest_jobs active_job
          JOIN experiments active_experiment
            ON active_experiment.id=active_job.experiment_id
          WHERE active_experiment.owner_id=e.owner_id
            AND active_job.status='leased'
            AND active_job.lease_expires_at>=now()
      ) < COALESCE(q.max_concurrent_runs,2)
      AND pg_try_advisory_xact_lock(hashtextextended(e.owner_id::text,1))
    ORDER BY j.priority,j.enqueued_at
    FOR UPDATE OF j SKIP LOCKED
    LIMIT 1
)
UPDATE backtest_jobs j
SET status='leased',attempt=j.attempt+1,leased_by='scale-proof',
    lease_token=gen_random_uuid(),lease_expires_at=now()+interval '120 seconds'
FROM candidate WHERE j.id=candidate.id;

ROLLBACK;

-- Restore planner statistics after the rolled-back load.
ANALYZE experiments;
ANALYZE backtest_jobs;
