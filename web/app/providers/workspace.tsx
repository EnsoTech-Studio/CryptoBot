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
  DEFAULT_EXECUTION,
  type Candle,
  type DiscoveryArchive,
  type EquityPoint,
  type ExecutionMarker,
  type ExecutionSettings,
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
  type StrategyDraft,
  type StrategyExecution,
  type Trade,
  type User,
} from "../../lib/api";
import { normalizeWeights, type DiscoveryDraft } from "../../lib/discovery";
import {
  DEFAULT_MARKET,
  DEFAULT_PANEL_TIMEFRAMES,
  PANEL_BOOTSTRAP_CANDLE_LIMIT,
  REFERENCE_MARKET,
  appendMarketEvent,
  buildSubscriptionKey,
  mergeOverlayDelta,
  marketKey,
  normalizeRealtimeFrame,
  upsertCandle,
  type RecentMarketEvent,
  type RealtimeOverlaySeries,
} from "../../lib/market";
import {
  MOCK_MARKET_PAIRS,
  createMockPanelData,
  createMockTicks,
  displayTickFromBbo,
  updateMockCandle,
  type DisplayTick,
} from "../../lib/realtime-mock";

export type LiveState = "connecting" | "live" | "stale" | "unavailable" | "paused";
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
  lastFrameAt?: string;
  latencyMs: number | null;
  loaded: boolean;
  historyLoading: boolean;
  historyLimit: number;
  error?: string;
};

export type ResultBundle = {
  candles: Candle[];
  trades: Trade[];
  nextTradeCursor: number | null;
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

const requiredTimeframes = ["1m", "5m", "15m", "1h", "4h", "1d"];
const knownTimeframes = ["1s", ...requiredTimeframes];
const MIN_REALTIME_CHARTS = 1;
const MAX_REALTIME_CHARTS = 4;
const referenceModeEnabled = process.env.NEXT_PUBLIC_UI_REFERENCE_MODE === "true";
const DISCOVERY_SESSION_KEY = "crypto-lab-discovery-session";
const marketMockEnabled = process.env.NEXT_PUBLIC_ENABLE_MARKET_MOCK === "true" || referenceModeEnabled;
const panelSeed = DEFAULT_PANEL_TIMEFRAMES.map((timeframe, index) => ({
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
  strategyDrafts: StrategyDraft[];
  panels: Panel[];
  chartCount: number;
  setChartCount: (count: number) => void;
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
  discoverySessions: SearchRun[];
  discoverySessionsState: LoadState;
  /* The API reports tested/generated but never echoes back the draft that
     started the run. Snapshotting it keeps progress honest: the denominator and
     the strategy names shown beside a score belong to the submitted run, not to
     whatever the user edited afterwards. */
  submittedDraft: DiscoveryDraft | null;
  leaderboard: LeaderboardEntry[];
  leaderboardState: LoadState;
  discoveryArchive: DiscoveryArchive | null;
  discoveryArchiveState: LoadState;
  news: NewsItem[];
  newsState: LoadState;
  coverage: { items_total: number; items_analyzed: number; items_unanalyzed: number } | null;
  /* Percentages are derived from the aggregate's label counts so the News
     screen never hardcodes a sentiment split. */
  newsDistribution: { positive: number; neutral: number; negative: number } | null;
  newsAverageScore: number | null;
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
  register: (email: string, password: string, displayName: string) => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  runBacktest: (children?: StrategyExecution[], execution?: ExecutionSettings, timeframe?: string, range?: { from: string; to: string }, market?: MarketSelection, datasetVersion?: string) => Promise<boolean>;
  startSearch: (draft: DiscoveryDraft) => Promise<void>;
  searchAction: (action: "pause" | "resume" | "cancel") => Promise<void>;
  selectDiscoverySession: (id: string) => Promise<void>;
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

function createPanels(timeframes = requiredTimeframes, realtimeEnabled = true, seedMock = false): Panel[] {
  const panelMarket = seedMock ? REFERENCE_MARKET : DEFAULT_MARKET;
  const available = timeframes.length > 0 ? timeframes : requiredTimeframes;
  const defaults = DEFAULT_PANEL_TIMEFRAMES.filter((timeframe) => available.includes(timeframe));
  const fallbacks = available.filter((timeframe) => !defaults.includes(timeframe));
  const chartTimeframes = [...defaults, ...fallbacks].slice(0, panelSeed.length);
  return panelSeed.map((seed, index) => ({
    ...seed,
    timeframe: chartTimeframes[index] ?? seed.timeframe,
    ...(seedMock ? createMockPanelData(panelMarket, chartTimeframes[index] ?? seed.timeframe, PANEL_BOOTSTRAP_CANDLE_LIMIT) : { candles: [], series: [], markers: [] }),
    liveState: seedMock ? (realtimeEnabled ? "live" : "paused") : realtimeEnabled ? "connecting" : "paused",
    lastFrameAt: seedMock ? "2025-04-29T10:45:38.123Z" : undefined,
    latencyMs: seedMock ? 102 : null,
    loaded: seedMock,
    historyLoading: false,
    historyLimit: PANEL_BOOTSTRAP_CANDLE_LIMIT,
  }));
}

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [strategyDrafts, setStrategyDrafts] = useState<StrategyDraft[]>([]);
  const [panels, setPanels] = useState<Panel[]>(() => createPanels(requiredTimeframes, true, referenceModeEnabled));
  const [chartCount, setChartCountState] = useState(MAX_REALTIME_CHARTS);
  const [focusIndex, setFocusIndex] = useState(0);
  const [marketPairs, setMarketPairs] = useState<MarketPair[]>(referenceModeEnabled ? MOCK_MARKET_PAIRS : []);
  const [marketPairsState, setMarketPairsState] = useState<LoadState>(referenceModeEnabled ? "ready" : "loading");
  const [dataMode, setDataMode] = useState<DataMode>(referenceModeEnabled ? "mock" : "live");
  /* Keep first client render identical to SSR. Reading localStorage here made a
     persisted pair (for example SOLUSDT) disagree with server-rendered
     DEFAULT_MARKET, producing a hydration failure before retryMarketPairs
     restored the same persisted selection after mount. */
  const [selectedMarket, setSelectedMarket] = useState<MarketSelection>(() => (
    referenceModeEnabled ? REFERENCE_MARKET : DEFAULT_MARKET
  ));
  const [realtimeEnabled, setRealtimeEnabledState] = useState(true);
  const [recentMarketEvents, setRecentMarketEvents] = useState<RecentMarketEvent[]>([]);
  const [recentTicks, setRecentTicks] = useState<DisplayTick[]>(() => referenceModeEnabled ? createMockTicks(REFERENCE_MARKET.symbol) : []);
  const [lastFrameAt, setLastFrameAt] = useState<string | undefined>(() => referenceModeEnabled ? "2025-04-29T10:45:38.123Z" : undefined);
  const [latencyMs, setLatencyMs] = useState<number | null>(referenceModeEnabled ? 102 : null);
  const [socketReconnectCount, setSocketReconnectCount] = useState(0);
  const [marketStatus, setMarketStatus] = useState<MarketStatus | null>(null);
  const [marketStatusState, setMarketStatusState] = useState<LoadState>(referenceModeEnabled ? "ready" : "loading");
  const [activeExperimentId, setActiveExperimentId] = useState<string | null>(null);
  const [experiment, setExperiment] = useState<ExperimentSummary | null>(null);
  const [result, setResult] = useState<ResultBundle | null>(null);
  const [searchId, setSearchId] = useState<string | null>(null);
  const [search, setSearch] = useState<SearchRun | null>(null);
  const [submittedDraft, setSubmittedDraft] = useState<DiscoveryDraft | null>(null);
  const [discoverySessions, setDiscoverySessions] = useState<SearchRun[]>([]);
  const [discoverySessionsState, setDiscoverySessionsState] = useState<LoadState>("idle");
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [leaderboardState, setLeaderboardState] = useState<LoadState>(referenceModeEnabled ? "ready" : "loading");
  const [discoveryArchive, setDiscoveryArchive] = useState<DiscoveryArchive | null>(null);
  const [discoveryArchiveState, setDiscoveryArchiveState] = useState<LoadState>("idle");
  const [news, setNews] = useState<NewsItem[]>([]);
  const [newsState, setNewsState] = useState<LoadState>(referenceModeEnabled ? "ready" : "loading");
  const [coverage, setCoverage] = useState<WorkspaceValue["coverage"]>(null);
  const [newsDistribution, setNewsDistribution] = useState<WorkspaceValue["newsDistribution"]>(null);
  const [newsAverageScore, setNewsAverageScore] = useState<number | null>(null);
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
  const discoverySessionsRequest = useRef(0);

  useEffect(() => {
    if (!user || !searchId) return;
    try {
      window.sessionStorage.setItem(
        DISCOVERY_SESSION_KEY,
        JSON.stringify({ ownerId: user.id, searchId, submittedDraft: submittedDraft ?? undefined }),
      );
    } catch {
      // Storage can be unavailable in a privacy-restricted browser; the live run still works.
    }
  }, [searchId, submittedDraft, user]);
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
    if (supported.length === 0) return requiredTimeframes;
    const supportedSet = new Set(supported);
    return knownTimeframes.filter((timeframe) => supportedSet.has(timeframe));
  }, [selectedPair]);

  const latestCandle = useMemo(() => {
    const candles = panels
      .map((panel) => panel.candles.at(-1))
      .filter((candle): candle is Candle => Boolean(candle))
      .sort((a, b) => a.open_time.localeCompare(b.open_time));
    return candles.at(-1);
  }, [panels]);

  const visiblePanels = panels.slice(0, chartCount);
  const readyPanelCount = visiblePanels.filter((panel) => panel.candles.length > 0).length;
  const stalePanelCount = visiblePanels.filter((panel) => panel.liveState === "stale").length;
  const unavailablePanelCount = visiblePanels.filter((panel) => panel.liveState === "unavailable").length;
  const livePanelCount = visiblePanels.filter((panel) => panel.liveState === "live").length;
  const signalCount = panels.reduce((sum, panel) => sum + panel.markers.length, 0);
  const activeStrategyCount = new Set(panels.map((panel) => panel.strategy)).size;
  const streamLabel: ConnectionLabel = !realtimeEnabled
    ? "Paused"
    : dataMode === "mock"
      ? "Mock"
      : marketPairsState === "unavailable" || unavailablePanelCount === visiblePanels.length
      ? "Unavailable"
      : stalePanelCount > 0 || unavailablePanelCount > 0 || marketStatus?.stale
        ? "Degraded"
        : readyPanelCount === visiblePanels.length && livePanelCount === visiblePanels.length
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

  function resolveStrategyExecutions(children: StrategyExecution[]): StrategyExecution[] {
    return children.map((child) => {
      const definition = strategies.find((strategy) => strategy.strategy_id === child.strategy_id);
      return {
        ...child,
        strategy_version: child.strategy_version ?? definition?.version ?? "v1",
        parameters: child.parameters ?? definition?.default_params ?? {},
      };
    });
  }

  function activateMockMode(market: MarketSelection = selectedMarketRef.current) {
    const catalogHasMarket = MOCK_MARKET_PAIRS.some((pair) => marketKey(pair) === marketKey(market));
    const mockPairs = catalogHasMarket ? MOCK_MARKET_PAIRS : [{
      provider: market.provider,
      symbol: market.symbol.toUpperCase(),
      base_asset: market.symbol.toUpperCase().replace(/USDT$/, ""),
      quote_asset: "USDT",
      timeframes: requiredTimeframes,
    }, ...MOCK_MARKET_PAIRS];
    dataModeRef.current = "mock";
    setDataMode("mock");
    setMarketPairs(mockPairs);
    setMarketPairsState("ready");
    setRecentTicks(createMockTicks(market.symbol));
    setLatencyMs(102);
    setLastFrameAt("2025-04-29T10:45:38.123Z");
    setPanels((current) => current.map((panel) => ({
      ...panel,
      liveState: realtimeEnabledRef.current ? "live" : "paused",
      lastFrameAt: "2025-04-29T10:45:38.123Z",
      latencyMs: 102,
    })));
    setMarketStatus({
      provider: "deterministic_mock",
      symbol: market.symbol.toUpperCase(),
      timeframe: panelsRef.current[0]?.timeframe ?? "1m",
      stale: false,
      last_closed_at: "2025-04-29T10:45:38.123Z",
      last_sequence: 1,
      reconnect_count: 0,
    });
    setMarketStatusState("ready");
    report("Backend market services unavailable. Showing clearly labeled deterministic mock data.", "warn");
  }

  async function loadPanel(
    index: number,
    override: Partial<Pick<Panel, "timeframe" | "strategy">> = {},
    limit = PANEL_BOOTSTRAP_CANDLE_LIMIT,
    explicitMarket: MarketSelection = selectedMarketRef.current,
  ) {
    const panel = { ...(panelsRef.current[index] ?? panelSeed[index]), ...override };
    const requestId = ++panelRequestIds.current[index];
    const requestMarketKey = marketKey(explicitMarket);
    const isHistoryRequest = limit > PANEL_BOOTSTRAP_CANDLE_LIMIT;
    if (isHistoryRequest) setPanel(index, { historyLoading: true, error: undefined });

    if (dataModeRef.current === "mock") {
      const mock = createMockPanelData(explicitMarket, panel.timeframe, limit);
      setPanel(index, {
        timeframe: panel.timeframe,
        strategy: panel.strategy,
        ...mock,
        lastClosed: mock.candles.at(-1)?.close_time,
        liveState: realtimeEnabledRef.current ? "live" : "paused",
        lastFrameAt: panel.lastFrameAt,
        latencyMs: panel.latencyMs,
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
      if (marketMockEnabled) {
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
      const errorMessage = `Market data unavailable: ${messageFromError(candlesResult.reason)}`;
      setPanel(index, {
        timeframe: panel.timeframe,
        strategy: panel.strategy,
        candles: [],
        series: [],
        markers: [],
        liveState: realtimeEnabledRef.current ? "unavailable" : "paused",
        lastFrameAt: undefined,
        latencyMs: null,
        loaded: true,
        historyLoading: false,
        historyLimit: limit,
        error: errorMessage,
      });
      report(errorMessage, "error");
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
          lastFrameAt: undefined,
          latencyMs: null,
          loaded: false,
          historyLimit: PANEL_BOOTSTRAP_CANDLE_LIMIT,
          error: undefined,
        });
        window.setTimeout(() => void loadPanel(index, { timeframe }), 0);
      },
      onStrategy: (strategy: string) => {
        setPanel(index, { strategy, liveState: realtimeEnabled ? "connecting" : "paused", lastFrameAt: undefined, latencyMs: null, loaded: false, error: undefined });
        window.setTimeout(() => void loadPanel(index, { strategy }), 0);
      },
    };
  }

  async function retryMarketPairs() {
    setMarketPairsState("loading");
    try {
      const payload = await api.marketPairs();
      const pairsByKey = new Map<string, MarketPair>();
      for (const pair of payload.pairs ?? []) {
        const normalized = {
          ...pair,
          symbol: pair.symbol.toUpperCase(),
          timeframes: [...new Set((pair.timeframes ?? []).filter(Boolean))],
        };
        const key = marketKey(normalized);
        const previous = pairsByKey.get(key);
        pairsByKey.set(key, previous ? {
          ...previous,
          timeframes: [...new Set([...previous.timeframes, ...normalized.timeframes])],
        } : normalized);
      }
      const pairs = [...pairsByKey.values()];
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
    } catch (error) {
      if (marketMockEnabled) {
        activateMockMode(REFERENCE_MARKET);
        setSelectedMarket(REFERENCE_MARKET);
        return;
      }
      dataModeRef.current = "live";
      setDataMode("live");
      setMarketPairs([]);
      setMarketPairsState("unavailable");
      setMarketStatus(null);
      setMarketStatusState("unavailable");
      setPanels((current) => current.map((panel) => ({
        ...panel,
        liveState: realtimeEnabledRef.current ? "unavailable" : "paused",
        error: `Market data unavailable: ${messageFromError(error)}`,
      })));
      report(`Market backend unavailable: ${messageFromError(error)}`, "error");
    }
  }

  async function refreshStaticData() {
    if (referenceModeEnabled) {
      setStrategyDrafts([]);
      setLeaderboard([]);
      setLeaderboardState("ready");
      setDiscoveryArchive(null);
      setDiscoveryArchiveState("ready");
      setNews([]);
      setNewsState("ready");
      setCoverage(null);
      setNewsAverageScore(null);
      setNewsDistribution(null);
      return;
    }
    const [strategyPayload, draftPayload, rank, newsPayload, aggregate] = await Promise.all([
      api.strategies().catch(() => null),
      api.strategyDrafts().catch(() => null),
      api.leaderboard(selectedMarketRef.current, panelsRef.current[0]?.timeframe ?? "5m").catch(() => null),
      api.news().catch(() => null),
      api.newsAggregate().catch(() => null),
    ]);
    setStrategies(strategyPayload?.strategies ?? []);
    setStrategyDrafts(draftPayload?.drafts ?? []);
    setLeaderboard(rank?.entries ?? []);
    setLeaderboardState(rank ? "ready" : "unavailable");
    setNews(newsPayload?.items ?? []);
    setNewsState(newsPayload ? "ready" : "unavailable");
    setCoverage(aggregate?.coverage ?? null);
    setNewsAverageScore(aggregate?.avg_score ?? null);
    setNewsDistribution(distributionFromCounts(aggregate?.distribution));
  }

  async function refreshDiscoverySessions() {
    const request = ++discoverySessionsRequest.current;
    if (referenceModeEnabled) {
      if (request === discoverySessionsRequest.current) {
        setDiscoverySessions([]);
        setDiscoverySessionsState("ready");
      }
      return;
    }
    try {
      const sessions = await api.discoveryRuns();
      if (request === discoverySessionsRequest.current) {
        setDiscoverySessions(sessions);
        setDiscoverySessionsState("ready");
      }
    } catch {
      if (request === discoverySessionsRequest.current) setDiscoverySessionsState("unavailable");
    }
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
          nextTradeCursor: trades.next_cursor,
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
    if (referenceModeEnabled) {
      const bootstrapTimer = window.setTimeout(() => activateMockMode(REFERENCE_MARKET), 0);
      return () => window.clearTimeout(bootstrapTimer);
    }
    api.me()
      .then((payload) => {
        setUser(payload.user);
        const session = readPersistedDiscoverySession(payload.user.id);
        if (session) {
          setSearchId(session.searchId);
          setSubmittedDraft(session.submittedDraft);
          setDiscoveryArchiveState("loading");
        }
        void refreshStaticData();
        void refreshDiscoverySessions();
      })
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
      const nextPanels = createPanels(availableTimeframes, realtimeEnabled, dataModeRef.current === "mock");
      setPanels(nextPanels);
      setFocusIndex(0);
      setRecentMarketEvents([]);
      const mockMode = dataModeRef.current === "mock";
      setRecentTicks(mockMode ? createMockTicks(selectedMarket.symbol) : []);
      setLastFrameAt(mockMode ? "2025-04-29T10:45:38.123Z" : undefined);
      setLatencyMs(mockMode ? 102 : null);
      setSocketReconnectCount(0);
      setMarketStatus(mockMode ? {
        provider: "binance_usdm",
        symbol: selectedMarket.symbol,
        timeframe: nextPanels[0]?.timeframe ?? "1m",
        stale: false,
        last_closed_at: "2025-04-29T10:45:38.123Z",
        last_sequence: 1,
        reconnect_count: 0,
      } : null);
      window.localStorage.setItem("crypto-lab-market", JSON.stringify(selectedMarket));
      nextPanels.forEach((panel, index) => void loadPanel(index, {
        timeframe: panel.timeframe,
        strategy: panel.strategy,
      }, PANEL_BOOTSTRAP_CANDLE_LIMIT, selectedMarket));
    });
    return () => window.cancelAnimationFrame(resetFrame);
    // Pair or supported timeframe changes require a clean, guarded reload.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [marketSignature, timeframeSignature, dataMode]);

  const currentPrimaryTimeframe = panels[0]?.timeframe;
  const primaryTimeframe = currentPrimaryTimeframe && availableTimeframes.includes(currentPrimaryTimeframe)
    ? currentPrimaryTimeframe
    : availableTimeframes[0] ?? requiredTimeframes[0];
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
            void loadPanel(index, {}, panelsRef.current[index]?.historyLimit ?? PANEL_BOOTSTRAP_CANDLE_LIMIT, selectedMarket);
            socket.close();
            return;
          }

          const sequence = frame.sequence;
          if (sequence !== undefined) {
            if ((sequence < lastSequence && frame.type !== "overlay_delta") ||
              (sequence === lastSequence && frame.type !== "overlay_delta")) return;
            if (sequence > lastSequence && lastSequence > 0 && sequence !== lastSequence + 1) {
              lastSequence = 0;
              setPanel(index, { liveState: "connecting" });
              void loadPanel(index, {}, panelsRef.current[index]?.historyLimit ?? PANEL_BOOTSTRAP_CANDLE_LIMIT, selectedMarket);
              socket.close();
              return;
            }
            if (sequence > lastSequence) lastSequence = sequence;
          }

          const frameTimestamp = frame.serverTime ?? frame.occurredAt;
          const frameLatency = frame.serverTime
            ? Date.parse(frame.serverTime)
            : Number.NaN;
          const nextLatency = Number.isFinite(frameLatency) ? Math.max(0, Date.now() - frameLatency) : null;
          if (nextLatency != null) setLatencyMs(nextLatency);
          if (frameTimestamp) {
            const receivedAt = new Date().toISOString();
            setLastFrameAt(receivedAt);
            setPanel(index, { lastFrameAt: receivedAt, ...(nextLatency != null ? { latencyMs: nextLatency } : {}) });
          }

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
          if (frame.type === "overlay_delta" && frame.overlay) {
            setPanels((current) => current.map((currentPanel, panelIndex) => {
              if (panelIndex !== index) return currentPanel;
              const merged = mergeOverlayDelta({
                series: currentPanel.series as unknown as RealtimeOverlaySeries[],
                markers: currentPanel.markers,
              }, frame.overlay!);
              return {
                ...currentPanel,
                series: merged.series as unknown as OverlaySeries[],
                markers: merged.markers,
                liveState: "live",
              };
            }));
          }
          if (frame.type === "stream_status") {
            if (frame.reconnectNo !== undefined) {
              setSocketReconnectCount((current) => Math.max(current, frame.reconnectNo!));
            }
            setPanel(index, {
              liveState: frame.state === "stale" || frame.state === "connecting"
                ? panelsRef.current[index]?.candles.length ? "stale" : "unavailable"
                : "live",
            });
          }
        };
        socket.onerror = () => {
          if (realtimeEnabledRef.current && marketKey(selectedMarketRef.current) === marketKey(selectedMarket)) {
            setPanel(index, { liveState: panelsRef.current[index]?.candles.length ? "stale" : "unavailable" });
          }
        };
        socket.onclose = () => {
          sockets.delete(socket);
          if (stopped || !realtimeEnabledRef.current || marketKey(selectedMarketRef.current) !== marketKey(selectedMarket)) return;
          setPanel(index, { liveState: panelsRef.current[index]?.candles.length ? "stale" : "unavailable" });
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
      const now = new Date().toISOString();
      const nextLatency = 22 + (tick % 9);
      const nextPanels = panelsRef.current.map((panel) => {
        const last = panel.candles.at(-1);
        if (!last) return panel;
        const nextCandle = updateMockCandle(last, tick + timeframeOrder(panel.timeframe));
        return {
          ...panel,
          candles: [...panel.candles.slice(0, -1), nextCandle],
          liveState: "live" as const,
          lastFrameAt: now,
          latencyMs: nextLatency,
        };
      });
      setPanels(nextPanels);
      const price = nextPanels[0]?.candles.at(-1)?.close;
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
      setLatencyMs(nextLatency);
    }, 60_000);
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
    let stopped = false;
    const refresh = async () => {
      try {
        const next = await api.searchRun(searchId);
        if (stopped) return;
        setSearch(next);
        setDiscoverySessions((current) => [next, ...current.filter((item) => item.search_run_id !== next.search_run_id)]);
        if (next.generator_id !== "discovery") {
          setDiscoveryArchive(null);
          setDiscoveryArchiveState("ready");
          return;
        }
        try {
          const archive = await api.discoveryArchive(searchId);
          if (!stopped) {
            setDiscoveryArchive(archive);
            setDiscoveryArchiveState("ready");
          }
        } catch {
          if (!stopped) setDiscoveryArchiveState("unavailable");
        }
      } catch {
        // The next polling tick retries a transient progress failure.
      }
    };
    const timer = window.setInterval(() => {
      void refresh();
      void refreshStaticData();
    }, 1800);
    void refresh();
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
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
    strategyDrafts,
    panels,
    chartCount,
    setChartCount(count) {
      const nextCount = Math.max(MIN_REALTIME_CHARTS, Math.min(MAX_REALTIME_CHARTS, Math.round(count)));
      setChartCountState(nextCount);
      setFocusIndex((current) => Math.min(current, nextCount - 1));
    },
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
      return loadPanel(index, {}, PANEL_BOOTSTRAP_CANDLE_LIMIT);
    },
    experiment,
    result,
    search,
    discoverySessions,
    discoverySessionsState,
    submittedDraft,
    leaderboard,
    leaderboardState,
    discoveryArchive,
    discoveryArchiveState,
    news,
    newsState,
    coverage,
    newsDistribution,
    newsAverageScore,
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
    async register(email, password, displayName) {
      try {
        const payload = await api.register(email, password, displayName);
        setUser(payload.user);
        await Promise.all([refreshStaticData(), refreshDiscoverySessions()]);
        report(`Registered as ${payload.user.email}`);
      } catch (error) {
        report(messageFromError(error), "error");
      }
    },
    async login(email, password) {
      try {
        const payload = await api.login(email, password);
        setUser(payload.user);
        await Promise.all([refreshStaticData(), refreshDiscoverySessions()]);
        report(`Signed in as ${payload.user.email}`);
      } catch (error) {
        report(messageFromError(error), "error");
      }
    },
    async logout() {
      try {
        await api.logout();
        discoverySessionsRequest.current += 1;
        setUser(null);
        setStrategyDrafts([]);
        setSearchId(null);
        setSearch(null);
        setSubmittedDraft(null);
        setDiscoveryArchive(null);
        setDiscoverySessions([]);
        report("Signed out.");
      } catch (error) {
        report(messageFromError(error), "error");
      }
    },
    async runBacktest(children = compositeChildren, execution = DEFAULT_EXECUTION, timeframe, range, market, datasetVersion) {
      try {
        const accepted = await api.createExperiment(
          resolveStrategyExecutions(children),
          market ?? selectedMarket,
          timeframe ?? panels[0]?.timeframe ?? "5m",
          execution,
          range,
          datasetVersion,
        );
        setActiveExperimentId(accepted.experiment_id);
        setResult(null);
        report(`Backtest queued: ${accepted.run_id.slice(0, 8)}`);
        return true;
      } catch (error) {
        report(messageFromError(error), "error");
        return false;
      }
    },
    async startSearch(draft) {
      try {
        const weights = normalizeWeights(draft.selectedStrategyIds, draft.weights);
        const accepted = await api.startSearch(draft, resolveStrategyExecutions(
          draft.selectedStrategyIds.map((strategy_id) => ({ strategy_id, weight: weights[strategy_id] })),
        ));
        setSearchId(accepted.search_run_id);
        setSearch(accepted);
        setSubmittedDraft(draft);
        setDiscoverySessions((current) => [accepted, ...current.filter((item) => item.search_run_id !== accepted.search_run_id)]);
        setDiscoveryArchive(null);
        setDiscoveryArchiveState(accepted.generator_id === "discovery" ? "loading" : "ready");
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
    async selectDiscoverySession(id) {
      try {
        const selected = await api.searchRun(id);
        if (selected.generator_id !== "discovery") throw new Error("Selected run is not a Discovery session.");
        setSearchId(selected.search_run_id);
        setSearch(selected);
        setSubmittedDraft(null);
        setDiscoveryArchive(null);
        setDiscoveryArchiveState("loading");
        setDiscoverySessions((current) => [selected, ...current.filter((item) => item.search_run_id !== selected.search_run_id)]);
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

/* The API returns label counts, not percentages. Deriving the last share from
   the other two keeps the three values summing to exactly 100. */
function distributionFromCounts(counts?: Record<"POSITIVE" | "NEUTRAL" | "NEGATIVE", number>) {
  if (!counts) return null;
  const total = counts.POSITIVE + counts.NEUTRAL + counts.NEGATIVE;
  if (total <= 0) return null;
  const positive = Math.round((counts.POSITIVE / total) * 100);
  const neutral = Math.round((counts.NEUTRAL / total) * 100);
  return { positive, neutral, negative: 100 - positive - neutral };
}

function timeframeOrder(timeframe: string) {
  const match = timeframe.match(/^(\d+)([smhdw])$/i);
  if (!match) return Number.MAX_SAFE_INTEGER;
  const unitSeconds: Record<string, number> = { s: 1, m: 60, h: 3_600, d: 86_400, w: 604_800 };
  return Number(match[1]) * (unitSeconds[match[2].toLowerCase()] ?? Number.MAX_SAFE_INTEGER);
}

function readPersistedMarket(): MarketSelection | null {  try {
    if (typeof window === "undefined") return null;
    const value = JSON.parse(window.localStorage.getItem("crypto-lab-market") ?? "null") as Partial<MarketSelection> | null;
    if (!value?.provider || !value.symbol) return null;
    return { provider: value.provider, symbol: value.symbol.toUpperCase() };
  } catch {
    return null;
  }
}

function readPersistedDiscoverySession(ownerId: string): {
  searchId: string;
  submittedDraft: DiscoveryDraft | null;
} | null {
  try {
    if (typeof window === "undefined") return null;
    const value = JSON.parse(window.sessionStorage.getItem(DISCOVERY_SESSION_KEY) ?? "null") as {
      ownerId?: unknown;
      searchId?: unknown;
      submittedDraft?: Partial<DiscoveryDraft>;
    } | null;
    if (
      value?.ownerId !== ownerId ||
      typeof value.searchId !== "string" ||
      !value.searchId ||
      (value.submittedDraft !== undefined && (
        !Array.isArray(value.submittedDraft.selectedStrategyIds) ||
        typeof value.submittedDraft.timeframe !== "string"
      ))
    ) return null;
    return { searchId: value.searchId, submittedDraft: value.submittedDraft as DiscoveryDraft | null ?? null };
  } catch {
    return null;
  }
}
