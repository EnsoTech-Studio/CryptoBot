-- Durable authoring commands: the HTTP boundary creates immutable intent;
-- a Python worker owns model/tool execution and may safely reclaim expired work.
ALTER TABLE strategy_drafts DROP CONSTRAINT strategy_drafts_status_check;
ALTER TABLE strategy_drafts ADD CONSTRAINT strategy_drafts_status_check CHECK (status IN (
    'DRAFT_CREATED','SOURCE_READY','SPEC_GENERATING','SPEC_VALIDATING',
    'CODE_GENERATING','POLICY_CHECKING','SANDBOX_TESTING','REPAIRING',
    'REVIEW_REQUIRED','APPROVED','REJECTED','FAILED'
));

ALTER TABLE agent_runs ALTER COLUMN state TYPE VARCHAR(32);
UPDATE agent_runs SET state=upper(state);
ALTER TABLE agent_runs DROP CONSTRAINT agent_runs_state_check;
ALTER TABLE agent_runs ADD CONSTRAINT agent_runs_state_check CHECK (state IN (
    'DRAFT_CREATED','SOURCE_READY','SPEC_GENERATING','SPEC_VALIDATING',
    'CODE_GENERATING','POLICY_CHECKING','SANDBOX_TESTING','REPAIRING',
    'REVIEW_REQUIRED','APPROVED','REJECTED','FAILED','PUBLISHED'
));
ALTER TABLE agent_runs DROP CONSTRAINT agent_runs_attempts_used_check;
ALTER TABLE agent_runs ADD CONSTRAINT agent_runs_attempts_used_check
    CHECK (attempts_used BETWEEN 0 AND 3);
ALTER TABLE agent_runs ADD COLUMN aggregate_version INTEGER NOT NULL DEFAULT 0
    CHECK (aggregate_version >= 0);
ALTER TABLE agent_runs ADD COLUMN cancellation_requested BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE agent_runs ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE TABLE agent_jobs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_run_id     UUID NOT NULL UNIQUE REFERENCES agent_runs(id) ON DELETE CASCADE,
    payload_json     JSONB NOT NULL,
    status           VARCHAR(16) NOT NULL DEFAULT 'queued'
                     CHECK (status IN ('queued','leased','completed','failed','cancelled')),
    enqueued_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    available_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    leased_by        VARCHAR(120),
    lease_token      UUID,
    lease_expires_at TIMESTAMPTZ,
    attempts         SMALLINT NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 3),
    max_attempts     SMALLINT NOT NULL DEFAULT 3 CHECK (max_attempts BETWEEN 1 AND 3),
    last_error_code  VARCHAR(64),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_agent_jobs_claim ON agent_jobs(status, available_at, enqueued_at);
CREATE INDEX idx_agent_jobs_lease ON agent_jobs(lease_expires_at) WHERE status='leased';

GRANT SELECT, INSERT, UPDATE ON agent_jobs TO research_runtime;
