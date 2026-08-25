-- Complete durable search stop state and cross-service request correlation.

ALTER TABLE experiments
    ADD COLUMN correlation_id VARCHAR(128);

ALTER TABLE search_runs
    ADD COLUMN generator_exhausted BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN correlation_id VARCHAR(128);

ALTER TABLE search_runs
    ADD CONSTRAINT search_stop_conditions_object
        CHECK (jsonb_typeof(stop_conditions) = 'object'),
    ADD CONSTRAINT search_stop_conditions_known_keys
        CHECK (
            stop_conditions - ARRAY[
                'max_candidates', 'max_duration_sec', 'max_non_improving',
                'max_failure_rate'
            ] = '{}'::jsonb
        ),
    ADD CONSTRAINT search_stop_conditions_present
        CHECK (
            stop_conditions ? 'max_candidates'
            OR stop_conditions ? 'max_duration_sec'
            OR stop_conditions ? 'max_non_improving'
            OR stop_conditions ? 'max_failure_rate'
        ),
    ADD CONSTRAINT search_max_candidates_valid
        CHECK (
            CASE WHEN NOT (stop_conditions ? 'max_candidates') THEN TRUE
            WHEN jsonb_typeof(stop_conditions->'max_candidates') <> 'number' THEN FALSE
            ELSE (stop_conditions->>'max_candidates')::numeric > 0
                 AND (stop_conditions->>'max_candidates')::numeric <= 500
                 AND trunc((stop_conditions->>'max_candidates')::numeric)
                     = (stop_conditions->>'max_candidates')::numeric
            END
        ),
    ADD CONSTRAINT search_max_duration_valid
        CHECK (
            CASE WHEN NOT (stop_conditions ? 'max_duration_sec') THEN TRUE
            WHEN jsonb_typeof(stop_conditions->'max_duration_sec') <> 'number' THEN FALSE
            ELSE (stop_conditions->>'max_duration_sec')::numeric > 0
                 AND (stop_conditions->>'max_duration_sec')::numeric <= 86400
                 AND trunc((stop_conditions->>'max_duration_sec')::numeric)
                     = (stop_conditions->>'max_duration_sec')::numeric
            END
        ),
    ADD CONSTRAINT search_max_non_improving_valid
        CHECK (
            CASE WHEN NOT (stop_conditions ? 'max_non_improving') THEN TRUE
            WHEN jsonb_typeof(stop_conditions->'max_non_improving') <> 'number' THEN FALSE
            ELSE (stop_conditions->>'max_non_improving')::numeric > 0
                 AND (stop_conditions->>'max_non_improving')::numeric <= 500
                 AND trunc((stop_conditions->>'max_non_improving')::numeric)
                     = (stop_conditions->>'max_non_improving')::numeric
            END
        ),
    ADD CONSTRAINT search_max_failure_rate_valid
        CHECK (
            CASE WHEN NOT (stop_conditions ? 'max_failure_rate') THEN TRUE
            WHEN jsonb_typeof(stop_conditions->'max_failure_rate') <> 'number' THEN FALSE
            ELSE (stop_conditions->>'max_failure_rate')::numeric > 0
                 AND (stop_conditions->>'max_failure_rate')::numeric <= 1
            END
        );

CREATE INDEX idx_search_runs_running_stop
    ON search_runs(updated_at, created_at)
    WHERE status = 'running';
