import type { MarketSelection } from "./market";
import type { ExecutionMarker, ExecutionSettings, MarketDataset, Strategy, StrategyExecution, Trade } from "./api";

export type BacktestMode = "single" | "composite";

/* Temporary option used when Discovery opens Backtest with an unsaved combo. */
export const DISCOVERY_BACKTEST_COMPOSITE_ID = "discovery-backtest-composite";

export type SavedCompositeStrategy = {
  id: string;
  displayName: string;
  children: StrategyExecution[];
  policy: "weighted_vote" | "majority_vote";
  threshold: number;
  createdAt: string;
};

/* The visible filter strip on ui-reference/backtest.jpg is the request. Before
   this type existed the eight controls were decoration and createExperiment
   posted literals. */

export type BacktestDraft = {
  market: MarketSelection;
  timeframe: string;
  mode: BacktestMode;
  selectedStrategyIds: string[];
  selectedStrategyWeights?: Record<string, number>;
  selectedCompositeId?: string;
  datasetVersion: string;
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

/* The research service keeps strategy versions immutable. Older database
   rows may therefore still expose an empty default_params object; retain the
   canonical built-in defaults at the request boundary so the experiment
   snapshot records the values the engine actually uses. */
const BUILTIN_DEFAULT_PARAMS: Record<string, Record<string, unknown>> = {
  ma_cross: { fast: 20, slow: 50 },
  ema_cross: { fast: 20, slow: 50 },
  rsi: { period: 14, oversold: 30, overbought: 70 },
  bollinger: { period: 20, deviation: 2 },
  macd: { fast: 12, slow: 26, signal: 9 },
  smc: { swing_period: 20 },
  support_resistance: { period: 20 },
  news_sentiment: { buy_above: 0.7, sell_below: -0.7, min_items: 3 },
};

export function effectiveStrategyParameters(strategy: Strategy): Record<string, unknown> {
  return {
    ...(strategy.version === "v1" ? BUILTIN_DEFAULT_PARAMS[strategy.strategy_id] ?? {} : {}),
    ...(strategy.default_params ?? {}),
  };
}

export function isExecutionMarkerSelected(marker: ExecutionMarker, sequenceNo: number | null): boolean {
  return sequenceNo !== null && marker.sequence_no === sequenceNo;
}

export function needsMoreTradesForPage(
  loadedCount: number, page: number, pageSize: number, nextCursor: number | null,
): boolean {
  return nextCursor !== null && loadedCount < page * pageSize;
}

export function canRunBacktest(userPresent: boolean, running: boolean, noStrategies: boolean, issues: string[]): boolean {
  return userPresent && !running && !noStrategies && issues.length === 0;
}

export function canCancelBacktest(status: string | null): boolean {
  return status === "queued" || status === "running";
}

export function buildBacktestChildren(
  mode: BacktestMode,
  singleStrategyId: string,
  selectedStrategyIds: string[],
  strategies: Strategy[],
  selectedStrategyWeights?: Record<string, number>,
): StrategyExecution[] {
  const ids = mode === "single" ? [singleStrategyId] : selectedStrategyIds;
  const valid = ids.filter((id, index) => id && ids.indexOf(id) === index && strategies.some((strategy) => strategy.strategy_id === id));
  const weight = mode === "single" ? 1 : valid.length > 0 ? 1 / valid.length : 0;
  return valid.map((strategyId) => {
    const definition = strategies.find((strategy) => strategy.strategy_id === strategyId);
    return {
      strategy_id: strategyId,
      strategy_version: definition?.version ?? "v1",
      parameters: definition ? effectiveStrategyParameters(definition) : {},
      weight: mode === "single" ? 1 : Number((selectedStrategyWeights?.[strategyId] ?? weight).toFixed(6)),
    };
  });
}

export function pickBacktestDataset(datasets: MarketDataset[], version: string): MarketDataset | undefined {
  return datasets.find((dataset) => dataset.dataset_version === version) ?? datasets[0];
}

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
    mode: "single",
    selectedStrategyIds: ["ma_cross"],
    datasetVersion: "",
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
  if (draft.mode === "composite" && draft.selectedStrategyIds.length < 2) {
    issues.push("Composite cần ít nhất 2 strategy.");
  }
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

export function resolvedTradeKpis(
  metrics: { wins: number; losses: number; net_profit: number } | null,
  fallback: DerivedKpis,
) {
  return metrics
    ? { wins: metrics.wins, losses: metrics.losses, netProfit: metrics.net_profit }
    : { wins: fallback.wins, losses: fallback.losses, netProfit: fallback.totalProfitAbs };
}

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
