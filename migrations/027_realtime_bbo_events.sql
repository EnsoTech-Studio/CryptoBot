-- Operational BBO history. Immutable market_dataset_bbo remains reserved for
-- frozen backtest snapshots; this table stores normalized live bookTicker data.
CREATE TABLE bbo_events (
    provider        VARCHAR(24) NOT NULL,
    symbol          VARCHAR(24) NOT NULL,
    event_time      TIMESTAMPTZ NOT NULL,
    source_sequence BIGINT NOT NULL,
    bid             NUMERIC(24,8) NOT NULL,
    bid_qty         NUMERIC(30,8) NOT NULL,
    ask             NUMERIC(24,8) NOT NULL,
    ask_qty         NUMERIC(30,8) NOT NULL,
    update_id       BIGINT,
    PRIMARY KEY (provider, symbol, event_time, source_sequence),
    FOREIGN KEY (provider, symbol) REFERENCES market_pairs(provider, symbol),
    CHECK (source_sequence > 0),
    CHECK (bid > 0 AND ask > 0 AND bid <= ask),
    CHECK (bid_qty >= 0 AND ask_qty >= 0)
);

CREATE INDEX idx_bbo_events_range
    ON bbo_events(provider, symbol, event_time DESC);

GRANT SELECT, INSERT ON bbo_events TO api_runtime;
GRANT SELECT ON bbo_events TO research_runtime, api_reader;
