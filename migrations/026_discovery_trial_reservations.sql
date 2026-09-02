-- Reserve one bounded train + three validation jobs before discovery trial admission.
-- Final sealed test is created only after an accepted candidate and is tracked
-- separately by search_runs.discovery_state.

CREATE TABLE discovery_trial_reservations (
    search_candidate_id UUID PRIMARY KEY REFERENCES search_candidates(id) ON DELETE CASCADE,
    reserved_jobs SMALLINT NOT NULL DEFAULT 4 CHECK (reserved_jobs = 4),
    consumed_jobs SMALLINT NOT NULL DEFAULT 0 CHECK (consumed_jobs BETWEEN 0 AND 4),
    released_jobs SMALLINT NOT NULL DEFAULT 0 CHECK (released_jobs BETWEEN 0 AND 4),
    status VARCHAR(16) NOT NULL DEFAULT 'reserved'
        CHECK (status IN ('reserved','consumed','released')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_discovery_trial_reservations_status
    ON discovery_trial_reservations(status);

GRANT SELECT,INSERT,UPDATE ON discovery_trial_reservations TO research_runtime;
