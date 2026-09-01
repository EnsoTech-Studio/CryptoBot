-- Typed agent-tool audit keeps only canonical request/result fingerprints.
CREATE TABLE tool_invocations (
    agent_run_id UUID NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
    sequence_no  SMALLINT NOT NULL CHECK (sequence_no >= 0),
    role         VARCHAR(48) NOT NULL,
    tool_name    VARCHAR(96) NOT NULL,
    tool_version VARCHAR(24) NOT NULL,
    state        VARCHAR(32) NOT NULL,
    request_hash CHAR(64) NOT NULL,
    result_hash  CHAR(64) NOT NULL,
    status       VARCHAR(16) NOT NULL CHECK (status IN ('allowed','denied','failed')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (agent_run_id, sequence_no)
);
CREATE INDEX idx_tool_invocations_run ON tool_invocations(agent_run_id, sequence_no);
GRANT SELECT, INSERT ON tool_invocations TO research_runtime;
