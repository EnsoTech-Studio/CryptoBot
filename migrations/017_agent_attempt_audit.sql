-- Audit each bounded designer attempt without retaining raw prompts or model output.
CREATE TABLE agent_attempts (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_run_id UUID NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
    attempt_no   SMALLINT NOT NULL CHECK (attempt_no BETWEEN 1 AND 3),
    stage        VARCHAR(32) NOT NULL CHECK (stage IN ('spec_generation')),
    status       VARCHAR(16) NOT NULL CHECK (status IN ('passed','failed')),
    input_hash   CHAR(64) NOT NULL,
    output_hash  CHAR(64),
    error_code   VARCHAR(64),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (agent_run_id, attempt_no)
);

CREATE INDEX idx_agent_attempts_run ON agent_attempts(agent_run_id, attempt_no);

GRANT SELECT, INSERT ON agent_attempts TO research_runtime;
