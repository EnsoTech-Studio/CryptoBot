-- Approved DSL strategies are executable data, never arbitrary Python.
CREATE TABLE strategy_runtime_specs (
    strategy_id   VARCHAR(48) NOT NULL,
    version       VARCHAR(24) NOT NULL,
    spec_json     JSONB NOT NULL,
    artifact_hash CHAR(64) NOT NULL,
    published_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (strategy_id, version),
    FOREIGN KEY (strategy_id, version) REFERENCES strategy_versions(strategy_id, version)
);

GRANT SELECT, INSERT ON strategy_runtime_specs TO research_runtime;
