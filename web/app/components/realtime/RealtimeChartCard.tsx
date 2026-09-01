"use client";

import { formatPrice } from "../../../lib/format";
import type { OverlayMarker, OverlaySeries } from "../../../lib/api";
import { useWorkspace, type Panel } from "../../providers/workspace";
import { ChartCanvas } from "../charts/ChartCanvas";
import { Icon } from "../ui/Icon";
import styles from "./realtime.module.css";

export function RealtimeChartCard({ panel, index }: { panel: Panel; index: number }) {
  const {
    selectedMarket,
    focusIndex,
    setFocusIndex,
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
              <span className={styles.srStatus}>{panel.liveState === "live" ? "Live" : panel.liveState === "connecting" ? "Syncing" : panel.liveState === "paused" ? "Paused" : "Stale"}</span>
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
        <span className={styles.overlayValue}>
          {overlay ? `${overlay.name} ${formatPrice(overlay.value)}` : "Overlay chưa có dữ liệu"}
        </span>
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
          {!realtimeEnabled ? "Realtime đang tạm dừng" : "Cập nhật realtime"}
          <i data-state={panel.liveState} aria-hidden="true" />
        </span>
      </footer>
    </article>
  );
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
