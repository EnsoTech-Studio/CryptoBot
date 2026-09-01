import assert from "node:assert/strict";
import test from "node:test";

import { draftIssues, normalizeWeights, createDraft } from "./discovery";
import { backtestIssues, createBacktestDraft, defaultBacktestStrategyId, defaultBacktestTimeframe, deriveKpis, draftToExecution } from "./backtest";
import type { Strategy, Trade } from "./api";

const MARKET = { provider: "binance_usdm", symbol: "BTCUSDT" };

test("normalizeWeights turns raw slider values into shares summing to exactly 1", () => {
  const weights = normalizeWeights(["a", "b", "c"], { a: 2, b: 3, c: 5 });
  assert.equal(Object.values(weights).reduce((sum, value) => sum + value, 0), 1);
  assert.equal(weights.c, 0.5);
});

test("normalizeWeights falls back to an even split when every weight is zero", () => {
  const weights = normalizeWeights(["a", "b", "c", "d"], {});
  assert.deepEqual(weights, { a: 0.25, b: 0.25, c: 0.25, d: 0.25 });
});

/* Rounding to six places can leave a residue; the largest share absorbs it so
   the API's "weights must sum to 1.0" check never trips. */
test("normalizeWeights keeps the sum at 1 for values that do not divide evenly", () => {
  const weights = normalizeWeights(["a", "b", "c"], { a: 1, b: 1, c: 1 });
  assert.equal(Object.values(weights).reduce((sum, value) => sum + value, 0), 1);
});

test("draftIssues rejects a draft the API would 422", () => {
  const draft = createDraft(MARKET, "5m");
  assert.ok(draftIssues(draft).some((issue) => issue.includes("ít nhất 2")));

  const overLimit = { ...draft, selectedStrategyIds: ["a", "b"], weights: { a: 1, b: 1 }, maxCandidates: 501 };
  assert.ok(draftIssues(overLimit).some((issue) => issue.includes("candidate")));

  const valid = { ...draft, selectedStrategyIds: ["a", "b"], weights: { a: 1, b: 1 } };
  assert.deepEqual(draftIssues(valid), []);
});

test("draftToExecution converts a percentage fee into integer basis points", () => {
  const draft = createBacktestDraft(MARKET, "5m");
  const execution = draftToExecution({ ...draft, feePercent: 0.08 });
  assert.equal(execution.feeBps, 8);
  assert.ok(Number.isInteger(execution.feeBps));
});

test("backtest draft defaults to a strategy that exists in the supplied registry", () => {
  assert.equal(defaultBacktestStrategyId([strategy("custom")]), "custom");
  assert.equal(defaultBacktestStrategyId([strategy("custom"), strategy("ma_cross")]), "ma_cross");
  assert.equal(defaultBacktestStrategyId([]), "");
});

test("backtest draft falls back to a timeframe supported by its selected pair", () => {
  assert.equal(defaultBacktestTimeframe(["1m", "5m"], "5m"), "5m");
  assert.equal(defaultBacktestTimeframe(["1h", "4h"], "5m"), "1h");
});

test("draftToExecution drops zero stop-loss and take-profit to null", () => {
  const draft = createBacktestDraft(MARKET, "5m");
  const execution = draftToExecution({ ...draft, stopLossPct: 0, takeProfitPct: 0 });
  assert.equal(execution.stopLossPct, null);
  assert.equal(execution.takeProfitPct, null);
});

test("backtestIssues catches an inverted date range and a negative fee", () => {
  const draft = createBacktestDraft(MARKET, "5m");
  assert.deepEqual(backtestIssues(draft), []);
  assert.ok(backtestIssues({ ...draft, rangeFrom: "2026-02-01", rangeTo: "2026-01-01" }).length > 0);
  assert.ok(backtestIssues({ ...draft, feePercent: -1 }).length > 0);
});

test("deriveKpis counts only settled trades and sums real fee and slippage", () => {
  const kpis = deriveKpis([
    trade({ pnl: 1.5, fee_paid: 0.05, slippage_cost: 0.03 }),
    trade({ pnl: -0.8, fee_paid: 0.05, slippage_cost: 0.03 }),
    trade({ pnl: 0, fee_paid: 0.05, slippage_cost: 0.03 }),
    trade({ pnl: 2, fee_paid: 0.05, slippage_cost: 0.03, exit_reason: "open" }),
  ]);
  assert.equal(kpis.settled, 3);
  assert.equal(kpis.wins, 1);
  assert.equal(kpis.losses, 1);
  assert.equal(Number(kpis.totalProfitAbs.toFixed(2)), 0.7);
  assert.equal(Number(kpis.totalFees.toFixed(2)), 0.2);
});

function trade(patch: Partial<Trade>): Trade {
  return {
    id: "t",
    sequence_no: 1,
    side: "LONG",
    entry_time: "2026-01-01T00:00:00Z",
    exit_time: "2026-01-01T01:00:00Z",
    entry_price: 100,
    exit_price: 101,
    quantity: 1,
    fee_paid: 0,
    slippage_cost: 0,
    sl_price: null,
    tp_price: null,
    pnl: 0,
    pnl_pct: 0,
    exit_reason: "take_profit",
    signal_t: "2026-01-01T00:00:00Z",
    ...patch,
  };
}

function strategy(strategy_id: string): Strategy {
  return {
    strategy_id,
    version: "v1",
    display_name: strategy_id,
    description: "",
    parameters_schema: {},
    default_params: {},
    overlay_types: [],
    warm_up_candles: 0,
    is_composite: false,
    code_fingerprint: strategy_id,
  };
}
