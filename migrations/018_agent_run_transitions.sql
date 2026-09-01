-- Immutable workflow evidence for deterministic authoring state transitions.
CREATE TABLE agent_run_transitions (
    agent_run_id UUID NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
    sequence_no  SMALLINT NOT NULL CHECK (sequence_no >= 0),
    state        VARCHAR(32) NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (agent_run_id, sequence_no)
);

GRANT SELECT, INSERT ON agent_run_transitions TO research_runtime;
