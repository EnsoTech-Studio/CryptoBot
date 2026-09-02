-- Durable partitions and assessment facts for SearchRun generator_id='discovery'.
-- Ordinary search keeps its one-candidate/one-experiment contract unchanged.

ALTER TABLE search_runs
    ADD COLUMN discovery_state JSONB;

ALTER TABLE experiments
    DROP CONSTRAINT IF EXISTS experiments_search_candidate_id_key;

CREATE TABLE discovery_candidate_experiments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    search_candidate_id UUID NOT NULL REFERENCES search_candidates(id) ON DELETE CASCADE,
    partition VARCHAR(16) NOT NULL CHECK (partition IN ('train','validation','test')),
    validation_ordinal SMALLINT,
    experiment_id UUID NOT NULL UNIQUE REFERENCES experiments(id) ON DELETE RESTRICT,
    range_from TIMESTAMPTZ NOT NULL,
    range_to TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (range_to > range_from),
    CHECK ((partition='validation') = (validation_ordinal IS NOT NULL)),
    UNIQUE(search_candidate_id, partition, validation_ordinal)
);

CREATE TABLE discovery_assessments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    search_candidate_id UUID NOT NULL UNIQUE REFERENCES search_candidates(id) ON DELETE CASCADE,
    train_evaluation_id UUID REFERENCES evaluations(id) ON DELETE RESTRICT,
    validation_evaluation_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    score NUMERIC(14,6),
    accepted BOOLEAN NOT NULL,
    rejection_reason VARCHAR(80),
    facts JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_discovery_partitions_experiment ON discovery_candidate_experiments(experiment_id);
CREATE INDEX idx_discovery_assessments_candidate ON discovery_assessments(search_candidate_id);

GRANT SELECT,INSERT,UPDATE ON discovery_candidate_experiments,discovery_assessments TO research_runtime;
