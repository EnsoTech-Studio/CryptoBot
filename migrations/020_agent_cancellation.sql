-- Cancellation is a persisted terminal intent. A worker holding an old lease
-- cannot finalize a draft after this state has committed.
ALTER TABLE strategy_drafts DROP CONSTRAINT strategy_drafts_status_check;
ALTER TABLE strategy_drafts ADD CONSTRAINT strategy_drafts_status_check CHECK (status IN (
    'DRAFT_CREATED','SOURCE_READY','SPEC_GENERATING','SPEC_VALIDATING',
    'CODE_GENERATING','POLICY_CHECKING','SANDBOX_TESTING','REPAIRING',
    'REVIEW_REQUIRED','APPROVED','REJECTED','FAILED','CANCELLED'
));

ALTER TABLE agent_runs DROP CONSTRAINT agent_runs_state_check;
ALTER TABLE agent_runs ADD CONSTRAINT agent_runs_state_check CHECK (state IN (
    'DRAFT_CREATED','SOURCE_READY','SPEC_GENERATING','SPEC_VALIDATING',
    'CODE_GENERATING','POLICY_CHECKING','SANDBOX_TESTING','REPAIRING',
    'REVIEW_REQUIRED','APPROVED','REJECTED','FAILED','PUBLISHED','CANCELLED'
));
ALTER TABLE agent_runs ADD COLUMN cancelled_at TIMESTAMPTZ;
