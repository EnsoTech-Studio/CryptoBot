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

type Numeric = number | string;
type ResearchTrade = {
  sequence_no: number;
  side: string;
  signal_t: string | null;
  entry_time: string;
  entry_price: number;
  quantity: number;
  exit_time: string | null;
  exit_price: number | null;
  pnl_absolute: number | null;
  pnl_percent: number | null;
  exit_reason: string | null;
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

async function ensureDataset(timeframe: string): Promise<MarketDataset> {
  const existing = await api.datasets(timeframe);
  return existing.datasets[0] ?? api.createDataset(timeframe);
}

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
  candles(timeframe: string, strategy = "composite@v1") {
    void strategy;
    return request<{ candles: Candle[] }>(
      `/api/v1/markets/candles?provider=binance_usdm&symbol=ETHUSDT&timeframe=${timeframe}&limit=180`,
    ).then((payload) => ({
      ...payload,
      candles: payload.candles.map(normalizeCandle),
    }));
  },
  overlays(timeframe: string, strategy = "composite@v1") {
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
  datasets(timeframe = "5m") {
    return request<{ datasets: MarketDataset[] }>(
      `/api/v1/markets/datasets?provider=binance_usdm&symbol=ETHUSDT&timeframe=${timeframe}&limit=20`,
    );
  },
  createDataset(timeframe = "5m") {
    return request<MarketDataset>("/api/v1/markets/datasets", {
      method: "POST",
      body: JSON.stringify({
        provider: "binance_usdm",
        symbol: "ETHUSDT",
        timeframe,
        revision_no: 1,
      }),
    });
  },
  async createExperiment(children: Array<{ strategy_id: string; weight: number }>) {
    const dataset = await ensureDataset("5m");
    return request<{ run_id: string; experiment_id: string; status: string }>("/api/v1/experiments", {
      method: "POST",
      body: JSON.stringify({
        provider: "binance_usdm",
        symbol: "ETHUSDT",
        timeframe: "5m",
        strategy_id: "composite",
        strategy_version: "v1",
        dataset_version: dataset.dataset_version,
        children: children.map((child) => ({
          strategy_id: child.strategy_id,
          version: "v1",
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
    return request<{ candles: Omit<Candle, "provider" | "symbol" | "timeframe">[] }>(
      `/api/v1/experiments/${id}/candles`,
    ).then((payload) => ({
      candles: payload.candles.map((candle) => normalizeCandle({
        ...candle,
        provider: "binance_usdm",
        symbol: "ETHUSDT",
        timeframe: "5m",
      })),
    }));
  },
  experimentTrades(id: string) {
    return request<{ trades: ResearchTrade[] }>(`/api/v1/experiments/${id}/trades`).then((payload) => ({
      trades: payload.trades.map((trade) => ({
        id: `${id}-${trade.sequence_no}`,
        sequence_no: trade.sequence_no,
        side: trade.side,
        entry_time: trade.entry_time,
        exit_time: trade.exit_time ?? trade.entry_time,
        entry_price: trade.entry_price,
        exit_price: trade.exit_price ?? trade.entry_price,
        quantity: trade.quantity,
        pnl: trade.pnl_absolute ?? 0,
        pnl_pct: trade.pnl_percent ?? 0,
        exit_reason: trade.exit_reason ?? "open",
        signal_t: trade.signal_t ?? trade.entry_time,
      })),
    }));
  },
  experimentEquity(id: string) {
    return request<{ equity: ResearchEquityPoint[] }>(`/api/v1/experiments/${id}/equity`).then((payload) => {
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
    return request<{ overlays: ResearchOverlay[] }>(
      `/api/v1/experiments/${id}/overlays`,
    ).then((payload) => ({
      series: [] as OverlaySeries[],
      signal_markers: payload.overlays.map((item) => ({
        t: item.candle_time,
        overlay_type: item.signal.toLowerCase(),
        confidence: item.confidence,
        evidence: item.child_signals,
      })),
      execution_markers: [] as ExecutionMarker[],
    }));
  },
  async startSearch() {
    const dataset = await ensureDataset("5m");
    return request<ResearchSearchRun>("/api/v1/search-runs", {
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
          dataset_version: dataset.dataset_version,
          range_from: "2026-01-01T00:00:00Z",
          range_to: "2026-03-01T00:00:00Z",
        },
        execution: {},
        seed: 42,
        idempotency_key: `search-${Date.now()}`,
      }),
    }).then(normalizeSearchRun);
  },
  searchRun(id: string) {
    return request<ResearchSearchRun>(`/api/v1/search-runs/${id}`).then(normalizeSearchRun);
  },
  searchAction(id: string, action: "pause" | "resume" | "cancel") {
    return request<{ status: string }>(`/api/v1/search-runs/${id}/actions`, {
      method: "POST",
      body: JSON.stringify({ action, command_id: `${action}-${Date.now()}` }),
    });
  },
  leaderboard(sortBy = "score") {
    return request<{ entries: ResearchLeaderboardEntry[] }>(`/api/v1/leaderboard?limit=10&sort_by=${sortBy}`).then(
      (payload) => ({ entries: payload.entries.map((entry) => ({ ...entry, id: entry.entry_id })) }),
    );
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
      return { buy_above: 0.45, sell_below: -0.45, min_items: 3 };
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
