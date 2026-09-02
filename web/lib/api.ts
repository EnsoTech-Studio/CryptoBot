import {
  DEFAULT_MARKET,
  MARKET_CONFIG_HASH,
  PANEL_BOOTSTRAP_CANDLE_LIMIT,
  marketRequestPath,
  type Candle,
  type MarketPair,
  type MarketSelection,
  type MarketStatus,
} from "./market";
import { normalizeWeights, type DiscoveryDraft } from "./discovery";

export type { Candle, MarketPair, MarketSelection, MarketStatus } from "./market";

export const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

export type User = {
  id: string;
  email: string;
  display_name: string;
  role: "RESEARCHER" | "OPERATOR" | "ADMIN";
};

export type MarketDataset = {
  id: string;
  dataset_version: string;
  market: { provider: string; symbol: string; timeframe: string };
  range_from: string;
  range_to: string;
  revision_no: number;
  candle_count: number;
  content_hash: string;
  bbo_content_hash: string;
};

export type OverlayPoint = { t: string; v: number | null };
export type OverlaySeries = {
  name: string;
  overlay_type: string;
  pane: "main" | "sub";
  unit?: string;
  scale?: { min: number; max: number };
  points?: OverlayPoint[];
  band?: { upper: OverlayPoint[]; middle: OverlayPoint[]; lower: OverlayPoint[] };
  zones?: { from: string; to: string; price_low: number; price_high: number }[];
  constant?: number;
  style?: "solid" | "dashed";
};
export type OverlayMarker = {
  t: string;
  overlay_type: string;
  confidence: number | null;
  evidence: Record<string, unknown> | null;
};

export type ExecutionMarker = {
  sequence_no?: number;
  selected?: boolean;
  t: string;
  line_until?: string;
  overlay_type: "entry" | "exit" | "stop_loss" | "take_profit" | string;
  trade_id?: string;
  price?: number;
  signal_t?: string;
  exit_reason?: string;
};

export type Strategy = {
  strategy_id: string;
  version: string;
  family?: string;
  display_name: string;
  description: string;
  parameters_schema: Record<string, unknown>;
  default_params: Record<string, unknown>;
  overlay_types: string[];
  warm_up_candles: number;
  is_composite: boolean;
  code_fingerprint: string;
};

export type StrategyExecution = {
  strategy_id: string;
  strategy_version?: string;
  parameters?: Record<string, unknown>;
  weight: number;
};

export type StrategySpec = {
  schema_version: string;
  strategy_id: string;
  display_name: string;
  family: "trend" | "momentum" | "volatility" | "structure" | "information";
  description: string;
  parameters: Record<string, Record<string, unknown>>;
  indicators: Array<Record<string, unknown>>;
  rules: Record<string, unknown>;
  warmup_bars: number;
};

export type StrategyDraft = {
  draft_id: string;
  owner_id: string;
  source_type: "text" | "approved_url" | "dsl";
  mode: "dsl" | "custom_python";
  name_hint: string | null;
  status: string;
  current_revision: number;
  source_hash: string;
  spec_hash: string | null;
  artifact_hash: string | null;
  sandbox_report_hash: string | null;
  repair_attempts_used: number;
  repair_attempts_max: number;
  strategy_spec: StrategySpec | null;
  created_at: string;
  updated_at: string;
};

export type Metrics = {
  total_return_pct: number;
  win_rate_pct: number;
  max_drawdown_pct: number;
  trade_count: number;
  wins: number;
  losses: number;
  net_profit: number;
  profit_factor: number;
  sharpe_ratio: number;
  score: number | null;
  evaluator_version: string;
};

export type ExperimentSummary = {
  id: string;
  run_id: string | null;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  provider: string;
  symbol: string;
  timeframe: string;
  strategy_id: string;
  strategy_version: string;
  candidate_hash: string;
  dataset_version: string;
  range_from: string;
  range_to: string;
  content_hash: string;
  created_at: string;
  candles_read: number;
  signals_count: number;
  metrics: Metrics | null;
  execution: Record<string, unknown>;
  candidate_definition: Record<string, unknown>;
};

export type Trade = {
  id: string;
  sequence_no: number;
  symbol: string;
  quote_currency: string;
  side: string;
  entry_time: string;
  exit_time: string;
  entry_price: number;
  exit_price: number;
  quantity: number;
  entry_notional: number;
  exit_notional: number | null;
  /* Research returns these; the adapter used to drop them, which made the
     reference ledger's Phi / Slippage / Stoploss / TakeProfit columns
     impossible to fill truthfully. */
  fee_paid: number;
  spread_cost: number;
  slippage_cost: number;
  gross_pnl: number | null;
  net_pnl: number | null;
  sl_price: number | null;
  tp_price: number | null;
  pnl: number;
  pnl_pct: number;
  exit_reason: string;
  signal_t: string;
  child_signals?: Record<string, unknown>;
};

export type EquityPoint = { t: string; equity: number; drawdown_pct: number };

export type LeaderboardEntry = {
  id: string;
  experiment_id: string;
  rank: number;
  score: number;
  strategy_id: string;
  strategy_version: string;
  candidate_hash: string;
  dataset_version: string;
  total_return_pct: number;
  win_rate_pct: number;
  max_drawdown_pct: number;
  sharpe_ratio: number;
  trade_count: number;
  observed_at: string;
};

export type SearchRun = {
  search_run_id: string;
  generator_id: string;
  status: string;
  candidates: { generated: number; tested: number; failed: number };
  best_score: number | null;
  current_candidate: string;
  dataset: { dataset_version: string; content_hash: string };
  stop_reason: string | null;
  updated_at: string;
};

export type DiscoveryArchiveCandidate = {
  candidate_id: string;
  ordinal: number;
  candidate_hash: string;
  candidate_definition: Record<string, unknown>;
  lineage: Record<string, unknown>;
  score: number | null;
  accepted: boolean | null;
  rejection_reason: string | null;
  assessment: Record<string, unknown> | null;
  reservation?: {
    reserved_jobs: number | null;
    consumed_jobs: number | null;
    released_jobs: number | null;
    status: string | null;
  };
  assessed_at: string | null;
};

export type DiscoveryArchive = {
  search_run_id: string;
  state: Record<string, unknown>;
  candidates: DiscoveryArchiveCandidate[];
};

export type NewsItem = {
  id: string;
  title: string;
  url: string;
  published_at: string;
  source: { key: string; display_name: string };
  related_coins: string[] | null;
  sentiment: null | {
    label: "POSITIVE" | "NEUTRAL" | "NEGATIVE";
    score: number;
    model: string;
    model_version: string;
    analyzed_at: string;
  };
};

export type Prediction = {
  label: string;
  score: number;
  model: string;
  model_version: string;
  received_at: string;
};

type ErrorPayload = {
  error?: { code?: string; message?: string };
  detail?: string;
};

type Numeric = number | string;
type ResearchTrade = {
  sequence_no: number;
  symbol: string;
  quote_currency: string;
  side: string;
  signal_t: string | null;
  entry_time: string;
  entry_price: number;
  quantity: number;
  entry_notional: number;
  fee_paid: number;
  spread_cost: number;
  slippage_cost: number;
  exit_time: string | null;
  exit_price: number | null;
  exit_notional: number | null;
  gross_pnl: number | null;
  net_pnl: number | null;
  pnl_absolute: number | null;
  pnl_percent: number | null;
  exit_reason: string | null;
  sl_price: number | null;
  tp_price: number | null;
};
type ResearchEquityPoint = {
  point_time: string;
  equity: number;
  drawdown_pct: number | null;
};
type ResearchOverlay = {
  candle_time: string;
  signal: string;
  confidence: number | null;
  child_signals: Record<string, unknown> | null;
};
type ResearchExecutionMarker = {
  sequence_no: number;
  t: string;
  line_until?: string;
  overlay_type: string;
  price: number;
  exit_reason?: string;
};
type ResearchSearchRun = {
  search_run_id: string;
  generator_id: string;
  status: string;
  generated: number;
  tested: number;
  failed: number;
  best_score: number | null;
  current_candidate_hash: string | null;
  dataset_version: string;
  content_hash: string;
  stop_reason: string | null;
  updated_at: string;
};
type ResearchLeaderboardEntry = Omit<LeaderboardEntry, "id"> & { entry_id: string };
type ResearchNewsItem = Omit<NewsItem, "source"> & {
  source_key: string;
  source_name: string;
};
type ResearchNewsAggregate = {
  item_count: number;
  analyzed_count: number;
  coverage: number;
  average_score: number | null;
  label_counts: Record<"POSITIVE" | "NEUTRAL" | "NEGATIVE", number>;
};

function normalizeCandle(candle: Omit<Candle, "open" | "high" | "low" | "close" | "volume"> & {
  open: Numeric;
  high: Numeric;
  low: Numeric;
  close: Numeric;
  volume: Numeric;
}): Candle {
  return {
    ...candle,
    open: Number(candle.open),
    high: Number(candle.high),
    low: Number(candle.low),
    close: Number(candle.close),
    volume: Number(candle.volume),
  };
}

function normalizeSearchRun(run: ResearchSearchRun): SearchRun {
  return {
    search_run_id: run.search_run_id,
    generator_id: run.generator_id,
    status: run.status,
    candidates: { generated: run.generated, tested: run.tested, failed: run.failed },
    best_score: run.best_score,
    current_candidate: run.current_candidate_hash ?? "",
    dataset: { dataset_version: run.dataset_version, content_hash: run.content_hash },
    stop_reason: run.stop_reason,
    updated_at: run.updated_at,
  };
}

async function ensureDataset(market: MarketSelection, timeframe: string, requestedVersion?: string): Promise<MarketDataset> {
  const existing = await api.datasets(market, timeframe);
  return existing.datasets.find((dataset) => dataset.dataset_version === requestedVersion)
    ?? existing.datasets[0]
    ?? api.createDataset(market, timeframe);
}

/* Discovery needs enough legal, reproducible variants for a real demo run.
   Defaults-only plus one composite produces one candidate and makes the loop
   look broken. These bounded values stay inside each built-in plugin's schema;
   the model still sees this grid and may choose from it using archive/research. */
const DISCOVERY_PARAMETER_GRID: Record<string, Record<string, number[]>> = {
  ma_cross: { fast: [5, 10, 20], slow: [30, 50, 80] },
  ema_cross: { fast: [5, 10, 20], slow: [30, 50, 80] },
  rsi: { period: [10, 14, 21], oversold: [25, 30], overbought: [70, 75] },
  support_resistance: { period: [14, 20, 30, 40] },
  bollinger: { period: [14, 20, 30], deviation: [1.5, 2, 2.5] },
  macd: { fast: [8, 12], slow: [20, 26, 40], signal: [5, 9] },
};

function discoveryParameterGrid(strategyIds: string[]): Record<string, Record<string, number[]>> {
  return Object.fromEntries(
    strategyIds
      .filter((strategyId) => DISCOVERY_PARAMETER_GRID[strategyId])
      .map((strategyId) => [strategyId, DISCOVERY_PARAMETER_GRID[strategyId]]),
  );
}

/* Execution assumptions the Backtest screen puts on screen. They used to be
   literals inside createExperiment, which meant the visible fee and slippage
   inputs changed nothing. Bounds mirror app/schemas.py ExperimentCreateIn. */
export type ExecutionSettings = {
  initialEquity: number;
  fixedNotional: number;
  leverage: number;
  feeBps: number;
  slippageBps: number;
  stopLossPct: number | null;
  takeProfitPct: number | null;
  intrabarPriority: "stop_loss_first" | "take_profit_first";
  policy: "weighted_vote" | "majority_vote";
  threshold: number;
};

export const DEFAULT_EXECUTION: ExecutionSettings = {
  initialEquity: 100,
  fixedNotional: 10,
  leverage: 1,
  feeBps: 8,
  slippageBps: 5,
  stopLossPct: 2,
  takeProfitPct: 4,
  intrabarPriority: "stop_loss_first",
  policy: "weighted_vote",
  threshold: 0.34,
};

function csrfToken(): string {
  if (typeof document === "undefined") return "";
  const match = document.cookie
    .split("; ")
    .find((cookie) => cookie.startsWith("csrf_token="));
  return match ? decodeURIComponent(match.split("=")[1]) : "";
}

let refreshingSession: Promise<boolean> | null = null;

/* Multiple panels can receive a 401 together when the short-lived access
   cookie expires. Share one refresh request: refresh tokens rotate, so a
   request per panel would otherwise invalidate the session itself. */
function refreshAccessSession(): Promise<boolean> {
  if (refreshingSession) return refreshingSession;
  refreshingSession = fetch(`${apiUrl}/api/v1/auth/refresh`, {
    method: "POST",
    headers: { "X-CSRF-Token": csrfToken() },
    credentials: "include",
    signal: AbortSignal.timeout(8_000),
  })
    .then((response) => response.ok)
    .catch(() => false)
    .finally(() => { refreshingSession = null; });
  return refreshingSession;
}

async function request<T>(path: string, init: RequestInit = {}, timeoutMs = 8_000, retried = false): Promise<T> {
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body) headers.set("Content-Type", "application/json");
  const method = (init.method ?? "GET").toUpperCase();
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) headers.set("X-CSRF-Token", csrfToken());

  let response: Response;
  try {
    response = await fetch(`${apiUrl}${path}`, {
      ...init,
      headers,
      credentials: "include",
      signal: init.signal ?? AbortSignal.timeout(timeoutMs),
    });
  } catch (error) {
    if (error instanceof DOMException && (error.name === "TimeoutError" || error.name === "AbortError")) {
      throw new Error("API request timed out");
    }
    throw error;
  }

  const payload = (await response.json().catch(() => undefined)) as unknown;
  if (response.status === 401 && !retried && !path.startsWith("/api/v1/auth/") && await refreshAccessSession()) {
    return request<T>(path, init, timeoutMs, true);
  }
  if (!response.ok) {
    const errorPayload = payload as ErrorPayload | undefined;
    throw new Error(errorPayload?.error?.message ?? errorPayload?.detail ?? "Request failed");
  }
  return payload as T;
}

export const api = {
  register(email: string, password: string, displayName: string) {
    return request<{ user: User }>("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, display_name: displayName }),
    });
  },
  login(email: string, password: string) {
    return request<{ user: User }>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  },
  me() {
    return request<{ user: User }>("/api/v1/auth/me");
  },
  logout() {
    return request<{ status: string }>("/api/v1/auth/logout", { method: "POST" });
  },
  strategies() {
    return request<{ strategies: Strategy[] }>("/api/v1/strategies");
  },
  createStrategyDraft(
    source: { type: "text"; text: string } | { type: "approved_url"; url: string },
    nameHint?: string,
    mode: StrategyDraft["mode"] = "dsl",
  ) {
    return request<StrategyDraft>("/api/v1/strategy-drafts", {
      method: "POST",
      body: JSON.stringify({
        mode,
        source,
        name_hint: nameHint || undefined,
        idempotency_key: `strategy-draft-${Date.now()}`,
      }),
    });
  },
  strategyDrafts(limit?: number) {
    const query = limit === undefined ? "" : `?limit=${Math.max(1, Math.floor(limit))}`;
    return request<{ drafts: StrategyDraft[] }>(`/api/v1/strategy-drafts${query}`);
  },
  strategyDraft(draftId: string) {
    return request<StrategyDraft>(`/api/v1/strategy-drafts/${encodeURIComponent(draftId)}`);
  },
  cancelStrategyDraft(draftId: string) {
    return request<StrategyDraft>(`/api/v1/strategy-drafts/${encodeURIComponent(draftId)}/actions`, {
      method: "POST",
      body: JSON.stringify({ action: "cancel" }),
    });
  },
  approveStrategyDraft(
    draft: StrategyDraft,
    reason = draft.mode === "custom_python"
      ? "Đã kiểm tra custom artifact; cần build/deploy, không hot-load vào runtime."
      : "Đã kiểm tra spec, artifact và sandbox fingerprint.",
  ) {
    if (!draft.spec_hash || !draft.artifact_hash || !draft.sandbox_report_hash) {
      throw new Error("Draft chưa có đủ fingerprint để approve");
    }
    return request<StrategyDraft>(`/api/v1/strategy-drafts/${draft.draft_id}/approval`, {
      method: "POST",
      body: JSON.stringify({
        revision: draft.current_revision,
        spec_hash: draft.spec_hash,
        artifact_hash: draft.artifact_hash,
        sandbox_report_hash: draft.sandbox_report_hash,
        decision: "approve",
        reason,
        idempotency_key: `strategy-approval-${draft.draft_id}-${draft.current_revision}`,
      }),
    });
  },
  marketPairs() {
    return request<{ pairs: MarketPair[] }>("/api/v1/markets/pairs", {}, 2_500);
  },
  marketStatus(market: MarketSelection, timeframe: string) {
    return request<MarketStatus>(marketRequestPath("/api/v1/markets/status", market, { timeframe }));
  },
  candles(market: MarketSelection, timeframe: string, limit = PANEL_BOOTSTRAP_CANDLE_LIMIT) {
    return request<{ candles: Candle[] }>(
      marketRequestPath("/api/v1/markets/candles", market, { timeframe, limit }),
    ).then((payload) => ({
      ...payload,
      candles: payload.candles.map(normalizeCandle),
    }));
  },
  overlays(market: MarketSelection, timeframe: string, strategy = "composite@v1", limit = PANEL_BOOTSTRAP_CANDLE_LIMIT) {
    return request<{
      series: OverlaySeries[];
      markers: OverlayMarker[];
      seq: number;
      last_closed_at: string;
      is_stale: boolean;
    }>(
      marketRequestPath("/api/v1/markets/chart-overlays", market, {
        timeframe,
        strategy,
        config_hash: MARKET_CONFIG_HASH,
        limit,
      }),
    );
  },
  datasets(market: MarketSelection = DEFAULT_MARKET, timeframe = "5m", signal?: AbortSignal) {
    return request<{ datasets: MarketDataset[] }>(
      marketRequestPath("/api/v1/markets/datasets", market, { timeframe, limit: 20 }),
      { signal },
    );
  },
  createDataset(market: MarketSelection = DEFAULT_MARKET, timeframe = "5m") {
    return request<MarketDataset>("/api/v1/markets/datasets", {
      method: "POST",
      body: JSON.stringify({
        provider: market.provider,
        symbol: market.symbol,
        timeframe,
        revision_no: 1,
      }),
    }, 30_000);
  },
  async createExperiment(
    children: StrategyExecution[],
    market: MarketSelection = DEFAULT_MARKET,
    timeframe = "5m",
    execution: ExecutionSettings = DEFAULT_EXECUTION,
    range?: { from: string; to: string },
    datasetVersion?: string,
  ) {
    const dataset = await ensureDataset(market, timeframe, datasetVersion);
    const isSingleStrategy = children.length === 1;
    const single = children[0];
    const replayRange = range ? boundedReplayRange(range, dataset) : undefined;
    return request<{ run_id: string; experiment_id: string; status: string }>("/api/v1/experiments", {
      method: "POST",
      body: JSON.stringify({
        provider: market.provider,
        symbol: market.symbol,
        timeframe,
        strategy_id: isSingleStrategy ? single.strategy_id : "composite",
        strategy_version: isSingleStrategy ? single.strategy_version ?? "v1" : "v1",
        ...(isSingleStrategy ? {
          candidate_definition: {
            strategy_id: single.strategy_id,
            version: single.strategy_version ?? "v1",
            parameters: single.parameters ?? {},
          },
        } : {}),
        dataset_version: dataset.dataset_version,
        ...(replayRange ? { range_from: replayRange.from, range_to: replayRange.to } : {}),
        ...(isSingleStrategy ? {} : {
          children: children.map((child) => ({
            strategy_id: child.strategy_id,
            version: child.strategy_version ?? "v1",
            weight: child.weight,
            parameters: child.parameters ?? {},
          })),
          combination: { policy: execution.policy, threshold: execution.threshold },
        }),
        initial_equity: execution.initialEquity,
        fixed_notional: execution.fixedNotional,
        leverage: execution.leverage,
        fee_bps: execution.feeBps,
        slippage_bps: execution.slippageBps,
        stop_loss_pct: execution.stopLossPct,
        take_profit_pct: execution.takeProfitPct,
        intrabar_priority: execution.intrabarPriority,
        idempotency_key: `manual-${Date.now()}`,
      }),
    });
  },
  experiment(id: string) {
    return request<ExperimentSummary>(`/api/v1/experiments/${id}`);
  },
  experiments(limit?: number) {
    const query = limit === undefined ? "" : `?limit=${Math.max(1, Math.floor(limit))}`;
    return request<{ experiments: ExperimentSummary[] }>(`/api/v1/experiments${query}`);
  },
  experimentCandles(id: string, market: MarketSelection = DEFAULT_MARKET, timeframe = "5m") {
    return request<{ candles: Omit<Candle, "provider" | "symbol" | "timeframe">[] }>(
      `/api/v1/experiments/${id}/candles`,
    ).then((payload) => ({
      candles: payload.candles.map((candle) => normalizeCandle({
        ...candle,
        provider: market.provider,
        symbol: market.symbol,
        timeframe,
      })),
    }));
  },
  experimentTrades(id: string, afterSequence?: number, limit = 100) {
    const query = new URLSearchParams({ limit: String(Math.min(200, Math.max(1, limit))) });
    if (afterSequence !== undefined) query.set("after_sequence", String(afterSequence));
    return request<{ trades: ResearchTrade[]; next_cursor: number | null }>(
      `/api/v1/experiments/${id}/trades?${query}`,
    ).then((payload) => ({
      trades: payload.trades.map((trade) => ({
        id: `${id}-${trade.sequence_no}`,
        sequence_no: trade.sequence_no,
        symbol: trade.symbol,
        quote_currency: trade.quote_currency,
        side: trade.side,
        entry_time: trade.entry_time,
        exit_time: trade.exit_time ?? trade.entry_time,
        entry_price: trade.entry_price,
        exit_price: trade.exit_price ?? trade.entry_price,
        quantity: trade.quantity,
        entry_notional: trade.entry_notional,
        exit_notional: trade.exit_notional ?? null,
        fee_paid: trade.fee_paid ?? 0,
        spread_cost: trade.spread_cost ?? 0,
        slippage_cost: trade.slippage_cost ?? 0,
        gross_pnl: trade.gross_pnl ?? null,
        net_pnl: trade.net_pnl ?? null,
        sl_price: trade.sl_price ?? null,
        tp_price: trade.tp_price ?? null,
        pnl: trade.pnl_absolute ?? 0,
        pnl_pct: trade.pnl_percent ?? 0,
        exit_reason: trade.exit_reason ?? "open",
        signal_t: trade.signal_t ?? trade.entry_time,
      })),
      next_cursor: payload.next_cursor,
    }));
  },
  experimentEquity(id: string, limit = 1_200) {
    return request<{ equity: ResearchEquityPoint[] }>(`/api/v1/experiments/${id}/equity?limit=${limit}`).then((payload) => {
      const points = payload.equity.map((point) => ({
        t: point.point_time,
        equity: point.equity,
        drawdown_pct: point.drawdown_pct ?? 0,
      }));
      const maxDrawdown = points.reduce(
        (lowest, point) => point.drawdown_pct < lowest.drawdown_pct ? point : lowest,
        points[0] ?? { t: "", equity: 0, drawdown_pct: 0 },
      );
      return { points, max_drawdown: maxDrawdown };
    });
  },
  experimentOverlays(id: string) {
    return request<{ overlays: ResearchOverlay[]; execution_markers: ResearchExecutionMarker[] }>(
      `/api/v1/experiments/${id}/overlays`,
    ).then((payload) => ({
      series: [] as OverlaySeries[],
      signal_markers: payload.overlays.map((item) => ({
        t: item.candle_time,
        overlay_type: item.signal.toLowerCase(),
        confidence: item.confidence,
        evidence: item.child_signals,
      })),
      execution_markers: payload.execution_markers ?? [],
    }));
  },
  /* Takes the visible draft. The previous signature ignored its arguments and
     posted a fixed 6-strategy domain_guided payload, so the on-screen method,
     weights and limits were decoration. */
  async startSearch(draft: DiscoveryDraft, children?: StrategyExecution[]) {
    const dataset = await ensureDataset(draft.market, draft.timeframe);
    const weights = normalizeWeights(draft.selectedStrategyIds, draft.weights);
    const executionChildren: StrategyExecution[] = children ?? draft.selectedStrategyIds.map((strategy_id) => ({
      strategy_id,
      weight: weights[strategy_id],
    }));
    return request<ResearchSearchRun>("/api/v1/search-runs", {
      method: "POST",
      body: JSON.stringify({
        generator_id: draft.method,
        search_space: {
          strategy_ids: draft.selectedStrategyIds,
          /* Keep individual leaves and smaller composites in the candidate
             pool. The builder's selected combination remains the execution
             default, while discovery can test alternatives. */
          cardinality: Array.from(new Set([1, 2, draft.selectedStrategyIds.length]))
            .filter((value) => value <= draft.selectedStrategyIds.length),
          policies: [draft.policy],
          parameter_grid: discoveryParameterGrid(draft.selectedStrategyIds),
        },
        stop_conditions: {
          max_candidates: draft.maxCandidates,
          max_duration_sec: draft.maxDurationSec,
          max_non_improving: draft.maxNonImproving,
        },
        market: {
          provider: draft.market.provider,
          symbol: draft.market.symbol,
          timeframe: draft.timeframe,
          dataset_version: dataset.dataset_version,
          range_from: dataset.range_from,
          range_to: dataset.range_to,
        },
        execution: {
          children: executionChildren.map((child) => ({
            strategy_id: child.strategy_id,
            version: child.strategy_version ?? "v1",
            weight: child.weight,
            parameters: child.parameters ?? {},
          })),
        },
        seed: draft.seed,
        idempotency_key: `search-${Date.now()}`,
      }),
    }, 45_000).then(normalizeSearchRun);
  },
  searchRun(id: string) {
    return request<ResearchSearchRun>(`/api/v1/search-runs/${id}`).then(normalizeSearchRun);
  },
  discoveryRuns() {
    return request<{ runs: ResearchSearchRun[] }>("/api/v1/search-runs").then(
      (payload) => payload.runs.map(normalizeSearchRun),
    );
  },
  searchAction(id: string, action: "pause" | "resume" | "cancel") {
    return request<{ status: string }>(`/api/v1/search-runs/${id}/actions`, {
      method: "POST",
      body: JSON.stringify({ action, command_id: `${action}-${Date.now()}` }),
    });
  },
  leaderboard(marketOrSortBy: MarketSelection | string = DEFAULT_MARKET, timeframe = "5m", sortBy = "score") {
    const market = typeof marketOrSortBy === "string" ? DEFAULT_MARKET : marketOrSortBy;
    const requestedTimeframe = typeof marketOrSortBy === "string" ? "5m" : timeframe;
    const requestedSort = typeof marketOrSortBy === "string" ? marketOrSortBy : sortBy;
    const path = marketRequestPath("/api/v1/leaderboard", market, {
      timeframe: requestedTimeframe,
      limit: 10,
      sort_by: requestedSort,
    });
    return request<{ entries: ResearchLeaderboardEntry[] }>(path).then(
      (payload) => ({ entries: payload.entries.map((entry) => ({ ...entry, id: entry.entry_id })) }),
    );
  },
  discoveryArchive(id: string) {
    return request<DiscoveryArchive>(`/api/v1/search-runs/${encodeURIComponent(id)}/archive`);
  },
  provenance(id: string) {
    return request<Record<string, unknown>>(`/api/v1/leaderboard/${id}/provenance`);
  },
  news() {
    return request<{ items: ResearchNewsItem[] }>("/api/v1/news").then((payload) => ({
      items: payload.items.map((item) => ({
        ...item,
        source: { key: item.source_key, display_name: item.source_name },
      })),
      meta: { last_collected_at: "", total: payload.items.length },
    }));
  },
  newsAggregate() {
    return request<ResearchNewsAggregate>("/api/v1/news/aggregate").then((payload) => ({
      distribution: payload.label_counts,
      avg_score: payload.average_score ?? 0,
      coverage: {
        items_total: payload.item_count,
        items_analyzed: payload.analyzed_count,
        items_unanalyzed: payload.item_count - payload.analyzed_count,
      },
    }));
  },
  collectNews(sourceId?: string) {
    return request<{ results: Array<Record<string, unknown>> }>("/api/v1/admin/news/collect", {
      method: "POST",
      body: JSON.stringify({ source_id: sourceId ?? null }),
    });
  },
  predict(text: string) {
    return request<Prediction>("/api/v1/ai/predict", {
      method: "POST",
      body: JSON.stringify({ text }),
    });
  },
};

function utcStart(date: string): string {
  return new Date(`${date}T00:00:00.000Z`).toISOString();
}

function utcEndExclusive(date: string): string {
  const [year, month, day] = date.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day + 1)).toISOString();
}

function boundedReplayRange(range: { from: string; to: string }, dataset: MarketDataset) {
  const from = utcStart(range.from);
  const to = utcEndExclusive(range.to);
  return {
    from: new Date(from) < new Date(dataset.range_from) ? dataset.range_from : from,
    to: new Date(to) > new Date(dataset.range_to) ? dataset.range_to : to,
  };
}

export function wsURL(subscriptionKey: string): string {
  const base = apiUrl.replace(/^http/, "ws");
  return `${base}/api/v1/markets/stream?key=${encodeURIComponent(subscriptionKey)}`;
}
