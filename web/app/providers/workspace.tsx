"use client";

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
  type MarketPair,
  type MarketSelection,
  type MarketStatus,
  type NewsItem,
  type OverlayMarker,
  type OverlaySeries,
  type Prediction,
  type SearchRun,
  type Strategy,
  type Trade,
  type User,
} from "../../lib/api";
import {
  DEFAULT_MARKET,
  appendMarketEvent,
  buildSubscriptionKey,
  marketKey,
  normalizeRealtimeFrame,
  upsertCandle,
  type RecentMarketEvent,
} from "../../lib/market";
import {
  MOCK_MARKET_PAIRS,
  createMockPanelData,
  createMockTicks,
  displayTickFromBbo,
  updateMockCandle,
  type DisplayTick,
} from "../../lib/realtime-mock";

export type LiveState = "connecting" | "live" | "stale" | "paused";
export type ConnectionLabel = "Live" | "Syncing" | "Degraded" | "Paused" | "Unavailable" | "Mock";
export type DataMode = "live" | "mock";

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
  loaded: boolean;
  historyLoading: boolean;
  historyLimit: number;
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

const preferredTimeframes = ["1m", "5m", "15m", "1h"];
const panelSeed = preferredTimeframes.map((timeframe, index) => ({
  id: `chart-${index + 1}`,
  title: `Market view ${index + 1}`,
  timeframe,
  strategy: "ma_cross@v1",
}));

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
  panelHandlers: (index: number) => { onTimeframe: (tf: string) => void; onStrategy: (strategy: string) => void };
  latestCandle?: Candle;
  headerChange: number | null;
  readyPanelCount: number;
  signalCount: number;
  activeStrategyCount: number;
  streamLabel: ConnectionLabel;
  dataMode: DataMode;
  marketPairs: MarketPair[];
  marketPairsState: LoadState;
  selectedMarket: MarketSelection;
  selectedPair?: MarketPair;
  availableTimeframes: string[];
  selectMarket: (market: MarketSelection) => void;
  retryMarketPairs: () => Promise<void>;
  realtimeEnabled: boolean;
  setRealtimeEnabled: (enabled: boolean) => void;
  recentMarketEvents: RecentMarketEvent[];
  recentTicks: DisplayTick[];
  lastFrameAt?: string;
  latencyMs: number | null;
  reconnectCount: number;
  marketStatus: MarketStatus | null;
  marketStatusState: LoadState;
  loadHistory: (index: number) => Promise<void>;
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

function createPanels(timeframes = preferredTimeframes, realtimeEnabled = true): Panel[] {
  const safeTimeframes = timeframes.length > 0 ? timeframes : preferredTimeframes;
  return safeTimeframes.slice(0, panelSeed.length).map((timeframe, index) => ({
    ...panelSeed[index],
    timeframe,
    candles: [],
    series: [],
    markers: [],
    liveState: realtimeEnabled ? "connecting" : "paused",
    loaded: false,
    historyLoading: false,
    historyLimit: 180,
  }));
}

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [panels, setPanels] = useState<Panel[]>(() => createPanels());
  const [focusIndex, setFocusIndex] = useState(0);
  const [marketPairs, setMarketPairs] = useState<MarketPair[]>([]);
  const [marketPairsState, setMarketPairsState] = useState<LoadState>("loading");
  const [dataMode, setDataMode] = useState<DataMode>("live");
  const [selectedMarket, setSelectedMarket] = useState<MarketSelection>(DEFAULT_MARKET);
  const [realtimeEnabled, setRealtimeEnabledState] = useState(true);
  const [recentMarketEvents, setRecentMarketEvents] = useState<RecentMarketEvent[]>([]);
  const [recentTicks, setRecentTicks] = useState<DisplayTick[]>([]);
  const [lastFrameAt, setLastFrameAt] = useState<string>();
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [socketReconnectCount, setSocketReconnectCount] = useState(0);
  const [marketStatus, setMarketStatus] = useState<MarketStatus | null>(null);
  const [marketStatusState, setMarketStatusState] = useState<LoadState>("loading");
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
  const panelRequestIds = useRef([0, 0, 0, 0]);
  const panelsRef = useRef(panels);
  const selectedMarketRef = useRef(selectedMarket);
  const realtimeEnabledRef = useRef(realtimeEnabled);
  const dataModeRef = useRef<DataMode>(dataMode);
  const mockTickRef = useRef(0);
  useEffect(() => {
    panelsRef.current = panels;
  }, [panels]);
  useEffect(() => {
    selectedMarketRef.current = selectedMarket;
  }, [selectedMarket]);
  useEffect(() => {
    realtimeEnabledRef.current = realtimeEnabled;
  }, [realtimeEnabled]);
  useEffect(() => {
    dataModeRef.current = dataMode;
  }, [dataMode]);

  const selectedPair = useMemo(
    () => marketPairs.find((pair) => marketKey(pair) === marketKey(selectedMarket)),
    [marketPairs, selectedMarket],
  );
  const availableTimeframes = useMemo(() => {
    const supported = selectedPair?.timeframes?.filter(Boolean) ?? [];
    if (supported.length === 0) return preferredTimeframes;
    return [...supported].sort((a, b) => timeframeOrder(a) - timeframeOrder(b));
  }, [selectedPair]);

  const latestCandle = useMemo(() => {
    const candles = panels
      .map((panel) => panel.candles.at(-1))
      .filter((candle): candle is Candle => Boolean(candle))
      .sort((a, b) => a.open_time.localeCompare(b.open_time));
    return candles.at(-1);
  }, [panels]);

  const readyPanelCount = panels.filter((panel) => panel.candles.length > 0).length;
  const stalePanelCount = panels.filter((panel) => panel.liveState === "stale").length;
  const livePanelCount = panels.filter((panel) => panel.liveState === "live").length;
  const signalCount = panels.reduce((sum, panel) => sum + panel.markers.length, 0);
  const activeStrategyCount = new Set(panels.map((panel) => panel.strategy)).size;
  const streamLabel: ConnectionLabel = !realtimeEnabled
    ? "Paused"
    : dataMode === "mock"
      ? "Mock"
      : marketPairsState === "unavailable" && readyPanelCount === 0
      ? "Unavailable"
      : stalePanelCount > 0 || marketStatus?.stale
        ? "Degraded"
        : readyPanelCount === panels.length && livePanelCount === panels.length
          ? "Live"
          : "Syncing";
  const headerChange = latestCandle && latestCandle.open !== 0
    ? ((latestCandle.close - latestCandle.open) / latestCandle.open) * 100
    : null;
  const reconnectCount = Math.max(socketReconnectCount, marketStatus?.reconnect_count ?? 0);

  function report(text: string, tone: NoticeTone = "info") {
    setNotice({ text, tone });
  }

  function openInspector(tab: InspectorTab) {
    setInspectorTab(tab);
    setInspectorOpen(true);
  }

  function setPanel(index: number, patch: Partial<Panel>) {
    setPanels((current) => current.map((panel, panelIndex) => panelIndex === index ? { ...panel, ...patch } : panel));
  }

  function activateMockMode(market: MarketSelection = selectedMarketRef.current) {
    const catalogHasMarket = MOCK_MARKET_PAIRS.some((pair) => marketKey(pair) === marketKey(market));
    const mockPairs = catalogHasMarket ? MOCK_MARKET_PAIRS : [{
      provider: market.provider,
      symbol: market.symbol.toUpperCase(),
      base_asset: market.symbol.toUpperCase().replace(/USDT$/, ""),
      quote_asset: "USDT",
      timeframes: ["1m", "5m", "15m", "1h", "4h"],
    }, ...MOCK_MARKET_PAIRS];
    dataModeRef.current = "mock";
    setDataMode("mock");
    setMarketPairs(mockPairs);
    setMarketPairsState("ready");
    setRecentTicks(createMockTicks(market.symbol));
    setLatencyMs(24);
    setLastFrameAt("2025-04-29T10:45:23.000Z");
    setMarketStatus({
      provider: "deterministic_mock",
      symbol: market.symbol.toUpperCase(),
      timeframe: panelsRef.current[0]?.timeframe ?? "1m",
      stale: false,
      last_closed_at: "2025-04-29T10:45:23.000Z",
      last_sequence: 1,
      reconnect_count: 0,
    });
    setMarketStatusState("ready");
    report("Backend market services unavailable. Showing clearly labeled deterministic mock data.", "warn");
  }

  async function loadPanel(
    index: number,
    override: Partial<Pick<Panel, "timeframe" | "strategy">> = {},
    limit = 180,
    explicitMarket: MarketSelection = selectedMarketRef.current,
  ) {
    const panel = { ...(panelsRef.current[index] ?? panelSeed[index]), ...override };
    const requestId = ++panelRequestIds.current[index];
    const requestMarketKey = marketKey(explicitMarket);
    const isHistoryRequest = limit > 180;
    if (isHistoryRequest) setPanel(index, { historyLoading: true, error: undefined });

    if (dataModeRef.current === "mock") {
      const mock = createMockPanelData(explicitMarket, panel.timeframe, limit);
      setPanel(index, {
        timeframe: panel.timeframe,
        strategy: panel.strategy,
        ...mock,
        lastClosed: mock.candles.at(-1)?.close_time,
        liveState: realtimeEnabledRef.current ? "live" : "paused",
        loaded: true,
        historyLoading: false,
        historyLimit: limit,
        error: undefined,
      });
      return;
    }

    const [candlesResult, overlaysResult] = await Promise.allSettled([
      api.candles(explicitMarket, panel.timeframe, limit),
      api.overlays(explicitMarket, panel.timeframe, panel.strategy, limit),
    ]);
    if (requestId !== panelRequestIds.current[index] || requestMarketKey !== marketKey(selectedMarketRef.current)) return;

    if (candlesResult.status === "rejected") {
      activateMockMode(explicitMarket);
      const mock = createMockPanelData(explicitMarket, panel.timeframe, limit);
      setPanel(index, {
        timeframe: panel.timeframe,
        strategy: panel.strategy,
        ...mock,
        lastClosed: mock.candles.at(-1)?.close_time,
        liveState: realtimeEnabledRef.current ? "live" : "paused",
        loaded: true,
        historyLoading: false,
        historyLimit: limit,
        error: undefined,
      });
      return;
    }

    const overlayPayload = overlaysResult.status === "fulfilled" ? overlaysResult.value : null;
    const overlayError = overlaysResult.status === "rejected"
      ? `Overlay unavailable: ${messageFromError(overlaysResult.reason)}`
      : undefined;
    setPanel(index, {
      timeframe: panel.timeframe,
      strategy: panel.strategy,
      candles: candlesResult.value.candles ?? [],
      series: overlayPayload?.series ?? [],
      markers: overlayPayload?.markers ?? [],
      lastClosed: overlayPayload?.last_closed_at,
      liveState: !realtimeEnabledRef.current ? "paused" : overlayPayload?.is_stale ? "stale" : "connecting",
      loaded: true,
      historyLoading: false,
      historyLimit: limit,
      error: overlayError,
    });
  }

  function panelHandlers(index: number) {
    return {
      onTimeframe: (timeframe: string) => {
        setPanel(index, {
          timeframe,
          candles: [],
          series: [],
          markers: [],
          liveState: realtimeEnabled ? "connecting" : "paused",
          loaded: false,
          historyLimit: 180,
          error: undefined,
        });
        window.setTimeout(() => void loadPanel(index, { timeframe }), 0);
      },
      onStrategy: (strategy: string) => {
        setPanel(index, { strategy, liveState: realtimeEnabled ? "connecting" : "paused", loaded: false, error: undefined });
        window.setTimeout(() => void loadPanel(index, { strategy }), 0);
      },
    };
  }

  async function retryMarketPairs() {
    setMarketPairsState("loading");
    try {
      const payload = await api.marketPairs();
      const pairs = (payload.pairs ?? []).map((pair) => ({
        ...pair,
        symbol: pair.symbol.toUpperCase(),
        timeframes: pair.timeframes ?? [],
      }));
      if (pairs.length === 0) throw new Error("Market pair catalog is empty");
      dataModeRef.current = "live";
      setDataMode("live");
      setMarketPairs(pairs);
      setMarketPairsState("ready");

      const persisted = readPersistedMarket();
      const candidate = persisted && pairs.some((pair) => marketKey(pair) === marketKey(persisted))
        ? persisted
        : pairs.find((pair) => marketKey(pair) === marketKey(selectedMarketRef.current)) ?? pairs[0];
      if (candidate) setSelectedMarket({ provider: candidate.provider, symbol: candidate.symbol });
    } catch {
      activateMockMode(DEFAULT_MARKET);
      setSelectedMarket(DEFAULT_MARKET);
    }
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
        const resultMarket = { provider: summary.provider, symbol: summary.symbol };
        const [candles, trades, equity, overlays] = await Promise.all([
          api.experimentCandles(id, resultMarket, summary.timeframe),
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
    const bootstrapTimer = window.setTimeout(() => {
      void refreshStaticData();
      void retryMarketPairs();
    }, 0);
    return () => window.clearTimeout(bootstrapTimer);
    // Bootstrap once; retries are user-driven after the initial request.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const marketSignature = marketKey(selectedMarket);
  const timeframeSignature = availableTimeframes.join("|");
  useEffect(() => {
    const resetFrame = window.requestAnimationFrame(() => {
      const nextPanels = createPanels(availableTimeframes, realtimeEnabled);
      setPanels(nextPanels);
      setFocusIndex(0);
      setRecentMarketEvents([]);
      setRecentTicks(dataModeRef.current === "mock" ? createMockTicks(selectedMarket.symbol) : []);
      setLastFrameAt(undefined);
      setLatencyMs(null);
      setSocketReconnectCount(0);
      setMarketStatus(null);
      window.localStorage.setItem("crypto-lab-market", JSON.stringify(selectedMarket));
      nextPanels.forEach((panel, index) => void loadPanel(index, {
        timeframe: panel.timeframe,
        strategy: panel.strategy,
      }, 180, selectedMarket));
    });
    return () => window.cancelAnimationFrame(resetFrame);
    // Pair or supported timeframe changes require a clean, guarded reload.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [marketSignature, timeframeSignature, dataMode]);

  const currentPrimaryTimeframe = panels[0]?.timeframe;
  const primaryTimeframe = currentPrimaryTimeframe && availableTimeframes.includes(currentPrimaryTimeframe)
    ? currentPrimaryTimeframe
    : availableTimeframes[0] ?? preferredTimeframes[0];
  useEffect(() => {
    if (dataMode === "mock") return;
    let stopped = false;
    let timer: number | undefined;
    const refresh = async () => {
      setMarketStatusState("loading");
      try {
        const status = await api.marketStatus(selectedMarketRef.current, primaryTimeframe);
        if (stopped) return;
        if (!status || typeof status.reconnect_count !== "number") throw new Error("Invalid market status response");
        setMarketStatus(status);
        setMarketStatusState("ready");
        setSocketReconnectCount((current) => Math.max(current, status.reconnect_count));
        if (status.last_closed_at) setLastFrameAt((current) => current ?? status.last_closed_at ?? undefined);
      } catch {
        if (!stopped) setMarketStatusState("unavailable");
      }
      if (!stopped) timer = window.setTimeout(refresh, 15_000);
    };
    void refresh();
    return () => {
      stopped = true;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [dataMode, marketSignature, primaryTimeframe]);

  const subscriptionSignature = panels.map((panel) => `${panel.timeframe}:${panel.strategy}`).join("|");
  useEffect(() => {
    if (!realtimeEnabled || dataMode === "mock" || marketPairsState !== "ready") return;

    let stopped = false;
    const sockets = new Set<WebSocket>();
    const reconnectTimers = new Set<number>();
    panelsRef.current.forEach((panel, index) => {
      const key = buildSubscriptionKey(selectedMarket, panel.timeframe, panel.strategy);
      let lastSequence = 0;
      let reconnectAttempt = 0;

      const connect = () => {
        if (stopped) return;
        setPanel(index, { liveState: "connecting" });
        const socket = new WebSocket(wsURL(key));
        sockets.add(socket);
        socket.onopen = () => {
          socket.send(JSON.stringify({
            action: "subscribe",
            key,
            req: `${panel.id}-${Date.now()}`,
            last_sequence: lastSequence,
          }));
        };
        socket.onmessage = (event) => {
          if (!realtimeEnabledRef.current || marketKey(selectedMarketRef.current) !== marketKey(selectedMarket)) return;
          let rawFrame: unknown;
          try {
            rawFrame = JSON.parse(event.data);
          } catch {
            return;
          }
          const frame = normalizeRealtimeFrame(rawFrame, selectedMarket);
          if (frame.type === "subscribed") {
            if (lastSequence === 0) lastSequence = frame.sequence ?? 0;
            reconnectAttempt = 0;
            setPanel(index, { liveState: "live" });
            return;
          }
          if (frame.type === "resync_required") {
            lastSequence = 0;
            setPanel(index, { liveState: "connecting" });
            void loadPanel(index, {}, panelsRef.current[index]?.historyLimit ?? 180, selectedMarket);
            socket.close();
            return;
          }

          const sequence = frame.sequence;
          if (sequence !== undefined) {
            if (sequence <= lastSequence) return;
            if (lastSequence > 0 && sequence !== lastSequence + 1) {
              lastSequence = 0;
              setPanel(index, { liveState: "connecting" });
              void loadPanel(index, {}, panelsRef.current[index]?.historyLimit ?? 180, selectedMarket);
              socket.close();
              return;
            }
            lastSequence = sequence;
          }

          if (frame.serverTime) {
            const serverTime = Date.parse(frame.serverTime);
            if (Number.isFinite(serverTime)) setLatencyMs(Math.max(0, Date.now() - serverTime));
          }
          if (frame.serverTime || frame.occurredAt) setLastFrameAt(frame.serverTime ?? frame.occurredAt);

          if (frame.type === "kline" && frame.kline) {
            const candle: Candle = {
              provider: selectedMarket.provider,
              symbol: selectedMarket.symbol,
              timeframe: panel.timeframe,
              open_time: frame.kline.openTime,
              close_time: frame.kline.closeTime,
              open: frame.kline.open,
              high: frame.kline.high,
              low: frame.kline.low,
              close: frame.kline.close,
              volume: frame.kline.volume,
              trade_count: frame.kline.tradeCount,
            };
            setPanels((current) => current.map((currentPanel, panelIndex) => panelIndex === index
              ? {
                  ...currentPanel,
                  candles: upsertCandle(currentPanel.candles, candle),
                  lastClosed: frame.final ? candle.close_time : currentPanel.lastClosed,
                  liveState: "live",
                  loaded: true,
                }
              : currentPanel));
          }
          if (frame.type === "bbo" && frame.bbo) {
            setRecentMarketEvents((current) => appendMarketEvent(current, frame.bbo!));
            setRecentTicks((current) => [
              displayTickFromBbo(
                frame.bbo!.id,
                frame.bbo!.occurredAt,
                frame.bbo!.bid,
                frame.bbo!.ask,
                frame.bbo!.bidQty,
                frame.bbo!.askQty,
              ),
              ...current.filter((item) => item.id !== frame.bbo!.id),
            ].slice(0, 50));
            setPanel(index, { liveState: "live" });
          }
          if (frame.type === "stream_status") {
            if (frame.reconnectNo !== undefined) {
              setSocketReconnectCount((current) => Math.max(current, frame.reconnectNo!));
            }
            setPanel(index, {
              liveState: frame.state === "stale" || frame.state === "connecting" ? "stale" : "live",
            });
          }
        };
        socket.onerror = () => {
          if (realtimeEnabledRef.current && marketKey(selectedMarketRef.current) === marketKey(selectedMarket)) {
            setPanel(index, { liveState: "stale" });
          }
        };
        socket.onclose = () => {
          sockets.delete(socket);
          if (stopped || !realtimeEnabledRef.current || marketKey(selectedMarketRef.current) !== marketKey(selectedMarket)) return;
          setPanel(index, { liveState: "stale" });
          reconnectAttempt += 1;
          setSocketReconnectCount((current) => Math.max(current, reconnectAttempt));
          const delay = Math.min(10_000, 500 * (2 ** (reconnectAttempt - 1)));
          const reconnectTimer = window.setTimeout(() => {
            reconnectTimers.delete(reconnectTimer);
            connect();
          }, delay);
          reconnectTimers.add(reconnectTimer);
        };
      };
      connect();
    });
    return () => {
      stopped = true;
      reconnectTimers.forEach((timer) => window.clearTimeout(timer));
      sockets.forEach((socket) => socket.close());
    };
    // Socket lifecycle is keyed by the exact market subscription signature.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataMode, marketPairsState, marketSignature, realtimeEnabled, subscriptionSignature]);

  useEffect(() => {
    if (dataMode !== "mock") return;
    if (!realtimeEnabled) return;

    const timer = window.setInterval(() => {
      mockTickRef.current += 1;
      const tick = mockTickRef.current;
      const nextPanels = panelsRef.current.map((panel) => {
        const last = panel.candles.at(-1);
        if (!last) return panel;
        const nextCandle = updateMockCandle(last, tick + timeframeOrder(panel.timeframe));
        return {
          ...panel,
          candles: [...panel.candles.slice(0, -1), nextCandle],
          liveState: "live" as const,
        };
      });
      setPanels(nextPanels);
      const price = nextPanels[0]?.candles.at(-1)?.close;
      const now = new Date().toISOString();
      if (price != null) {
        setRecentTicks((current) => [{
          id: `mock-live-${tick}`,
          occurredAt: now,
          price,
          quantity: Number((0.008 + (tick % 13) * 0.003).toFixed(3)),
          side: tick % 3 === 0 ? "sell" as const : "buy" as const,
        }, ...current].slice(0, 50));
      }
      setLastFrameAt(now);
      setLatencyMs(22 + (tick % 9));
    }, 1_600);
    return () => window.clearInterval(timer);
  }, [dataMode, marketSignature, realtimeEnabled, selectedMarket.symbol]);

  useEffect(() => {
    if (!activeExperimentId) return;
    const settled = experiment?.status === "completed" || experiment?.status === "failed" || experiment?.status === "cancelled";
    if (settled) return;
    const timer = window.setInterval(() => void refreshExperiment(activeExperimentId), 1600);
    const refreshTimer = window.setTimeout(() => void refreshExperiment(activeExperimentId), 0);
    return () => {
      window.clearInterval(timer);
      window.clearTimeout(refreshTimer);
    };
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
    dataMode,
    marketPairs,
    marketPairsState,
    selectedMarket,
    selectedPair,
    availableTimeframes,
    selectMarket(market) {
      setSelectedMarket({ provider: market.provider, symbol: market.symbol.toUpperCase() });
    },
    retryMarketPairs,
    realtimeEnabled,
    setRealtimeEnabled(enabled) {
      realtimeEnabledRef.current = enabled;
      setRealtimeEnabledState(enabled);
      setPanels((current) => current.map((panel) => ({
        ...panel,
        liveState: enabled ? (dataModeRef.current === "mock" ? "live" : "connecting") : "paused",
      })));
      report(enabled ? "Realtime stream resumed." : "Realtime stream paused.");
    },
    recentMarketEvents,
    recentTicks,
    lastFrameAt,
    latencyMs,
    reconnectCount,
    marketStatus,
    marketStatusState,
    loadHistory(index) {
      return loadPanel(index, {}, 1_000);
    },
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
        const accepted = await api.createExperiment(compositeChildren, selectedMarket, panels[0]?.timeframe ?? "5m");
        setActiveExperimentId(accepted.experiment_id);
        setResult(null);
        report(`Backtest queued: ${accepted.run_id.slice(0, 8)}`);
      } catch (error) {
        report(messageFromError(error), "error");
      }
    },
    async startSearch() {
      try {
        const accepted = await api.startSearch(selectedMarket, panels[0]?.timeframe ?? "5m");
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

function timeframeOrder(timeframe: string) {
  const match = timeframe.match(/^(\d+)([mhdw])$/i);
  if (!match) return Number.MAX_SAFE_INTEGER;
  const unitMinutes: Record<string, number> = { m: 1, h: 60, d: 1_440, w: 10_080 };
  return Number(match[1]) * (unitMinutes[match[2].toLowerCase()] ?? Number.MAX_SAFE_INTEGER);
}

function readPersistedMarket(): MarketSelection | null {
  try {
    const value = JSON.parse(window.localStorage.getItem("crypto-lab-market") ?? "null") as Partial<MarketSelection> | null;
    if (!value?.provider || !value.symbol) return null;
    return { provider: value.provider, symbol: value.symbol.toUpperCase() };
  } catch {
    return null;
  }
}
