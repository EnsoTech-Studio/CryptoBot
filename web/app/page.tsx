"use client";

import type { ReactElement } from "react";
import { useEffect, useMemo, useState } from "react";

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
  type OverlayPoint,
  type OverlaySeries,
  type Prediction,
  type SearchRun,
  type Strategy,
  type Trade,
  type User,
} from "../lib/api";

const panelSeed = [
  { id: "chart-1", title: "Scalp feed", timeframe: "5m", strategy: "composite@1.0.0" },
  { id: "chart-2", title: "Trend check", timeframe: "15m", strategy: "ma_cross@1.0.0" },
  { id: "chart-3", title: "Volatility", timeframe: "1h", strategy: "bollinger@1.0.0" },
  { id: "chart-4", title: "Structure", timeframe: "4h", strategy: "support_resistance@1.0.0" },
];

type Panel = {
  id: string;
  title: string;
  timeframe: string;
  strategy: string;
  candles: Candle[];
  series: OverlaySeries[];
  markers: OverlayMarker[];
  lastClosed?: string;
  liveState: "connecting" | "live" | "stale";
  error?: string;
};

type ResultBundle = {
  candles: Candle[];
  trades: Trade[];
  equity: EquityPoint[];
  series: OverlaySeries[];
  signalMarkers: OverlayMarker[];
  executionMarkers: ExecutionMarker[];
};

export default function Home() {
  const [user, setUser] = useState<User | null>(null);
  const [email, setEmail] = useState("researcher@example.com");
  const [password, setPassword] = useState("Research#2026");
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [panels, setPanels] = useState<Panel[]>(
    panelSeed.map((panel) => ({ ...panel, candles: [], series: [], markers: [], liveState: "connecting" })),
  );
  const [activeExperimentId, setActiveExperimentId] = useState<string | null>(null);
  const [experiment, setExperiment] = useState<ExperimentSummary | null>(null);
  const [result, setResult] = useState<ResultBundle | null>(null);
  const [searchId, setSearchId] = useState<string | null>(null);
  const [search, setSearch] = useState<SearchRun | null>(null);
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [provenance, setProvenance] = useState<Record<string, unknown> | null>(null);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [coverage, setCoverage] = useState<{ items_total: number; items_analyzed: number; items_unanalyzed: number } | null>(null);
  const [predictionText, setPredictionText] = useState("Ethereum inflows look positive, but volatility risk remains.");
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [notice, setNotice] = useState("Connecting market stream...");

  const latestCandle = useMemo(() => {
    const candles = panels
      .map((panel) => panel.candles.at(-1))
      .filter((candle): candle is Candle => Boolean(candle))
      .sort((a, b) => a.open_time.localeCompare(b.open_time));
    return candles.at(-1);
  }, [panels]);
  const readyPanelCount = panels.filter((panel) => panel.candles.length > 0).length;
  const stalePanelCount = panels.filter((panel) => panel.liveState === "stale").length;
  const signalCount = panels.reduce((sum, panel) => sum + panel.markers.length, 0);
  const activeStrategyCount = new Set(panels.map((panel) => panel.strategy)).size;
  const streamLabel = stalePanelCount > 0 ? "Degraded" : readyPanelCount === panels.length ? "Live" : "Syncing";

  useEffect(() => {
    api.me()
      .then((payload) => setUser(payload.user))
      .catch(() => setNotice("Sign in to run experiments and search loops."));
    api.strategies().then((payload) => setStrategies(payload.strategies)).catch(() => undefined);
    refreshStaticData();
    panelSeed.forEach((_, index) => void loadPanel(index));
    // Initial bootstrap only: loadPanel uses the seed panel state for this pass.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const subscriptionSignature = panels.map((panel) => `${panel.timeframe}:${panel.strategy}`).join("|");

  useEffect(() => {
    const sockets = panels.map((panel, index) => {
      const key = `binance_usdm|ETHUSDT|${panel.timeframe}|${panel.strategy}|sha256:${"4".repeat(64)}`;
      const socket = new WebSocket(wsURL(key));
      socket.onopen = () => {
        socket.send(JSON.stringify({ action: "subscribe", key, req: `${panel.id}-${Date.now()}` }));
        setPanel(index, { liveState: "live" });
      };
      socket.onmessage = (event) => {
        const frame = JSON.parse(event.data) as {
          type?: string;
          kline?: Record<string, string>;
          series?: OverlaySeries[];
          markers?: OverlayMarker[];
        };
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
            trade_count: 0,
          };
          setPanels((current) => current.map((p, i) => i === index ? { ...p, candles: upsertCandle(p.candles, candle), lastClosed: candle.open_time, liveState: "live" } : p));
        }
        if (frame.type === "overlay_delta") {
          void loadPanel(index);
        }
      };
      socket.onerror = () => setPanel(index, { liveState: "stale" });
      socket.onclose = () => setPanel(index, { liveState: "stale" });
      return socket;
    });
    return () => sockets.forEach((socket) => socket.close());
    // Reconnect sockets only when a panel subscription key changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subscriptionSignature]);

  useEffect(() => {
    if (!activeExperimentId) return;
    const timer = window.setInterval(() => {
      void refreshExperiment(activeExperimentId);
    }, 1600);
    void refreshExperiment(activeExperimentId);
    return () => window.clearInterval(timer);
    // Poll the active experiment id; refreshExperiment is intentionally not a dependency.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeExperimentId]);

  useEffect(() => {
    if (!searchId) return;
    const timer = window.setInterval(() => {
      api.searchRun(searchId).then(setSearch).catch(() => undefined);
      void refreshStaticData();
    }, 1800);
    api.searchRun(searchId).then(setSearch).catch(() => undefined);
    return () => window.clearInterval(timer);
  }, [searchId]);

  const compositeChildren = useMemo(() => [
    { strategy_id: "ma_cross", weight: 0.34 },
    { strategy_id: "rsi", weight: 0.33 },
    { strategy_id: "support_resistance", weight: 0.33 },
  ], []);

  async function login() {
    try {
      const payload = await api.login(email, password);
      setUser(payload.user);
      setNotice(`Signed in: ${payload.user.email}`);
    } catch (error) {
      setNotice(messageFromError(error));
    }
  }

  async function runBacktest() {
    try {
      const accepted = await api.createExperiment(compositeChildren);
      setActiveExperimentId(accepted.experiment_id);
      setNotice(`Backtest queued: ${accepted.run_id.slice(0, 8)}`);
    } catch (error) {
      setNotice(messageFromError(error));
    }
  }

  async function startSearch() {
    try {
      const accepted = await api.startSearch();
      setSearchId(accepted.search_run_id);
      setNotice(`Search run started: ${accepted.search_run_id.slice(0, 8)}`);
    } catch (error) {
      setNotice(messageFromError(error));
    }
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
          candles: candles.candles,
          trades: trades.trades,
          equity: equity.points,
          series: overlays.series,
          signalMarkers: overlays.signal_markers,
          executionMarkers: overlays.execution_markers,
        });
        void refreshStaticData();
      }
    } catch (error) {
      setNotice(messageFromError(error));
    }
  }

  async function refreshStaticData() {
    const [rank, newsPayload, aggregate] = await Promise.all([
      api.leaderboard().catch(() => ({ entries: [] })),
      api.news().catch(() => ({ items: [], meta: { last_collected_at: "", total: 0 } })),
      api.newsAggregate().catch(() => ({ coverage: null })),
    ]);
    setLeaderboard(rank.entries);
    setNews(newsPayload.items);
    setCoverage(aggregate.coverage);
  }

  async function loadPanel(index: number, override: Partial<Pick<Panel, "timeframe" | "strategy">> = {}) {
    const panel = { ...(panels[index] ?? panelSeed[index]), ...override };
    try {
      const [candles, overlays] = await Promise.all([
        api.candles(panel.timeframe, panel.strategy),
        api.overlays(panel.timeframe, panel.strategy),
      ]);
      setPanel(index, {
        candles: candles.candles,
        series: overlays.series,
        markers: overlays.markers,
        lastClosed: overlays.last_closed_at,
        liveState: overlays.is_stale ? "stale" : "live",
        error: undefined,
      });
    } catch (error) {
      setPanel(index, { candles: [], series: [], markers: [], liveState: "stale", error: messageFromError(error) });
      setNotice(messageFromError(error));
    }
  }

  function setPanel(index: number, patch: Partial<Panel>) {
    setPanels((current) => current.map((panel, i) => i === index ? { ...panel, ...patch } : panel));
  }

  async function testSentiment() {
    try {
      const payload = await api.predict(predictionText);
      setPrediction(payload);
    } catch (error) {
      setNotice(messageFromError(error));
    }
  }

  return (
    <main className="terminal-shell">
      <aside className="left-rail" aria-label="Workspace">
        <div className="brand-block">
          <span className="brand-mark">CL</span>
          <div>
            <strong>Crypto Lab</strong>
            <span>Strategy research</span>
          </div>
        </div>
        <nav className="rail-nav">
          <a href="#markets" aria-current="page">Dashboard</a>
          <a href="#backtest">Backtests</a>
          <a href="#search">Search</a>
          <a href="#leaderboard">Leaderboard</a>
          <a href="#news">News</a>
        </nav>
        <div className="rail-card">
          <span>Market</span>
          <strong>ETHUSDT</strong>
          <span>Provider</span>
          <strong>Binance USD-M</strong>
          <span>Panels</span>
          <strong>{readyPanelCount}/4 active</strong>
        </div>
      </aside>

      <section className="terminal-main">
        <header className="terminal-topbar">
          <div className="topbar-market">
            <span className={`stream-dot ${streamLabel.toLowerCase()}`} />
            <div>
              <strong>ETHUSDT strategy cockpit</strong>
              <span>{notice}</span>
            </div>
          </div>
          <div className="session-panel">
            {user ? (
              <>
                <span>{user.display_name}</span>
                <strong>{user.role}</strong>
                <button className="ghost-action" onClick={() => api.logout().then(() => setUser(null))}>Logout</button>
              </>
            ) : (
              <>
                <input value={email} onChange={(event) => setEmail(event.target.value)} aria-label="Email" />
                <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" aria-label="Password" />
                <button className="primary-action" onClick={login}>Login</button>
              </>
            )}
          </div>
        </header>

        <section id="markets" className="market-command">
          <div>
            <p className="eyebrow">Realtime Market Data</p>
            <h1>Four-panel market view</h1>
            <div className="command-meta">
              <span>{streamLabel}</span>
              <span>{activeStrategyCount} strategies</span>
              <span>{signalCount} signals</span>
            </div>
          </div>
          <div className="command-actions">
            <button className="primary-action" onClick={runBacktest} disabled={!user}>Run backtest</button>
            <button className="ghost-action" onClick={startSearch} disabled={!user}>Start search</button>
          </div>
        </section>

        <section className="market-strip" aria-label="Market status">
          <Metric label="Last close" value={latestCandle ? formatPrice(latestCandle.close) : "waiting"} />
          <Metric label="Volume" value={latestCandle ? formatCompact(latestCandle.volume) : "0"} />
          <Metric label="Backtest" value={experiment?.status ?? "idle"} />
          <Metric label="News coverage" value={coverage ? `${coverage.items_analyzed}/${coverage.items_total}` : "0/0"} />
        </section>

        <section className="chart-grid" aria-label="Realtime market dashboard">
          {panels.map((panel, index) => (
            <ChartPanel
              key={panel.id}
              panel={panel}
              strategies={strategies}
              onTimeframe={(timeframe) => {
                setPanel(index, { timeframe, liveState: "connecting" });
                window.setTimeout(() => void loadPanel(index, { timeframe }), 0);
              }}
              onStrategy={(strategy) => {
                setPanel(index, { strategy, liveState: "connecting" });
                window.setTimeout(() => void loadPanel(index, { strategy }), 0);
              }}
            />
          ))}
        </section>

        <section className="operation-grid">
          <section id="backtest" className="surface">
            <div className="surface-head">
              <div>
                <p className="eyebrow">Experiment</p>
                <h2>Async backtest</h2>
              </div>
              <button className="primary-action" onClick={runBacktest} disabled={!user}>Run</button>
            </div>
            {experiment ? (
              <div className="metric-grid">
                <Metric label="Status" value={experiment.status} />
                <Metric label="Signals" value={String(experiment.signals_count)} />
                <Metric label="Trades" value={String(experiment.metrics?.trade_count ?? 0)} />
                <Metric label="Score" value={formatNumber(experiment.metrics?.score)} />
              </div>
            ) : (
              <p className="muted">No active experiment. Queue a composite snapshot to inspect trades, equity and provenance.</p>
            )}
          </section>

          <section id="search" className="surface">
            <div className="surface-head">
              <div>
                <p className="eyebrow">Search loop</p>
                <h2>Generate, queue, rank</h2>
              </div>
              <button className="primary-action" onClick={startSearch} disabled={!user}>Start</button>
            </div>
            {search ? (
              <>
                <div className="metric-grid">
                  <Metric label="Generated" value={String(search.candidates.generated)} />
                  <Metric label="Tested" value={String(search.candidates.tested)} />
                  <Metric label="Failed" value={String(search.candidates.failed)} />
                  <Metric label="Best" value={formatNumber(search.best_score)} />
                </div>
                <div className="button-row">
                  <button className="ghost-action" onClick={() => api.searchAction(search.search_run_id, "pause").then(() => api.searchRun(search.search_run_id).then(setSearch))}>Pause</button>
                  <button className="ghost-action" onClick={() => api.searchAction(search.search_run_id, "resume").then(() => api.searchRun(search.search_run_id).then(setSearch))}>Resume</button>
                  <button className="ghost-action danger" onClick={() => api.searchAction(search.search_run_id, "cancel").then(() => api.searchRun(search.search_run_id).then(setSearch))}>Cancel</button>
                </div>
              </>
            ) : (
              <p className="muted">No active loop. Search results will update the Top-K board as candidates finish.</p>
            )}
          </section>
        </section>

        {result && experiment ? (
          <section className="result-layout">
            <section className="surface result-chart">
              <div className="surface-head">
                <div>
                  <p className="eyebrow">Backtest visualization</p>
                  <h2>{experiment.candidate_hash.slice(0, 12)}</h2>
                </div>
                <span className="dataset-pill">{experiment.dataset_version}</span>
              </div>
              <ChartCanvas
                candles={result.candles}
                series={result.series}
                markers={result.signalMarkers}
                executionMarkers={result.executionMarkers}
                tall
              />
            </section>
            <section className="surface">
              <div className="surface-head">
                <div>
                  <p className="eyebrow">Evaluation</p>
                  <h2>Metrics</h2>
                </div>
                <span className="dataset-pill">{experiment.metrics?.evaluator_version}</span>
              </div>
              <div className="metric-grid vertical">
                <Metric label="Return" value={`${formatNumber(experiment.metrics?.total_return_pct)}%`} />
                <Metric label="Win rate" value={`${formatNumber(experiment.metrics?.win_rate_pct)}%`} />
                <Metric label="MDD" value={`${formatNumber(experiment.metrics?.max_drawdown_pct)}%`} />
                <Metric label="Sharpe" value={formatNumber(experiment.metrics?.sharpe_ratio)} />
              </div>
              <EquityChart points={result.equity} />
            </section>
            <section className="surface trades-table">
              <div className="surface-head">
                <div>
                  <p className="eyebrow">Trades</p>
                  <h2>{result.trades.length} executions</h2>
                </div>
              </div>
              <table>
                <thead>
                  <tr><th>#</th><th>Entry UTC</th><th>Exit UTC</th><th>PnL</th><th>Reason</th></tr>
                </thead>
                <tbody>
                  {result.trades.map((trade) => (
                    <tr key={trade.id}>
                      <td>{trade.sequence_no}</td>
                      <td>{formatPrice(trade.entry_price)}<span>{compactDateTime(trade.entry_time)}</span></td>
                      <td>{formatPrice(trade.exit_price)}<span>{compactDateTime(trade.exit_time)}</span></td>
                      <td className={trade.pnl >= 0 ? "positive" : "negative"}>{trade.pnl.toFixed(3)}</td>
                      <td>{trade.exit_reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          </section>
        ) : null}

        <section className="bottom-grid">
          <section id="leaderboard" className="surface leaderboard">
            <div className="surface-head">
              <div>
                <p className="eyebrow">Leaderboard</p>
                <h2>Top-K strategy snapshots</h2>
              </div>
              <button className="ghost-action" onClick={refreshStaticData}>Refresh</button>
            </div>
            <table>
              <thead><tr><th>Rank</th><th>Strategy</th><th>Score</th><th>Return</th><th>MDD</th><th></th></tr></thead>
              <tbody>
                {leaderboard.map((entry) => (
                  <tr key={entry.id}>
                    <td>{entry.rank}</td>
                    <td>{entry.candidate_hash.slice(0, 10)}</td>
                    <td>{formatNumber(entry.score)}</td>
                    <td className={entry.total_return_pct >= 0 ? "positive" : "negative"}>{formatNumber(entry.total_return_pct)}%</td>
                    <td>{formatNumber(entry.max_drawdown_pct)}%</td>
                    <td><button className="ghost-action" onClick={() => api.provenance(entry.id).then(setProvenance)}>Trace</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {provenance ? <pre className="provenance">{JSON.stringify(provenance, null, 2)}</pre> : null}
          </section>

          <section id="news" className="surface news-panel">
            <div className="surface-head">
              <div>
                <p className="eyebrow">News and sentiment</p>
                <h2>Coverage {coverage ? `${coverage.items_analyzed}/${coverage.items_total}` : "0/0"}</h2>
              </div>
            </div>
            <div className="sentiment-test">
              <textarea value={predictionText} onChange={(event) => setPredictionText(event.target.value)} />
              <button className="primary-action" onClick={testSentiment} disabled={!user}>Analyze</button>
              {prediction ? <span className={`sentiment ${prediction.label.toLowerCase()}`}>{prediction.label} {Math.round(prediction.score * 100)}%</span> : null}
            </div>
            <div className="news-list">
              {news.map((item) => (
                <article key={item.id}>
                  <span className={`sentiment ${(item.sentiment?.label ?? "unavailable").toLowerCase()}`}>
                    {item.sentiment?.label ?? "unavailable"}
                  </span>
                  <h3>{item.title}</h3>
                  <p>{item.source.display_name} / {compactDateTime(item.published_at)}</p>
                </article>
              ))}
            </div>
          </section>
        </section>
      </section>
    </main>
  );
}

function ChartPanel({ panel, strategies, onTimeframe, onStrategy }: {
  panel: Panel;
  strategies: Strategy[];
  onTimeframe: (timeframe: string) => void;
  onStrategy: (strategy: string) => void;
}) {
  const hasCurrentStrategy = strategies.some((strategy) => `${strategy.strategy_id}@${strategy.version}` === panel.strategy);
  return (
    <section className="chart-panel">
      <div className="chart-toolbar">
        <div>
          <div className="pair-line">
            <strong>ETHUSDT</strong>
            <span>{panel.title}</span>
          </div>
          <p>{strategyName(strategies, panel.strategy)} / {panel.timeframe}</p>
        </div>
        <span className={`live-badge ${panel.liveState}`}>{panel.liveState}</span>
      </div>
      <ChartCanvas candles={panel.candles} series={panel.series} markers={panel.markers} />
      {panel.error ? <p className="panel-error">{panel.error}</p> : null}
      <div className="chart-legend" aria-label="Chart layers">
        <span className="legend-item candle">Candle</span>
        <span className="legend-item volume">Volume</span>
        <span className="legend-item ma">MA</span>
        <span className="legend-item band">BB</span>
        <span className="legend-item structure">S/R</span>
        <span className="legend-item signal">Signal</span>
      </div>
      <div className="chart-controls">
        <select value={panel.timeframe} onChange={(event) => onTimeframe(event.target.value)} aria-label={`${panel.title} timeframe`}>
          {["1m", "5m", "15m", "1h", "4h", "1d"].map((tf) => <option key={tf}>{tf}</option>)}
        </select>
        <select value={panel.strategy} onChange={(event) => onStrategy(event.target.value)} aria-label={`${panel.title} strategy`}>
          {!hasCurrentStrategy ? <option value={panel.strategy}>{panel.strategy}</option> : null}
          {strategies.map((strategy) => (
            <option key={`${strategy.strategy_id}@${strategy.version}`} value={`${strategy.strategy_id}@${strategy.version}`}>
              {strategy.display_name}
            </option>
          ))}
        </select>
      </div>
    </section>
  );
}

function ChartCanvas({
  candles,
  series,
  markers,
  executionMarkers = [],
  tall = false,
}: {
  candles: Candle[];
  series: OverlaySeries[];
  markers: OverlayMarker[];
  executionMarkers?: ExecutionMarker[];
  tall?: boolean;
}) {
  const width = 900;
  const height = tall ? 430 : 280;
  const pad = { left: 58, right: 58, top: 20, bottom: 28 };
  const gap = 10;
  const volumeH = tall ? 72 : 42;
  const subSeries = series.filter((item) => item.pane === "sub");
  const subH = subSeries.length > 0 ? (tall ? 70 : 44) : 0;
  const plotH = height - pad.top - pad.bottom - volumeH - subH - gap * (subH > 0 ? 2 : 1);
  const plotW = width - pad.left - pad.right;
  const volumeTop = pad.top + plotH + gap;
  const subTop = volumeTop + volumeH + (subH > 0 ? gap : 0);
  const view = candles.slice(-120);
  const priceValues = view.flatMap((candle) => [candle.high, candle.low]);
  series.filter((item) => item.pane === "main").forEach((item) => {
    item.points?.forEach((point) => { if (point.v != null) priceValues.push(point.v); });
    item.band?.upper.forEach((point) => { if (point.v != null) priceValues.push(point.v); });
    item.band?.lower.forEach((point) => { if (point.v != null) priceValues.push(point.v); });
    item.zones?.forEach((zone) => priceValues.push(zone.price_low, zone.price_high));
  });
  executionMarkers.forEach((marker) => {
    if (marker.price != null) priceValues.push(marker.price);
  });
  const minPrice = Number.isFinite(Math.min(...priceValues)) ? Math.min(...priceValues) : 0;
  const maxPrice = Number.isFinite(Math.max(...priceValues)) ? Math.max(...priceValues) : 1;
  const pricePadding = Math.max(1, (maxPrice - minPrice) * 0.08);
  const priceMin = minPrice - pricePadding;
  const priceMax = maxPrice + pricePadding;
  const maxVolume = Math.max(1, ...view.map((candle) => candle.volume));
  const x = (index: number) => pad.left + (index / Math.max(1, view.length - 1)) * plotW;
  const y = (value: number) => pad.top + (1 - (value - priceMin) / Math.max(1, priceMax - priceMin)) * plotH;
  const vy = (value: number) => volumeTop + (1 - value / maxVolume) * volumeH;
  const candleWidth = Math.max(3, plotW / Math.max(1, view.length) * 0.58);

  return (
    <svg className="chart-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Candlestick chart with volume and overlays">
      <rect x="0" y="0" width={width} height={height} className="chart-bg" />
      <rect x={pad.left} y={pad.top} width={plotW} height={plotH} className="pane-bg main-pane" />
      <rect x={pad.left} y={volumeTop} width={plotW} height={volumeH} className="pane-bg volume-pane" />
      {subH > 0 ? <rect x={pad.left} y={subTop} width={plotW} height={subH} className="pane-bg sub-pane" /> : null}
      {view.length === 0 ? (
        <text x={width / 2} y={height / 2} textAnchor="middle" className="empty-chart">market data unavailable</text>
      ) : null}
      {[0, 0.25, 0.5, 0.75, 1].map((tick) => (
        <line key={tick} x1={pad.left} x2={width - pad.right} y1={pad.top + tick * plotH} y2={pad.top + tick * plotH} className="grid-line" />
      ))}
      {[0, 0.5, 1].map((tick) => (
        <line key={`v-${tick}`} x1={pad.left} x2={width - pad.right} y1={volumeTop + tick * volumeH} y2={volumeTop + tick * volumeH} className="grid-line soft" />
      ))}
      {subH > 0 ? [0, 0.5, 1].map((tick) => (
        <line key={`s-${tick}`} x1={pad.left} x2={width - pad.right} y1={subTop + tick * subH} y2={subTop + tick * subH} className="grid-line soft" />
      )) : null}
      {view.map((candle, index) => {
        const cx = x(index);
        const up = candle.close >= candle.open;
        const bodyTop = y(Math.max(candle.open, candle.close));
        const bodyBottom = y(Math.min(candle.open, candle.close));
        const volumeY = vy(candle.volume);
        return (
          <g key={candle.open_time}>
            <rect x={cx - candleWidth / 2} y={volumeY} width={candleWidth} height={Math.max(1, volumeTop + volumeH - volumeY)} className={up ? "volume-bar up" : "volume-bar down"} />
            <line x1={cx} x2={cx} y1={y(candle.high)} y2={y(candle.low)} className={up ? "wick up" : "wick down"} />
            <rect x={cx - candleWidth / 2} y={bodyTop} width={candleWidth} height={Math.max(2, bodyBottom - bodyTop)} className={up ? "body up" : "body down"} />
          </g>
        );
      })}
      {series.filter((item) => item.pane === "main").flatMap((item, index) => renderMainSeries(item, view, index, x, y))}
      {renderSignalMarkers(markers, view, x, y)}
      {renderExecutionMarkers(executionMarkers, view, x, y)}
      {subH > 0 ? subSeries.flatMap((item, index) => renderSubSeries(item, view, index, x, subTop, subH)) : null}
      <text x={pad.left} y={height - 10} className="axis-label">{view[0] ? compactDate(view[0].open_time) : ""}</text>
      <text x={width - pad.right - 112} y={height - 10} className="axis-label">{view.at(-1) ? compactTime(view.at(-1)!.open_time) : ""}</text>
      <text x={width - pad.right + 8} y={pad.top + 12} className="price-label">{Number.isFinite(priceMax) ? priceMax.toFixed(2) : ""}</text>
      <text x={width - pad.right + 8} y={pad.top + plotH - 4} className="price-label">{Number.isFinite(priceMin) ? priceMin.toFixed(2) : ""}</text>
      <text x={pad.left + 8} y={volumeTop + 13} className="axis-label">Volume</text>
    </svg>
  );
}

function renderMainSeries(item: OverlaySeries, candles: Candle[], seriesIndex: number, x: (index: number) => number, y: (value: number) => number) {
  const paths: ReactElement[] = [];
  const keyPrefix = `${item.name}-${seriesIndex}`;
  if (item.points) {
    const d = pointPath(item.points, candles, x, y);
    if (d) paths.push(<path key={`${keyPrefix}-line`} d={d} className={`overlay-line ${item.overlay_type} ${item.style ?? "solid"}`} />);
  }
  if (item.band) {
    const area = bandAreaPath(item.band.upper, item.band.lower, candles, x, y);
    if (area) paths.push(<path key={`${keyPrefix}-fill`} d={area} className="band-fill" />);
    for (const [name, points] of Object.entries(item.band)) {
      const d = pointPath(points as OverlayPoint[], candles, x, y);
      if (d) paths.push(<path key={`${keyPrefix}-${name}`} d={d} className={`overlay-line bollinger ${name}`} />);
    }
  }
  item.zones?.forEach((zone, index) => {
    const startIndex = clampIndex(indexForTime(candles, zone.from), candles.length);
    const endIndex = clampIndex(indexForTime(candles, zone.to), candles.length, candles.length - 1);
    paths.push(
      <rect
        key={`${keyPrefix}-zone-${index}`}
        x={x(startIndex)}
        y={y(zone.price_high)}
        width={Math.max(1, x(endIndex) - x(startIndex))}
        height={Math.max(2, y(zone.price_low) - y(zone.price_high))}
        className={item.overlay_type.includes("support") ? "zone support" : "zone resistance"}
      />,
    );
  });
  return paths;
}

function renderSubSeries(
  item: OverlaySeries,
  candles: Candle[],
  seriesIndex: number,
  x: (index: number) => number,
  top: number,
  height: number,
) {
  const values = item.points?.map((point) => point.v).filter((value): value is number => value != null) ?? [];
  const min = item.scale?.min ?? Math.min(...values, 0);
  const max = item.scale?.max ?? Math.max(...values, 1);
  const y = (value: number) => top + (1 - (value - min) / Math.max(1, max - min)) * height;
  const paths: ReactElement[] = [];
  if (item.constant != null) {
    const lineY = y(item.constant);
    paths.push(<line key={`${item.name}-constant-${seriesIndex}`} x1={58} x2={842} y1={lineY} y2={lineY} className="sub-constant" />);
  }
  if (item.points) {
    const d = pointPath(item.points, candles, x, y);
    if (d) paths.push(<path key={`${item.name}-sub-${seriesIndex}`} d={d} className={`overlay-line sub ${item.overlay_type}`} />);
  }
  return paths;
}

function renderSignalMarkers(markers: OverlayMarker[], candles: Candle[], x: (index: number) => number, y: (value: number) => number) {
  return markers.flatMap((marker): ReactElement[] => {
    const index = indexForTime(candles, marker.t);
    if (index < 0) return [];
    const candle = candles[index];
    const isBuy = marker.overlay_type.includes("buy");
    const cx = x(index);
    const cy = isBuy ? y(candle.low) + 18 : y(candle.high) - 18;
    return [
      <path key={`${marker.t}-${marker.overlay_type}-shape`} d={isBuy ? triangleUp(cx, cy) : triangleDown(cx, cy)} className={isBuy ? "signal-marker buy" : "signal-marker sell"} />,
      <text key={`${marker.t}-${marker.overlay_type}-text`} x={cx} y={isBuy ? cy + 4 : cy + 3} textAnchor="middle" className="signal-text">{isBuy ? "B" : "S"}</text>,
    ];
  });
}

function renderExecutionMarkers(markers: ExecutionMarker[], candles: Candle[], x: (index: number) => number, y: (value: number) => number) {
  return markers.flatMap((marker, index): ReactElement[] => {
    if (marker.price == null) return [];
    const markerIndex = indexForTime(candles, marker.t);
    if (markerIndex < 0) return [];
    const cx = x(markerIndex);
    const cy = y(marker.price);
    if (marker.overlay_type === "take_profit" || marker.overlay_type === "stop_loss") {
      const endIndex = clampIndex(indexForTime(candles, marker.line_until ?? marker.t), candles.length, candles.length - 1);
      const label = marker.overlay_type === "take_profit" ? "TP" : "SL";
      return [
        <line key={`${marker.overlay_type}-${index}`} x1={cx} x2={x(endIndex)} y1={cy} y2={cy} className={`risk-line ${marker.overlay_type}`} />,
        <text key={`${marker.overlay_type}-${index}-label`} x={Math.min(x(endIndex) + 5, 830)} y={cy - 4} className={`risk-label ${marker.overlay_type}`}>{label}</text>,
      ];
    }
    if (marker.overlay_type === "entry") {
      return [
        <circle key={`entry-${index}`} cx={cx} cy={cy} r="5" className="exec-marker entry" />,
        <text key={`entry-${index}-label`} x={cx + 8} y={cy - 8} className="exec-label">ENTRY</text>,
      ];
    }
    if (marker.overlay_type === "exit") {
      return [
        <path key={`exit-${index}`} d={crossPath(cx, cy)} className={`exec-marker exit ${marker.exit_reason ?? ""}`} />,
        <text key={`exit-${index}-label`} x={cx + 8} y={cy + 13} className="exec-label">EXIT</text>,
      ];
    }
    return [];
  });
}

function pointPath(points: OverlayPoint[], candles: Candle[], x: (index: number) => number, y: (value: number) => number) {
  const visible = points
    .map((point) => ({ point, index: indexForTime(candles, point.t) }))
    .filter(({ point, index }) => index >= 0 && point.v != null);
  return visible.map(({ point, index }, i) => `${i === 0 ? "M" : "L"}${x(index)},${y(point.v as number)}`).join(" ");
}

function bandAreaPath(upper: OverlayPoint[], lower: OverlayPoint[], candles: Candle[], x: (index: number) => number, y: (value: number) => number) {
  const upperCoords = upper
    .map((point) => ({ point, index: indexForTime(candles, point.t) }))
    .filter(({ point, index }) => index >= 0 && point.v != null)
    .map(({ point, index }) => `${x(index)},${y(point.v as number)}`);
  const lowerCoords = lower
    .map((point) => ({ point, index: indexForTime(candles, point.t) }))
    .filter(({ point, index }) => index >= 0 && point.v != null)
    .map(({ point, index }) => `${x(index)},${y(point.v as number)}`)
    .reverse();
  if (upperCoords.length < 2 || lowerCoords.length < 2) return "";
  return `M${upperCoords.join(" L")} L${lowerCoords.join(" L")} Z`;
}

function EquityChart({ points }: { points: EquityPoint[] }) {
  const width = 360;
  const height = 128;
  if (points.length === 0) {
    return <svg className="equity-svg" viewBox={`0 0 ${width} ${height}`}><text x="180" y="70" textAnchor="middle">equity unavailable</text></svg>;
  }
  const values = points.map((point) => point.equity);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const minDrawdown = Math.min(...points.map((point) => point.drawdown_pct), 0);
  const path = points.map((point, index) => {
    const px = (index / Math.max(1, points.length - 1)) * (width - 20) + 10;
    const py = 10 + (1 - (point.equity - minValue) / Math.max(1, maxValue - minValue)) * (height - 24);
    return `${index === 0 ? "M" : "L"}${px},${py}`;
  }).join(" ");
  const drawdownPath = points.map((point, index) => {
    const px = (index / Math.max(1, points.length - 1)) * (width - 20) + 10;
    const py = height - 12 - (Math.abs(point.drawdown_pct) / Math.max(1, Math.abs(minDrawdown))) * (height - 34);
    return `${index === 0 ? "M" : "L"}${px},${py}`;
  }).join(" ");
  return <svg className="equity-svg" viewBox={`0 0 ${width} ${height}`}><path className="drawdown" d={drawdownPath} /><path className="equity" d={path} /></svg>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong></div>;
}

function strategyName(strategies: Strategy[], key: string): string {
  const [id, version] = key.split("@");
  return strategies.find((strategy) => strategy.strategy_id === id && strategy.version === version)?.display_name ?? key;
}

function formatNumber(value?: number | null): string {
  if (value == null || Number.isNaN(value)) return "0.00";
  return value.toFixed(2);
}

function formatPrice(value: number): string {
  return value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatCompact(value: number): string {
  return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 2 }).format(value);
}

function compactDate(value: string): string {
  return new Date(value).toLocaleDateString("en-US", { month: "2-digit", day: "2-digit", timeZone: "UTC" });
}

function compactTime(value: string): string {
  return `${new Date(value).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC" })} UTC`;
}

function compactDateTime(value: string): string {
  return new Date(value).toLocaleString("en-US", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "UTC",
  });
}

function messageFromError(error: unknown): string {
  return error instanceof Error ? error.message : "Request failed";
}

function upsertCandle(candles: Candle[], candle: Candle): Candle[] {
  const next = candles.filter((item) => item.open_time !== candle.open_time);
  next.push(candle);
  return next.sort((a, b) => a.open_time.localeCompare(b.open_time)).slice(-180);
}

function indexForTime(candles: Candle[], value: string): number {
  const direct = candles.findIndex((candle) => candle.open_time === value);
  if (direct >= 0) return direct;
  const target = Date.parse(value);
  if (!Number.isFinite(target)) return -1;
  return candles.findIndex((candle) => Date.parse(candle.open_time) === target);
}

function clampIndex(value: number, length: number, fallback = 0): number {
  if (length <= 0) return 0;
  if (value < 0) return Math.max(0, Math.min(length - 1, fallback));
  return Math.max(0, Math.min(length - 1, value));
}

function triangleUp(x: number, y: number) {
  return `M${x},${y - 11} L${x - 9},${y + 7} L${x + 9},${y + 7} Z`;
}

function triangleDown(x: number, y: number) {
  return `M${x},${y + 11} L${x - 9},${y - 7} L${x + 9},${y - 7} Z`;
}

function crossPath(x: number, y: number) {
  return `M${x - 7},${y - 7} L${x + 7},${y + 7} M${x + 7},${y - 7} L${x - 7},${y + 7}`;
}
