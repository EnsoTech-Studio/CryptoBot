-- Exact trade-cost provenance. New runs compute these facts from executable
-- bid/ask; legacy rows retain their recorded net PnL with unknown spread = 0.
ALTER TABLE trades
    ADD COLUMN entry_notional NUMERIC(24,8) NOT NULL DEFAULT 0,
    ADD COLUMN exit_notional NUMERIC(24,8),
    ADD COLUMN spread_cost NUMERIC(24,8) NOT NULL DEFAULT 0,
    ADD COLUMN gross_pnl NUMERIC(24,8),
    ADD COLUMN net_pnl NUMERIC(24,8);

ALTER TABLE trades DISABLE TRIGGER trades_immutable;
UPDATE trades
SET entry_notional=entry_price*quantity,
    exit_notional=CASE WHEN exit_price IS NULL THEN NULL ELSE exit_price*quantity END,
    gross_pnl=CASE WHEN pnl_absolute IS NULL THEN NULL ELSE pnl_absolute+fee_paid+slippage_cost END,
    net_pnl=pnl_absolute;
ALTER TABLE trades ENABLE TRIGGER trades_immutable;

GRANT SELECT, INSERT ON trades TO research_runtime;
