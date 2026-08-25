export const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

export type User = {
  id: string;
  email: string;
  display_name: string;
  role: "RESEARCHER" | "OPERATOR" | "ADMIN";
};

export type Candle = {
  provider: string;
  symbol: string;
  timeframe: string;
  open_time: string;
  close_time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  trade_count: number;
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
  overlay_types: string[];
  warm_up_candles: number;
  is_composite: boolean;
  code_fingerprint: string;
};

export type Metrics = {
  total_return_pct: number;
  win_rate_pct: number;
  max_drawdown_pct: number;
  trade_count: number;
  profit_factor: number;
  sharpe_ratio: number;
  score: number;
  evaluator_version: string;
};

export type ExperimentSummary = {
  id: string;
  run_id: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  provider: string;
  symbol: string;
  timeframe: string;
  strategy_id: string;
  strategy_version: string;
  candidate_hash: string;
  dataset_version: string;
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
  side: string;
  entry_time: string;
  exit_time: string;
  entry_price: number;
  exit_price: number;
  quantity: number;
  pnl: number;
  pnl_pct: number;
  exit_reason: string;
  signal_t: string;
  child_signals?: Record<string, unknown>;
};

export type EquityPoint = { t: string; equity: number; drawdown_pct: number };

export type LeaderboardEntry = {
  id: string;
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

function csrfToken(): string {
  if (typeof document === "undefined") return "";
  const match = document.cookie
    .split("; ")
    .find((cookie) => cookie.startsWith("csrf_token="));
  return match ? decodeURIComponent(match.split("=")[1]) : "";
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body) headers.set("Content-Type", "application/json");
  const method = (init.method ?? "GET").toUpperCase();
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) headers.set("X-CSRF-Token", csrfToken());

  const response = await fetch(`${apiUrl}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });

  const payload = (await response.json().catch(() => undefined)) as unknown;
  if (!response.ok) {
    const errorPayload = payload as ErrorPayload | undefined;
    throw new Error(errorPayload?.error?.message ?? errorPayload?.detail ?? "Request failed");
  }
  return payload as T;
}

export const api = {
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
  candles(timeframe: string, strategy = "composite@1.0.0") {
    void strategy;
    return request<{ candles: Candle[] }>(
      `/api/v1/markets/candles?provider=binance_usdm&symbol=ETHUSDT&timeframe=${timeframe}&limit=180`,
    );
  },
  overlays(timeframe: string, strategy = "composite@1.0.0") {
    return request<{
      series: OverlaySeries[];
      markers: OverlayMarker[];
      seq: number;
      last_closed_at: string;
      is_stale: boolean;
    }>(
      `/api/v1/markets/chart-overlays?provider=binance_usdm&symbol=ETHUSDT&timeframe=${timeframe}&strategy=${strategy}&config_hash=sha256:${"4".repeat(64)}&limit=180`,
    );
  },
  createExperiment(children: Array<{ strategy_id: string; weight: number }>) {
    return request<{ run_id: string; experiment_id: string; status: string }>("/api/v1/experiments", {
      method: "POST",
      body: JSON.stringify({
        provider: "binance_usdm",
        symbol: "ETHUSDT",
        timeframe: "5m",
        strategy_id: "composite",
        strategy_version: "1.0.0",
        children: children.map((child) => ({
          strategy_id: child.strategy_id,
          version: "1.0.0",
          weight: child.weight,
          parameters: defaultParams(child.strategy_id),
        })),
        combination: { policy: "weighted_vote", threshold: 0.34, encoding: "BUY=1,SELL=-1,HOLD=0" },
        initial_equity: 100,
        fixed_notional: 10,
        leverage: 1,
        fee_bps: 10,
        slippage_bps: 0,
        stop_loss_pct: 2.5,
        take_profit_pct: 4,
        intrabar_priority: "stop_loss_first",
        idempotency_key: `manual-${Date.now()}`,
      }),
    });
  },
  experiment(id: string) {
    return request<ExperimentSummary>(`/api/v1/experiments/${id}`);
  },
  experimentCandles(id: string) {
    return request<{ candles: Candle[] }>(`/api/v1/experiments/${id}/candles`);
  },
  experimentTrades(id: string) {
    return request<{ trades: Trade[] }>(`/api/v1/experiments/${id}/trades`);
  },
  experimentEquity(id: string) {
    return request<{ points: EquityPoint[]; max_drawdown: EquityPoint }>(`/api/v1/experiments/${id}/equity`);
  },
  experimentOverlays(id: string) {
    return request<{ series: OverlaySeries[]; signal_markers: OverlayMarker[]; execution_markers: ExecutionMarker[] }>(
      `/api/v1/experiments/${id}/overlays`,
    );
  },
  startSearch() {
    return request<{ search_run_id: string }>("/api/v1/search-runs", {
      method: "POST",
      body: JSON.stringify({
        generator_id: "domain_guided",
        search_space: {
          strategy_ids: ["ma_cross", "rsi", "bollinger", "support_resistance", "news_sentiment", "macd"],
          cardinality: [2, 3],
          policies: ["weighted_vote"],
          parameter_grid: {},
        },
        stop_conditions: { max_candidates: 6, max_duration_sec: 900, max_non_improving: 4 },
        market: {
          provider: "binance_usdm",
          symbol: "ETHUSDT",
          timeframe: "5m",
          range_from: "2026-01-01T00:00:00Z",
          range_to: "2026-03-01T00:00:00Z",
        },
        execution: {},
        seed: 42,
        idempotency_key: `search-${Date.now()}`,
      }),
    });
  },
  searchRun(id: string) {
    return request<SearchRun>(`/api/v1/search-runs/${id}`);
  },
  searchAction(id: string, action: "pause" | "resume" | "cancel") {
    return request<{ status: string }>(`/api/v1/search-runs/${id}/actions`, {
      method: "POST",
      body: JSON.stringify({ action, command_id: `${action}-${Date.now()}` }),
    });
  },
  leaderboard(sortBy = "score") {
    return request<{ entries: LeaderboardEntry[] }>(`/api/v1/leaderboard?limit=10&sort_by=${sortBy}`);
  },
  provenance(id: string) {
    return request<Record<string, unknown>>(`/api/v1/leaderboard/${id}/provenance`);
  },
  news() {
    return request<{ items: NewsItem[]; meta: { last_collected_at: string; total: number } }>("/api/v1/news");
  },
  newsAggregate() {
    return request<{
      distribution: Record<"POSITIVE" | "NEUTRAL" | "NEGATIVE", number>;
      avg_score: number;
      coverage: { items_total: number; items_analyzed: number; items_unanalyzed: number };
    }>("/api/v1/news/aggregate");
  },
  predict(text: string) {
    return request<Prediction>("/api/v1/ai/predict", {
      method: "POST",
      body: JSON.stringify({ text }),
    });
  },
};

function defaultParams(strategyID: string): Record<string, number> {
  switch (strategyID) {
    case "ma_cross":
      return { fast: 20, slow: 50 };
    case "rsi":
      return { period: 14, buy_threshold: 30, sell_threshold: 70 };
    case "bollinger":
      return { period: 20, stddev: 2 };
    case "support_resistance":
      return { lookback: 60, zone_bps: 45 };
    case "news_sentiment":
      return { window_sec: 3600, buy_threshold: 0.45, sell_threshold: -0.45 };
    case "macd":
      return { fast: 12, slow: 26, signal: 9 };
    default:
      return {};
  }
}

export function wsURL(subscriptionKey: string): string {
  const base = apiUrl.replace(/^http/, "ws");
  return `${base}/api/v1/markets/stream?key=${encodeURIComponent(subscriptionKey)}`;
}
