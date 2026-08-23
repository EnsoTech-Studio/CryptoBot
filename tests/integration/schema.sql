-- Blueprint design.md DDL (queue-path subset) for the Python backtest worker.
-- Extracted verbatim from blueprint/design.md §8 except market_dataset_bbo,
-- which design.md does not define (only experiments.bbo_dataset_hash exists);
-- it is added here with the columns the dispatcher's load_dataset expects.
CREATE EXTENSION IF NOT EXISTS "pgcrypto";     -- gen_random_uuid()

CREATE TYPE timeframe_enum AS ENUM ('1m','5m','15m','30m','1h','2h','4h','1d');
CREATE TYPE signal_enum    AS ENUM ('BUY','SELL','HOLD');
CREATE TYPE run_status     AS ENUM ('queued','running','completed','failed','cancelled');
CREATE TYPE job_status     AS ENUM ('queued','leased','completed','failed','cancelled');
CREATE TYPE trade_side     AS ENUM ('LONG','SHORT');
CREATE TYPE fill_policy_enum AS ENUM ('bbo_limit');
CREATE TYPE position_policy_enum AS ENUM ('one_net_position');
CREATE TYPE open_position_policy_enum AS ENUM ('last_executable_bbo');
CREATE TYPE event_dispatch_status AS ENUM ('pending','claimed','delivered','dead');

CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    display_name  VARCHAR(120) NOT NULL,
    role          VARCHAR(24)  NOT NULL
                  CHECK (role IN ('RESEARCHER','OPERATOR','ADMIN')),
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE market_pairs (
    id       SMALLSERIAL PRIMARY KEY,
    symbol   VARCHAR(24) NOT NULL,
    base     VARCHAR(12) NOT NULL,
    quote    VARCHAR(12) NOT NULL,
    provider VARCHAR(24) NOT NULL DEFAULT 'binance_usdm',
    is_active BOOLEAN    NOT NULL DEFAULT TRUE,
    UNIQUE (provider, symbol)
);

CREATE TABLE market_datasets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_version VARCHAR(120) UNIQUE NOT NULL,
    provider        VARCHAR(24)    NOT NULL,
    symbol          VARCHAR(24)    NOT NULL,
    timeframe       timeframe_enum NOT NULL,
    range_from      TIMESTAMPTZ    NOT NULL,
    range_to        TIMESTAMPTZ    NOT NULL,
    revision_no     SMALLINT       NOT NULL DEFAULT 1,
    candle_count    INT            NOT NULL,
    content_hash    CHAR(64)       NOT NULL,
    created_at      TIMESTAMPTZ    NOT NULL DEFAULT now(),
    FOREIGN KEY (provider, symbol) REFERENCES market_pairs(provider, symbol),
    CHECK (range_to > range_from),
    CHECK (revision_no > 0),
    CHECK (candle_count > 0),
    UNIQUE (provider, symbol, timeframe, range_from, range_to, revision_no)
);
CREATE INDEX idx_datasets_lookup
    ON market_datasets(provider, symbol, timeframe, range_from, range_to);

CREATE TABLE market_dataset_candles (
    market_dataset_id UUID NOT NULL REFERENCES market_datasets(id) ON DELETE RESTRICT,
    open_time         TIMESTAMPTZ    NOT NULL,
    close_time        TIMESTAMPTZ    NOT NULL,
    open              NUMERIC(24,8)  NOT NULL,
    high              NUMERIC(24,8)  NOT NULL,
    low               NUMERIC(24,8)  NOT NULL,
    close             NUMERIC(24,8)  NOT NULL,
    volume            NUMERIC(30,8)  NOT NULL,
    trade_count       INT,
    PRIMARY KEY (market_dataset_id, open_time),
    CHECK (high >= low),
    CHECK (high >= open AND high >= close),
    CHECK (low <= open AND low <= close),
    CHECK (volume >= 0),
    CHECK (close_time > open_time)
);
CREATE INDEX idx_dataset_candles_range
    ON market_dataset_candles(market_dataset_id, open_time);

-- Not in design.md; the dispatcher reads the frozen BBO replay from it.
CREATE TABLE market_dataset_bbo (
    market_dataset_id UUID NOT NULL REFERENCES market_datasets(id) ON DELETE RESTRICT,
    event_time        TIMESTAMPTZ   NOT NULL,
    source_sequence   BIGINT        NOT NULL,
    bid               NUMERIC(24,8) NOT NULL,
    bid_qty           NUMERIC(30,8) NOT NULL,
    ask               NUMERIC(24,8) NOT NULL,
    ask_qty           NUMERIC(30,8) NOT NULL,
    update_id         BIGINT,
    PRIMARY KEY (market_dataset_id, event_time, source_sequence)
);
CREATE INDEX idx_dataset_bbo_range ON market_dataset_bbo(market_dataset_id, event_time);

CREATE TABLE strategy_definitions (
    strategy_id  VARCHAR(48) PRIMARY KEY,
    display_name VARCHAR(120) NOT NULL,
    family       VARCHAR(24),
    description  TEXT,
    is_composite BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        (is_composite = TRUE  AND family IS NULL)
        OR
        (is_composite = FALSE AND family IS NOT NULL
         AND family IN ('trend','momentum','volatility','structure','information'))
    )
);

CREATE TABLE strategy_versions (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id       VARCHAR(48) NOT NULL REFERENCES strategy_definitions(strategy_id),
    version           VARCHAR(24) NOT NULL,
    parameters_schema JSONB       NOT NULL,
    default_params    JSONB       NOT NULL,
    input_requirements JSONB      NOT NULL,
    overlay_types     JSONB       NOT NULL,
    code_fingerprint  CHAR(64)    NOT NULL,
    registered_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (strategy_id, version)
);

CREATE TABLE experiments (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id             UUID NOT NULL REFERENCES users(id),
    strategy_version_id  UUID NOT NULL REFERENCES strategy_versions(id),
    candidate_definition JSONB NOT NULL,
    candidate_hash       CHAR(64) NOT NULL,
    market_dataset_id    UUID NOT NULL REFERENCES market_datasets(id),
    bbo_dataset_hash     CHAR(64),
    initial_equity       NUMERIC(20,8) NOT NULL DEFAULT 100,
    fixed_notional       NUMERIC(20,8) NOT NULL DEFAULT 10,
    leverage             NUMERIC(12,4) NOT NULL DEFAULT 1,
    fee_bps              SMALLINT NOT NULL DEFAULT 10,
    slippage_bps         SMALLINT NOT NULL DEFAULT 0,
    fill_policy          fill_policy_enum     NOT NULL DEFAULT 'bbo_limit',
    position_policy      position_policy_enum NOT NULL DEFAULT 'one_net_position',
    open_position_at_end open_position_policy_enum NOT NULL DEFAULT 'last_executable_bbo',
    stop_loss_pct        NUMERIC(6,3),
    take_profit_pct      NUMERIC(6,3),
    intrabar_priority    VARCHAR(20) NOT NULL DEFAULT 'stop_loss_first'
                         CHECK (intrabar_priority IN ('stop_loss_first','take_profit_first')),
    evaluator_version    VARCHAR(24) NOT NULL,
    search_candidate_id  UUID UNIQUE,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (fee_bps >= 0 AND slippage_bps >= 0),
    CHECK (initial_equity > 0 AND fixed_notional > 0 AND leverage > 0),
    CHECK (stop_loss_pct   IS NULL OR (stop_loss_pct   > 0 AND stop_loss_pct   < 100)),
    CHECK (take_profit_pct IS NULL OR take_profit_pct > 0)
);
CREATE INDEX idx_experiments_owner ON experiments(owner_id, created_at DESC);
CREATE INDEX idx_experiments_hash  ON experiments(candidate_hash, market_dataset_id);

CREATE TABLE backtest_jobs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id    UUID UNIQUE NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    status           job_status NOT NULL DEFAULT 'queued',
    priority         SMALLINT NOT NULL DEFAULT 100,
    attempt          SMALLINT NOT NULL DEFAULT 0,
    max_attempts     SMALLINT NOT NULL DEFAULT 3,
    leased_by        VARCHAR(64),
    lease_token      UUID,
    lease_expires_at TIMESTAMPTZ,
    last_error       TEXT,
    enqueued_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at     TIMESTAMPTZ,
    CHECK (status <> 'leased'
           OR (leased_by IS NOT NULL AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL))
);
CREATE INDEX idx_jobs_claimable ON backtest_jobs(priority, enqueued_at)
    WHERE status = 'queued';
CREATE INDEX idx_jobs_expired_lease ON backtest_jobs(lease_expires_at)
    WHERE status = 'leased';

CREATE TABLE backtest_runs (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id  UUID UNIQUE NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    status         run_status NOT NULL DEFAULT 'queued',
    worker_id      VARCHAR(64),
    lease_token    UUID,
    attempt        SMALLINT NOT NULL DEFAULT 0,
    candles_read   INT,
    signals_count  INT,
    duration_ms    INT,
    error_code     VARCHAR(48),
    error_detail   TEXT,
    started_at     TIMESTAMPTZ,
    finished_at    TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE trades (
    id               BIGSERIAL PRIMARY KEY,
    backtest_run_id  UUID NOT NULL REFERENCES backtest_runs(id) ON DELETE CASCADE,
    sequence_no      INT  NOT NULL,
    side             trade_side NOT NULL DEFAULT 'LONG',
    signal_t         TIMESTAMPTZ,
    entry_time       TIMESTAMPTZ NOT NULL,
    entry_price      NUMERIC(24,8) NOT NULL,
    exit_time        TIMESTAMPTZ,
    exit_price       NUMERIC(24,8),
    quantity         NUMERIC(24,8) NOT NULL,
    fee_paid         NUMERIC(24,8) NOT NULL DEFAULT 0,
    slippage_cost    NUMERIC(24,8) NOT NULL DEFAULT 0,
    pnl_absolute     NUMERIC(24,8),
    pnl_percent      NUMERIC(12,6),
    exit_reason      VARCHAR(32),
    sl_price         NUMERIC(24,8),
    tp_price         NUMERIC(24,8),
    UNIQUE (backtest_run_id, sequence_no),
    CHECK (exit_time IS NULL OR exit_time >= entry_time),
    CHECK (exit_reason IS NULL
           OR exit_reason IN ('signal','stop_loss','take_profit','end_of_sample')),
    CHECK (exit_time IS NULL
           OR (exit_price IS NOT NULL AND pnl_absolute IS NOT NULL
               AND pnl_percent IS NOT NULL AND exit_reason IS NOT NULL)),
    CHECK (exit_reason IS NULL OR exit_time IS NOT NULL),
    CHECK (exit_reason <> 'stop_loss'   OR sl_price IS NOT NULL),
    CHECK (exit_reason <> 'take_profit' OR tp_price IS NOT NULL)
);
CREATE INDEX idx_trades_run ON trades(backtest_run_id, sequence_no);

CREATE TABLE run_signals (
    id              BIGSERIAL PRIMARY KEY,
    backtest_run_id UUID NOT NULL REFERENCES backtest_runs(id) ON DELETE CASCADE,
    candle_time     TIMESTAMPTZ NOT NULL,
    signal          signal_enum NOT NULL,
    confidence      NUMERIC(6,4),
    child_signals   JSONB,
    UNIQUE (backtest_run_id, candle_time)
);

CREATE TABLE equity_points (
    backtest_run_id UUID NOT NULL REFERENCES backtest_runs(id) ON DELETE CASCADE,
    point_time      TIMESTAMPTZ NOT NULL,
    equity          NUMERIC(24,8) NOT NULL,
    drawdown_pct    NUMERIC(12,6),
    PRIMARY KEY (backtest_run_id, point_time)
);

CREATE TABLE evaluations (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    backtest_run_id   UUID NOT NULL REFERENCES backtest_runs(id) ON DELETE CASCADE,
    evaluator_version VARCHAR(24) NOT NULL,
    total_return_pct  NUMERIC(14,6) NOT NULL,
    win_rate_pct      NUMERIC(8,4)  NOT NULL,
    max_drawdown_pct  NUMERIC(10,6) NOT NULL,
    trade_count       INT      NOT NULL,
    open_trade_count  INT      NOT NULL DEFAULT 0,
    profit_factor     NUMERIC(12,6),
    sharpe_ratio      NUMERIC(12,6),
    avg_trade_pct     NUMERIC(12,6),
    computed_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (backtest_run_id, evaluator_version),
    CHECK (win_rate_pct BETWEEN 0 AND 100),
    CHECK (max_drawdown_pct <= 0),
    CHECK (trade_count >= 0),
    CHECK (open_trade_count >= 0)
);

CREATE TABLE domain_events (
    event_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type     VARCHAR(48) NOT NULL,
    schema_version SMALLINT NOT NULL DEFAULT 1,
    aggregate_type VARCHAR(32) NOT NULL,
    aggregate_id   UUID NOT NULL,
    correlation_id VARCHAR(64),
    payload        JSONB NOT NULL,
    occurred_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    dispatch_status  event_dispatch_status NOT NULL DEFAULT 'pending',
    attempt          SMALLINT NOT NULL DEFAULT 0,
    max_attempts     SMALLINT NOT NULL DEFAULT 5,
    claimed_by       VARCHAR(64),
    claim_expires_at TIMESTAMPTZ,
    next_attempt_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_error       TEXT,
    delivered_at     TIMESTAMPTZ,
    CHECK (dispatch_status <> 'delivered' OR delivered_at IS NOT NULL)
);
CREATE INDEX idx_events_aggregate  ON domain_events(aggregate_type, aggregate_id, occurred_at);
CREATE INDEX idx_events_dispatchable ON domain_events(next_attempt_at, occurred_at)
    WHERE dispatch_status = 'pending';
