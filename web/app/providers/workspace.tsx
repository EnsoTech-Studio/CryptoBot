"use client";

/* ===========================================================================
   Workspace state
   ---------------------------------------------------------------------------
   Everything that must survive route navigation lives here: market panels and
   their websockets, the active experiment, the search run, leaderboard, news
   and the inspector. The provider is mounted by the workspace layout, so
   moving between /, /backtests, /search, /leaderboard and /news does NOT
   reconnect a socket or drop a poll in flight.
   =========================================================================== */

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { messageFromError } from "../../lib/format";
import {
  api,
  wsURL,
  type Candle,
  type EquityPoint,
  type ExecutionMarker,
  type ExperimentSummary,
  type LeaderboardEntry,
  type NewsItem,
  type OverlayMarker,
  type OverlaySeries,
  type Prediction,
  type SearchRun,
  type Strategy,
  type Trade,
  type User,
} from "../../lib/api";

export type LiveState = "connecting" | "live" | "stale";

export type Panel = {
  id: string;
  title: string;
  timeframe: string;
  strategy: string;
  candles: Candle[];
  series: OverlaySeries[];
  markers: OverlayMarker[];
  lastClosed?: string;
  liveState: LiveState;
  /* Distinguishing "never loaded" from "loaded and empty" is what lets the UI
     show a skeleton instead of claiming data is unavailable. */
  loaded: boolean;
  error?: string;
};

export type ResultBundle = {
  candles: Candle[];
  trades: Trade[];
  equity: EquityPoint[];
  series: OverlaySeries[];
  signalMarkers: OverlayMarker[];
  executionMarkers: ExecutionMarker[];
};

export type Theme = "light" | "dark";
export type NoticeTone = "info" | "warn" | "error";
export type Notice = { text: string; tone: NoticeTone };
export type InspectorTab = "metrics" | "trades" | "provenance";
export type LoadState = "idle" | "loading" | "ready" | "unavailable";

type RealtimeFrame = {
  type?: "subscribed" | "resync_required" | "kline" | "bbo" | "stream_status" | "error";
  sequence?: number;
  seq?: number;
  final?: boolean;
  state?: "connecting" | "stale" | "connected" | "recovered";
  kline?: {
    open_time: string;
    close_time: string;
    open: string;
    high: string;
    low: string;
    close: string;
    volume: string;
    trade_count?: number | string;
  };
};

const panelSeed = [
  { id: "chart-1", title: "Scalp feed", timeframe: "5m", strategy: "composite@v1" },
  { id: "chart-2", title: "Trend check", timeframe: "15m", strategy: "ma_cross@v1" },
  { id: "chart-3", title: "Volatility", timeframe: "1h", strategy: "bollinger@v1" },
  { id: "chart-4", title: "Structure", timeframe: "4h", strategy: "support_resistance@v1" },
];

const compositeChildren = [
  { strategy_id: "ma_cross", weight: 0.34 },
  { strategy_id: "rsi", weight: 0.33 },
  { strategy_id: "support_resistance", weight: 0.33 },
];

type WorkspaceValue = {
  user: User | null;
  strategies: Strategy[];
  panels: Panel[];
  focusIndex: number;
  setFocusIndex: (index: number) => void;
  panelHandlers: (index: number) => { onTimeframe: (tf: string) => void; onStrategy: (s: string) => void };
  latestCandle?: Candle;
  headerChange: number | null;
  readyPanelCount: number;
  signalCount: number;
  activeStrategyCount: number;
  streamLabel: "Live" | "Syncing" | "Degraded";
  experiment: ExperimentSummary | null;
  result: ResultBundle | null;
  search: SearchRun | null;
  leaderboard: LeaderboardEntry[];
  leaderboardState: LoadState;
  news: NewsItem[];
  newsState: LoadState;
  coverage: { items_total: number; items_analyzed: number; items_unanalyzed: number } | null;
  provenance: Record<string, unknown> | null;
  prediction: Prediction | null;
  predictionText: string;
  setPredictionText: (text: string) => void;
  notice: Notice;
  theme: Theme;
  chooseTheme: (theme: Theme) => void;
  inspectorOpen: boolean;
  inspectorTab: InspectorTab;
  setInspectorTab: (tab: InspectorTab) => void;
  openInspector: (tab: InspectorTab) => void;
  closeInspector: () => void;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  runBacktest: () => Promise<void>;
  startSearch: () => Promise<void>;
  searchAction: (action: "pause" | "resume" | "cancel") => Promise<void>;
  refreshStaticData: () => Promise<void>;
  loadProvenance: (id: string) => Promise<void>;
  testSentiment: () => Promise<void>;
};

const WorkspaceContext = createContext<WorkspaceValue | null>(null);

export function useWorkspace(): WorkspaceValue {
  const value = useContext(WorkspaceContext);
  if (!value) throw new Error("useWorkspace must be used inside <WorkspaceProvider>");
  return value;
}

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [panels, setPanels] = useState<Panel[]>(
    panelSeed.map((panel) => ({ ...panel, candles: [], series: [], markers: [], liveState: "connecting", loaded: false })),
  );
  const [focusIndex, setFocusIndex] = useState(0);
  const [activeExperimentId, setActiveExperimentId] = useState<string | null>(null);
  const [experiment, setExperiment] = useState<ExperimentSummary | null>(null);
  const [result, setResult] = useState<ResultBundle | null>(null);
  const [searchId, setSearchId] = useState<string | null>(null);
  const [search, setSearch] = useState<SearchRun | null>(null);
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [leaderboardState, setLeaderboardState] = useState<LoadState>("loading");
  const [news, setNews] = useState<NewsItem[]>([]);
  const [newsState, setNewsState] = useState<LoadState>("loading");
  const [coverage, setCoverage] = useState<WorkspaceValue["coverage"]>(null);
  const [provenance, setProvenance] = useState<Record<string, unknown> | null>(null);
  const [predictionText, setPredictionText] = useState("Ethereum inflows look positive, but volatility risk remains.");
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [notice, setNotice] = useState<Notice>({ text: "Connecting market stream…", tone: "info" });
  const [theme, setTheme] = useState<Theme>("light");
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [inspectorTab, setInspectorTab] = useState<InspectorTab>("metrics");
  const autoOpened = useRef<string | null>(null);
  const panelsRef = useRef(panels);
  useEffect(() => {
    panelsRef.current = panels;
  }, [panels]);

  const latestCandle = useMemo(() => {
    const candles = panels
      .map((panel) => panel.candles.at(-1))
      .filter((candle): candle is Candle => Boolean(candle))
      .sort((a, b) => a.open_time.localeCompare(b.open_time));
    return candles.at(-1);
  }, [panels]);

  const readyPanelCount = panels.filter((panel) => panel.candles.length > 0).length;
  const stalePanelCount = panels.filter((panel) => panel.liveState === "stale").length;
  const signalCount = panels.reduce((sum, panel) => sum + (panel.markers ?? []).length, 0);
  const activeStrategyCount = new Set(panels.map((panel) => panel.strategy)).size;
  const streamLabel = stalePanelCount > 0 ? "Degraded" : readyPanelCount === panels.length ? "Live" : "Syncing";
  const headerChange = latestCandle && latestCandle.open !== 0
    ? ((latestCandle.close - latestCandle.open) / latestCandle.open) * 100
    : null;

  function report(text: string, tone: NoticeTone = "info") {
    setNotice({ text, tone });
  }

  function openInspector(tab: InspectorTab) {
    setInspectorTab(tab);
    setInspectorOpen(true);
  }

  function setPanel(index: number, patch: Partial<Panel>) {
    setPanels((current) => current.map((panel, i) => i === index ? { ...panel, ...patch } : panel));
  }

  async function loadPanel(index: number, override: Partial<Pick<Panel, "timeframe" | "strategy">> = {}) {
    const panel = { ...(panelsRef.current[index] ?? panelSeed[index]), ...override };
    try {
      const [candles, overlays] = await Promise.all([
        api.candles(panel.timeframe, panel.strategy),
        api.overlays(panel.timeframe, panel.strategy),
      ]);
      setPanel(index, {
        candles: candles.candles ?? [],
        series: overlays.series ?? [],
        markers: overlays.markers ?? [],
        lastClosed: overlays.last_closed_at,
        liveState: overlays.is_stale ? "stale" : "live",
        loaded: true,
        error: undefined,
      });
    } catch (error) {
      setPanel(index, {
        candles: [],
        series: [],
        markers: [],
        liveState: "stale",
        loaded: true,
        error: messageFromError(error),
      });
      report(messageFromError(error), "error");
    }
  }

  function panelHandlers(index: number) {
    return {
      onTimeframe: (timeframe: string) => {
        setPanel(index, { timeframe, liveState: "connecting", loaded: false });
        window.setTimeout(() => void loadPanel(index, { timeframe }), 0);
      },
      onStrategy: (strategy: string) => {
        setPanel(index, { strategy, liveState: "connecting", loaded: false });
        window.setTimeout(() => void loadPanel(index, { strategy }), 0);
      },
    };
  }

  async function refreshStaticData() {
    const [rank, newsPayload, aggregate] = await Promise.all([
      api.leaderboard().catch(() => null),
      api.news().catch(() => null),
      api.newsAggregate().catch(() => null),
    ]);
    setLeaderboard(rank?.entries ?? []);
    setLeaderboardState(rank ? "ready" : "unavailable");
    setNews(newsPayload?.items ?? []);
    setNewsState(newsPayload ? "ready" : "unavailable");
    setCoverage(aggregate?.coverage ?? null);
  }

  async function refreshExperiment(id: string) {
    try {
      const summary = await api.experiment(id);
      setExperiment(summary);
      if (summary.status === "completed") {
        const [candles, trades, equity, overlays] = await Promise.all([
          api.experimentCandles(id),
          api.experimentTrades(id),
          api.experimentEquity(id),
          api.experimentOverlays(id),
        ]);
        setResult({
          candles: candles.candles ?? [],
          trades: trades.trades ?? [],
          equity: equity.points ?? [],
          series: overlays.series ?? [],
          signalMarkers: overlays.signal_markers ?? [],
          executionMarkers: overlays.execution_markers ?? [],
        });
        if (autoOpened.current !== id) {
          autoOpened.current = id;
          openInspector("metrics");
        }
        void refreshStaticData();
      }
    } catch (error) {
      report(messageFromError(error), "error");
    }
  }

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      setTheme("light");
      window.localStorage.setItem("crypto-lab-theme", "light");
      document.documentElement.dataset.theme = "light";
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  function chooseTheme(next: Theme) {
    setTheme(next);
    window.localStorage.setItem("crypto-lab-theme", next);
    document.documentElement.dataset.theme = next;
  }

  useEffect(() => {
    api.me()
      .then((payload) => setUser(payload.user))
      .catch(() => report("Sign in to run experiments and search loops.", "warn"));
    api.strategies().then((payload) => setStrategies(payload.strategies ?? [])).catch(() => undefined);
    // These are async fetches whose setState lands in a later microtask, i.e.
    // legitimate external-system synchronization rather than a render cascade.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refreshStaticData();
    panelSeed.forEach((_, index) => void loadPanel(index));
    // Bootstrap once on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const subscriptionSignature = panels.map((panel) => `${panel.timeframe}:${panel.strategy}`).join("|");

  useEffect(() => {
    let stopped = false;
    const sockets = new Set<WebSocket>();
    const reconnectTimers = new Set<number>();
    panelsRef.current.forEach((panel, index) => {
      const key = `binance_usdm|ETHUSDT|${panel.timeframe}|${panel.strategy}|sha256:${"4".repeat(64)}`;
      let lastSequence = 0;
      let reconnectAttempt = 0;

      const connect = () => {
        if (stopped) return;
        const socket = new WebSocket(wsURL(key));
        sockets.add(socket);
        socket.onopen = () => {
          reconnectAttempt = 0;
          socket.send(JSON.stringify({
            action: "subscribe",
            key,
            req: `${panel.id}-${Date.now()}`,
            last_sequence: lastSequence,
          }));
          setPanel(index, { liveState: "live" });
        };
        socket.onmessage = (event) => {
          const frame = JSON.parse(event.data) as RealtimeFrame;
          if (frame.type === "subscribed") {
            if (lastSequence === 0) lastSequence = frame.sequence ?? frame.seq ?? 0;
            return;
          }
          if (frame.type === "resync_required") {
            lastSequence = 0;
            setPanel(index, { liveState: "connecting" });
            void loadPanel(index);
            socket.close();
            return;
          }
          const sequence = frame.sequence ?? frame.seq;
          if (sequence !== undefined) {
            if (sequence <= lastSequence) return;
            if (lastSequence > 0 && sequence !== lastSequence + 1) {
              lastSequence = 0;
              setPanel(index, { liveState: "connecting" });
              void loadPanel(index);
              socket.close();
              return;
            }
            lastSequence = sequence;
          }
          if (frame.type === "kline" && frame.kline) {
            const kline = frame.kline;
            const candle: Candle = {
              provider: "binance_usdm",
              symbol: "ETHUSDT",
              timeframe: panel.timeframe,
              open_time: kline.open_time,
              close_time: kline.close_time,
              open: Number(kline.open),
              high: Number(kline.high),
              low: Number(kline.low),
              close: Number(kline.close),
              volume: Number(kline.volume),
              trade_count: Number(kline.trade_count ?? 0),
            };
            setPanels((current) => current.map((p, i) => i === index
              ? {
                  ...p,
                  candles: upsertCandle(p.candles, candle),
                  lastClosed: frame.final ? candle.close_time : p.lastClosed,
                  liveState: "live",
                  loaded: true,
                }
              : p));
          }
          if (frame.type === "stream_status") {
            setPanel(index, {
              liveState: frame.state === "stale" || frame.state === "connecting" ? "stale" : "live",
            });
          }
        };
        socket.onerror = () => setPanel(index, { liveState: "stale" });
        socket.onclose = () => {
          sockets.delete(socket);
          if (stopped) return;
          setPanel(index, { liveState: "stale" });
          const delay = Math.min(10_000, 500 * (2 ** reconnectAttempt));
          reconnectAttempt += 1;
          const timer = window.setTimeout(() => {
            reconnectTimers.delete(timer);
            connect();
          }, delay);
          reconnectTimers.add(timer);
        };
      };
      connect();
    });
    return () => {
      stopped = true;
      reconnectTimers.forEach((timer) => window.clearTimeout(timer));
      sockets.forEach((socket) => socket.close());
    };
    // Reconnect only when a subscription key changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subscriptionSignature]);

  useEffect(() => {
    if (!activeExperimentId) return;
    const settled = experiment?.status === "completed" || experiment?.status === "failed" || experiment?.status === "cancelled";
    if (settled) return;
    const timer = window.setInterval(() => void refreshExperiment(activeExperimentId), 1600);
    // Async fetch; setState resolves in a later microtask, not synchronously.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refreshExperiment(activeExperimentId);
    return () => window.clearInterval(timer);
    // Poll only while the run is in flight.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeExperimentId, experiment?.status]);

  useEffect(() => {
    if (!searchId) return;
    const timer = window.setInterval(() => {
      api.searchRun(searchId).then(setSearch).catch(() => undefined);
      void refreshStaticData();
    }, 1800);
    api.searchRun(searchId).then(setSearch).catch(() => undefined);
    return () => window.clearInterval(timer);
  }, [searchId]);

  useEffect(() => {
    if (!inspectorOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setInspectorOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [inspectorOpen]);

  const value: WorkspaceValue = {
    user,
    strategies,
    panels,
    focusIndex,
    setFocusIndex,
    panelHandlers,
    latestCandle,
    headerChange,
    readyPanelCount,
    signalCount,
    activeStrategyCount,
    streamLabel,
    experiment,
    result,
    search,
    leaderboard,
    leaderboardState,
    news,
    newsState,
    coverage,
    provenance,
    prediction,
    predictionText,
    setPredictionText,
    notice,
    theme,
    chooseTheme,
    inspectorOpen,
    inspectorTab,
    setInspectorTab,
    openInspector,
    closeInspector: () => setInspectorOpen(false),
    async login(email, password) {
      try {
        const payload = await api.login(email, password);
        setUser(payload.user);
        report(`Signed in as ${payload.user.email}`);
      } catch (error) {
        report(messageFromError(error), "error");
      }
    },
    async logout() {
      try {
        await api.logout();
        setUser(null);
        report("Signed out.");
      } catch (error) {
        report(messageFromError(error), "error");
      }
    },
    async runBacktest() {
      try {
        const accepted = await api.createExperiment(compositeChildren);
        setActiveExperimentId(accepted.experiment_id);
        setResult(null);
        report(`Backtest queued: ${accepted.run_id.slice(0, 8)}`);
      } catch (error) {
        report(messageFromError(error), "error");
      }
    },
    async startSearch() {
      try {
        const accepted = await api.startSearch();
        setSearchId(accepted.search_run_id);
        report(`Search run started: ${accepted.search_run_id.slice(0, 8)}`);
      } catch (error) {
        report(messageFromError(error), "error");
      }
    },
    async searchAction(action) {
      if (!search) return;
      try {
        await api.searchAction(search.search_run_id, action);
        setSearch(await api.searchRun(search.search_run_id));
        report(`Search ${action} accepted.`);
      } catch (error) {
        report(messageFromError(error), "error");
      }
    },
    refreshStaticData,
    async loadProvenance(id) {
      try {
        setProvenance(await api.provenance(id));
        openInspector("provenance");
      } catch (error) {
        report(messageFromError(error), "error");
      }
    },
    async testSentiment() {
      try {
        setPrediction(await api.predict(predictionText));
      } catch (error) {
        report(messageFromError(error), "error");
      }
    },
  };

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

function upsertCandle(candles: Candle[], candle: Candle): Candle[] {
  const next = candles.filter((item) => item.open_time !== candle.open_time);
  next.push(candle);
  return next.sort((a, b) => a.open_time.localeCompare(b.open_time)).slice(-180);
}
