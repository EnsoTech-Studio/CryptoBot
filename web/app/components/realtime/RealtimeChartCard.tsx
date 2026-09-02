"use client";

import { formatPrice } from "../../../lib/format";
import { REALTIME_TIMEFRAME_OPTIONS } from "../../../lib/market";
import type { OverlayMarker, OverlaySeries } from "../../../lib/api";
import { useWorkspace, type LiveState, type Panel } from "../../providers/workspace";
import { ChartCanvas } from "../charts/ChartCanvas";
import { Icon } from "../ui/Icon";
import styles from "./realtime.module.css";

export function RealtimeChartCard({ panel, index }: { panel: Panel; index: number }) {
  const {
    selectedMarket,
    focusIndex,
    setFocusIndex,
    availableTimeframes,
    panelHandlers,
    loadHistory,
    realtimeEnabled,
    dataMode,
  } = useWorkspace();
  const lastCandle = panel.candles.at(-1);
  const priceChange = dataMode === "mock"
    ? panel.timeframe === "1h" ? -0.15 : 0.28
    : lastCandle && lastCandle.open !== 0
      ? ((lastCandle.close - lastCandle.open) / lastCandle.open) * 100
      : null;
  const signal = latestSignal(panel.markers);
  const overlay = latestMainOverlay(panel.series);
  const signalLabel = signal?.side === "buy" ? "BUY" : signal?.side === "sell" ? "SELL" : "No signal";
  const chartSummary = lastCandle
    ? `${selectedMarket.symbol} ${panel.timeframe}, giá đóng cửa ${formatPrice(lastCandle.close)}, ${signalLabel}${dataMode === "mock" ? ", dữ liệu mô phỏng" : ""}`
    : `${selectedMarket.symbol} ${panel.timeframe}, chưa có dữ liệu thị trường`;
  const timeframeOptions = REALTIME_TIMEFRAME_OPTIONS
    .filter((timeframe) => availableTimeframes.includes(timeframe));
  const onTimeframe = panelHandlers(index).onTimeframe;

  return (
    <article className={`${styles.chartCard} ${focusIndex === index ? styles.chartCardFocused : ""}`}>
      <header className={styles.chartHeader}>
        <div className={styles.chartIdentityBlock}>
          <button
            type="button"
            className={styles.chartIdentity}
            onClick={() => setFocusIndex(index)}
            aria-label={`Tập trung biểu đồ ${selectedMarket.symbol} ${panel.timeframe}`}
            aria-pressed={focusIndex === index}
          >
            <span className={styles.symbol}>{selectedMarket.symbol}</span>
            <span className={styles.liveState} data-state={panel.liveState}>
              <i aria-hidden="true" />
              <span className={styles.statusLabel}>{liveStateLabel(panel.liveState)}</span>
            </span>
          </button>
          <span className={styles.chartSeparator} aria-hidden="true">·</span>
          <span className={styles.timeframeText}>{panel.timeframe}</span>
        </div>
        <div className={styles.quote}>
          <strong>{lastCandle ? formatPrice(lastCandle.close) : "—"}</strong>
          <span className={priceChange == null || priceChange >= 0 ? styles.positive : styles.negative}>
            {priceChange == null ? "Đang chờ dữ liệu" : `${priceChange >= 0 ? "+" : ""}${priceChange.toFixed(2)}%`}
          </span>
        </div>
        <span className={`${styles.signalBadge} ${signal?.side ? styles[signal.side] : styles.noSignal}`}>{signalLabel}</span>
      </header>

      <div className={styles.chartMeta}>
        <div className={styles.chartTimeframeControl}>
          <span className={styles.chartControlLabel}>Khung</span>
          <select
            className={styles.chartTimeframeSelect}
            value={panel.timeframe}
            aria-label={`Khung thời gian cho biểu đồ ${selectedMarket.symbol}`}
            onChange={(event) => onTimeframe(event.target.value)}
          >
            {timeframeOptions.map((timeframe) => (
              <option
                key={timeframe}
              >
                {timeframe}
              </option>
            ))}
          </select>
        </div>
        <span className={styles.overlayValue}>
          {overlay ? `${overlay.name} ${formatPrice(overlay.value)}` : "Overlay chưa có dữ liệu"}
        </span>
        <div className={styles.chartTelemetry} aria-label={`Telemetry ${selectedMarket.symbol} ${panel.timeframe}`}>
          <span><b>Latency</b> {panel.latencyMs == null ? "—" : `${panel.latencyMs} ms`}</span>
          <span><b>Last</b> {panel.lastFrameAt ? formatUtcTime(panel.lastFrameAt) : "—"}</span>
        </div>
      </div>

      <div className={styles.chartViewport} aria-busy={!panel.loaded}>
        {!panel.loaded && panel.candles.length === 0 ? (
          <div className={styles.chartSkeleton} aria-label="Đang tải biểu đồ"><span /><span /><span /></div>
        ) : (
          <ChartCanvas
            candles={panel.candles}
            series={panel.series}
            markers={panel.markers}
            size="realtime"
            ariaLabel={chartSummary}
          />
        )}
      </div>

      {panel.error ? <p className={styles.chartError} role="status">{panel.error}</p> : null}

      <footer className={styles.chartFooter}>
        <button
          type="button"
          className={styles.historyButton}
          onClick={() => void loadHistory(index)}
          disabled={panel.historyLoading}
        >
          <Icon name="download" />
          {panel.historyLoading ? "Đang tải…" : panel.historyLimit >= 1_000 ? "1000 nến lịch sử" : "Load 1000 nến lịch sử"}
        </button>
        <span className={styles.footerStatus}>
          <Icon name="refresh" aria-hidden="true" />
          {panel.liveState === "stale" ? "Dữ liệu stale" : panel.liveState === "unavailable" ? "Dữ liệu unavailable" : panel.liveState === "connecting" ? "Đang đồng bộ" : !realtimeEnabled ? "Realtime đang tạm dừng" : "Cập nhật realtime"}
          <i data-state={panel.liveState} aria-hidden="true" />
        </span>
      </footer>
    </article>
  );
}

function liveStateLabel(state: LiveState) {
  switch (state) {
    case "live": return "Live";
    case "connecting": return "Syncing";
    case "stale": return "Stale";
    case "unavailable": return "Unavailable";
    case "paused": return "Paused";
  }
}

function formatUtcTime(value: string) {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "—";
  return `${date.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit", timeZone: "Asia/Ho_Chi_Minh" })} ICT`;
}

function latestSignal(markers: OverlayMarker[]) {
  const marker = [...markers]
    .filter((item) => item.overlay_type.toLowerCase().includes("buy") || item.overlay_type.toLowerCase().includes("sell"))
    .sort((a, b) => a.t.localeCompare(b.t))
    .at(-1);
  if (!marker) return null;
  return { marker, side: marker.overlay_type.toLowerCase().includes("buy") ? "buy" as const : "sell" as const };
}

function latestMainOverlay(series: OverlaySeries[]) {
  for (const item of series.filter((entry) => entry.pane === "main")) {
    const point = item.points?.filter((entry) => entry.v != null).at(-1);
    if (point?.v != null) return { name: item.name, value: point.v };
    const middle = item.band?.middle.filter((entry) => entry.v != null).at(-1);
    if (middle?.v != null) return { name: `${item.name} mid`, value: middle.v };
  }
  return null;
}
