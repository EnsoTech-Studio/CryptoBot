-- DSL-first strategy authoring. Generated code is evidence for review only;
-- approval is bound to immutable hashes and never hot-loads arbitrary Python.
CREATE TABLE strategy_drafts (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id          UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_type       VARCHAR(24) NOT NULL CHECK (source_type IN ('text','approved_url','dsl')),
    source_ref        TEXT NOT NULL,
    source_hash       CHAR(64) NOT NULL,
    mode              VARCHAR(24) NOT NULL CHECK (mode IN ('dsl','custom_python')),
    name_hint         VARCHAR(120),
    current_revision  INT NOT NULL DEFAULT 0 CHECK (current_revision >= 0),
    status            VARCHAR(32) NOT NULL DEFAULT 'DRAFT_CREATED'
                      CHECK (status IN (
                          'DRAFT_CREATED','SOURCE_READY','REVIEW_REQUIRED','APPROVED',
                          'REJECTED','FAILED'
                      )),
    idempotency_key   VARCHAR(120),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (owner_id, idempotency_key)
);
CREATE INDEX idx_strategy_drafts_owner ON strategy_drafts(owner_id, updated_at DESC);

CREATE TABLE strategy_draft_revisions (
    draft_id          UUID NOT NULL REFERENCES strategy_drafts(id) ON DELETE CASCADE,
    revision          INT NOT NULL CHECK (revision > 0),
    spec_json         JSONB NOT NULL,
    spec_hash         CHAR(64) NOT NULL,
    created_by        VARCHAR(24) NOT NULL CHECK (created_by IN ('designer','user')),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (draft_id, revision),
    UNIQUE (draft_id, spec_hash)
);

CREATE TABLE agent_runs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    draft_id            UUID NOT NULL REFERENCES strategy_drafts(id) ON DELETE CASCADE,
    agent_type          VARCHAR(32) NOT NULL,
    state               VARCHAR(24) NOT NULL CHECK (state IN ('completed','failed','review_required')),
    model               VARCHAR(120) NOT NULL,
    model_version       VARCHAR(120) NOT NULL,
    prompt_hash         CHAR(64) NOT NULL,
    tool_policy_version VARCHAR(48) NOT NULL,
    attempts_used       SMALLINT NOT NULL DEFAULT 1 CHECK (attempts_used BETWEEN 1 AND 3),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE strategy_artifacts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    draft_id        UUID NOT NULL REFERENCES strategy_drafts(id) ON DELETE CASCADE,
    revision        INT NOT NULL,
    language        VARCHAR(24) NOT NULL CHECK (language IN ('python','dsl')),
    source_text     TEXT NOT NULL,
    artifact_hash   CHAR(64) NOT NULL UNIQUE,
    compiler_version VARCHAR(48) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (draft_id, revision) REFERENCES strategy_draft_revisions(draft_id, revision)
);

CREATE TABLE sandbox_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id     UUID NOT NULL REFERENCES strategy_artifacts(id) ON DELETE CASCADE,
    policy_version  VARCHAR(48) NOT NULL,
    fixture_version VARCHAR(48) NOT NULL,
    status          VARCHAR(24) NOT NULL CHECK (status IN ('passed','failed','blocked')),
    report_json     JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE strategy_approvals (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    draft_id            UUID NOT NULL REFERENCES strategy_drafts(id) ON DELETE CASCADE,
    reviewer_id         UUID NOT NULL REFERENCES users(id),
    revision            INT NOT NULL,
    spec_hash           CHAR(64) NOT NULL,
    artifact_hash       CHAR(64) NOT NULL,
    sandbox_report_hash CHAR(64) NOT NULL,
    decision            VARCHAR(16) NOT NULL CHECK (decision IN ('approve','reject')),
    reason              VARCHAR(2_000) NOT NULL,
    idempotency_key     VARCHAR(120),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (draft_id, revision, spec_hash, artifact_hash, sandbox_report_hash)
);
CREATE UNIQUE INDEX idx_strategy_approvals_idempotency
    ON strategy_approvals(draft_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

GRANT SELECT, INSERT, UPDATE ON strategy_drafts, strategy_draft_revisions,
    agent_runs, strategy_artifacts, sandbox_runs, strategy_approvals TO research_runtime;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO research_runtime;
