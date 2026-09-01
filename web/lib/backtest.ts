import type { MarketSelection } from "./market";
import type { ExecutionSettings, Strategy, Trade } from "./api";

/* The visible filter strip on ui-reference/backtest.jpg is the request. Before
   this type existed the eight controls were decoration and createExperiment
   posted literals. */

export type BacktestDraft = {
  market: MarketSelection;
  timeframe: string;
  rangeFrom: string;
  rangeTo: string;
  initialEquity: number;
  strategyId: string;
  /* The reference labels this "Transaction Cost %" but the API takes basis
     points, so the UI shows a percentage and converts on submit. */
  feePercent: number;
  slippageBps: number;
  stopLossPct: number;
  takeProfitPct: number;
};

export const PAGE_SIZES = [10, 25, 50, 100] as const;

export function defaultBacktestStrategyId(strategies: Strategy[]): string {
  return strategies.find((strategy) => strategy.strategy_id === "ma_cross")?.strategy_id
    ?? strategies[0]?.strategy_id
    ?? "";
}

export function defaultBacktestTimeframe(timeframes: string[], preferred: string): string {
  return timeframes.includes(preferred) ? preferred : timeframes[0] ?? preferred;
}

export function createBacktestDraft(market: MarketSelection, timeframe: string): BacktestDraft {
  return {
    market,
    timeframe,
    rangeFrom: "2025-05-01",
    rangeTo: "2025-05-15",
    initialEquity: 100,
    strategyId: "ma_cross",
    feePercent: 0.08,
    slippageBps: 5,
    stopLossPct: 2,
    takeProfitPct: 4,
  };
}

/* fee_bps must be an integer (app/schemas.py: fee_bps int, 0..10000).
   0.08% -> 8 bps. */
export function draftToExecution(draft: BacktestDraft): ExecutionSettings {
  return {
    initialEquity: draft.initialEquity,
    fixedNotional: Math.max(1, Math.round(draft.initialEquity / 10)),
    leverage: 1,
    feeBps: Math.round(draft.feePercent * 100),
    slippageBps: Math.round(draft.slippageBps),
    stopLossPct: draft.stopLossPct > 0 ? draft.stopLossPct : null,
    takeProfitPct: draft.takeProfitPct > 0 ? draft.takeProfitPct : null,
    intrabarPriority: "stop_loss_first",
    policy: "weighted_vote",
    threshold: 0.34,
  };
}

export function backtestIssues(draft: BacktestDraft): string[] {
  const issues: string[] = [];
  if (draft.initialEquity <= 0) issues.push("Vốn phải lớn hơn 0.");
  if (draft.feePercent < 0 || draft.feePercent > 100) issues.push("Transaction cost phải trong [0, 100]%.");
  if (draft.slippageBps < 0 || draft.slippageBps > 10_000) issues.push("Slippage phải trong [0, 10000] bps.");
  if (draft.stopLossPct < 0 || draft.stopLossPct >= 100) issues.push("Stop loss phải trong [0, 100)%.");
  if (draft.takeProfitPct < 0) issues.push("Take profit không được âm.");
  if (draft.rangeFrom && draft.rangeTo && draft.rangeFrom > draft.rangeTo) {
    issues.push("From date phải trước To date.");
  }
  return issues;
}

/* The evaluator returns return %, win rate %, drawdown % and trade count.
   Wins, losses and absolute profit are not in the metrics payload but are
   derivable from the settled trade list, so they are computed rather than
   guessed. */
export type DerivedKpis = {
  wins: number;
  losses: number;
  settled: number;
  totalProfitAbs: number;
  totalFees: number;
  totalSlippage: number;
};

export function deriveKpis(trades: Trade[]): DerivedKpis {
  const settled = trades.filter((trade) => trade.exit_reason !== "open");
  return {
    wins: settled.filter((trade) => trade.pnl > 0).length,
    losses: settled.filter((trade) => trade.pnl < 0).length,
    settled: settled.length,
    totalProfitAbs: settled.reduce((sum, trade) => sum + trade.pnl, 0),
    totalFees: trades.reduce((sum, trade) => sum + trade.fee_paid, 0),
    totalSlippage: trades.reduce((sum, trade) => sum + trade.slippage_cost, 0),
  };
}
