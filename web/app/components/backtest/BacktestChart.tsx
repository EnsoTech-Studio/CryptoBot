"use client";

import { useState } from "react";

import { createMockPanelData } from "../../../lib/realtime-mock";
import { mockExecutionMarkers } from "../../../lib/backtest-mock";
import { DISPLAY_TIME_ZONE } from "../../../lib/format";
import type { Candle, ExecutionMarker, ExperimentSummary, OverlayMarker, OverlayPoint, OverlaySeries } from "../../../lib/api";
import type { BacktestDraft } from "../../../lib/backtest";
import { isExecutionMarkerSelected } from "../../../lib/backtest";
import { Button, Panel } from "../ui/Foundation";
import { ChartCanvas } from "../charts/ChartCanvas";
import { Icon } from "../ui/Icon";
import styles from "./backtest.module.css";

/* Result chart with the reference's legend row. Series and markers are whatever
   the completed run persisted; when nothing has run, a deterministic candle set
   fills the frame so the layout matches the image. */
export function BacktestChart({
  draft,
  experiment,
  candles,
  series,
  markers,
  executionMarkers,
  isMock,
  empty,
  onRun,
  runDisabled,
  runLabel,
  selectedTradeSequence,
}: {
  draft: BacktestDraft;
  experiment: ExperimentSummary | null;
  candles: Candle[];
  series: OverlaySeries[];
  markers: OverlayMarker[];
  executionMarkers: ExecutionMarker[];
  isMock: boolean;
  empty: boolean;
  onRun: () => void;
  runDisabled: boolean;
  runLabel: string;
  selectedTradeSequence: number | null;
}) {
  const mock = isMock ? createMockPanelData(draft.market, draft.timeframe, 180) : null;
  const shownCandles = mock ? mock.candles : candles;
  /* Keep mock overlays on same price scale as selected market. The former
     fixed BTC values flattened non-BTC candles into what looked like dots. */
  const shownSeries = mock ? [mock.series[0], createMockMa50(mock.candles)] : series;
  const shownMarkers = mock ? mock.markers : markers;
  const shownExecutionMarkers = (mock ? mockExecutionMarkers(mock.candles) : executionMarkers).map((marker) => ({
    ...marker,
    selected: isExecutionMarkerSelected(marker, selectedTradeSequence),
  }));
  const firstExecutionTime = shownExecutionMarkers[0]?.t ?? "";
  const lastExecutionTime = shownExecutionMarkers.at(-1)?.t ?? "";
  const windowKey = `${shownCandles.length}:${shownCandles[0]?.open_time ?? ""}:${shownCandles.at(-1)?.open_time ?? ""}:${shownExecutionMarkers.length}:${firstExecutionTime}:${lastExecutionTime}`;
  const maximum = Math.max(0, shownCandles.length - 1);
  const [savedWindow, setSavedWindow] = useState(() => defaultWindow(windowKey, maximum, shownCandles, shownExecutionMarkers));
  /* A new run is a new visual context. Start on a readable trailing candle
     window until the user moves a thumb, rather than resetting in an effect. */
  const activeWindow = savedWindow.key === windowKey ? savedWindow : defaultWindow(windowKey, maximum, shownCandles, shownExecutionMarkers);
  const start = Math.min(activeWindow.start, maximum);
  const end = Math.max(start, Math.min(activeWindow.end, maximum));
  const windowCandles = shownCandles.slice(start, end + 1);
  const windowFrom = windowCandles[0]?.open_time;
  const windowTo = windowCandles.at(-1)?.open_time;
  const windowClose = windowCandles.at(-1)?.close_time;
  const windowExecutionMarkers = shownExecutionMarkers
    .filter((marker) => isWithinWindow(marker.t, windowFrom, windowClose))
    .filter((marker) => marker.overlay_type !== "stop_loss" && marker.overlay_type !== "take_profit");
  const last = windowCandles.at(-1)?.close ?? 0;
  const windowCount = windowCandles.length;
  const ma20 = lastSeriesValue(shownSeries[0]) ?? last;
  const ma50 = lastSeriesValue(shownSeries[1]) ?? last;
  const support = Math.min(...windowCandles.map((candle) => candle.low), last);
  const resistance = Math.max(...windowCandles.map((candle) => candle.high), last);
  const chartTitle = `Biểu đồ Backtest (${experiment?.symbol ?? draft.market.symbol} · ${experiment?.timeframe ?? draft.timeframe})`;

  if (empty) {
    return (
      <Panel title={chartTitle}>
        <div className={styles.chartEmpty}>
          <span>Chạy backtest để xem nến, tín hiệu và các lệnh đã khớp.</span>
          <Button variant="primary" disabled={runDisabled} onClick={onRun}>
            <Icon name="play" aria-hidden="true" />
            {runLabel}
          </Button>
        </div>
      </Panel>
    );
  }

  return (
    <Panel
      title={chartTitle}
      action={
        <span className={styles.chartActions}>
          <Button variant="primary" disabled={runDisabled} onClick={onRun}>
            <Icon name="play" aria-hidden="true" />
            {runLabel}
          </Button>
        </span>
      }
    >
      <div className={styles.legendRow}>
        <span className={styles.legendMa20}>MA(20)</span>
        <b className={styles.legendMa20}>{fmt(ma20)}</b>
        <span className={styles.legendMa50}>MA(50)</span>
        <b className={styles.legendMa50}>{fmt(ma50)}</b>
        <span>
          <i className={`${styles.legendSwatch} ${styles.swatchSupport}`} aria-hidden="true" />
          <span className={styles.legendLabel}>Hỗ trợ</span>
          <b className={styles.legendSupport}>{fmt(support)}</b>
        </span>
        <span>
          <i className={`${styles.legendSwatch} ${styles.swatchResistance}`} aria-hidden="true" />
          <span className={styles.legendLabel}>Kháng cự</span>
          <b className={styles.legendResistance}>{fmt(resistance)}</b>
        </span>
      </div>

      <div className={styles.chartViewport}>
        <ChartCanvas
          candles={windowCandles}
          series={shownSeries}
          markers={shownMarkers}
          showSignalMarkers={false}
          executionMarkers={windowExecutionMarkers}
          size="result"
          visibleLimit={windowCount}
          ariaLabel={`Biểu đồ backtest ${draft.market.symbol} ${draft.timeframe}`}
        />
      </div>

      {shownCandles.length > 1 ? (
        <div className={styles.chartWindow} aria-label="Cửa sổ dữ liệu hiển thị trên biểu đồ">
          <div className={styles.chartWindowHead}>
            <span>Khung xem chart</span>
            <b>{formatWindowTime(windowFrom)} → {formatWindowTime(windowTo)}</b>
            <span>{windowCount.toLocaleString("en-US")} nến</span>
          </div>
          <div className={styles.chartWindowSliders}>
            <span
              className={styles.chartWindowFill}
              aria-hidden="true"
              style={{ left: `${maximum === 0 ? 0 : start / maximum * 100}%`, width: `${maximum === 0 ? 100 : (end - start) / maximum * 100}%` }}
            />
            <input
              type="range"
              min="0"
              max={maximum}
              value={start}
              className={styles.chartWindowStart}
              aria-label="Bắt đầu cửa sổ chart"
              aria-valuetext={formatWindowTime(shownCandles[start]?.open_time)}
              onChange={(event) => setSavedWindow({ key: windowKey, start: Math.min(Number(event.target.value), end), end })}
            />
            <input
              type="range"
              min="0"
              max={maximum}
              value={end}
              className={styles.chartWindowEnd}
              aria-label="Kết thúc cửa sổ chart"
              aria-valuetext={formatWindowTime(shownCandles[end]?.open_time)}
              onChange={(event) => setSavedWindow({ key: windowKey, start, end: Math.max(Number(event.target.value), start) })}
            />
          </div>
        </div>
      ) : null}

      {!isMock && experiment ? (
        <div className={styles.legendRow}>
          <span className={styles.legendLabel}>Dataset</span>
          <b>{experiment.dataset_version}</b>
        </div>
      ) : null}
    </Panel>
  );
}

function createMockMa50(candles: Candle[]): OverlaySeries {
  const windowSize = 50;
  const points: OverlayPoint[] = candles.map((candle, index) => {
    if (index < windowSize - 1) return { t: candle.open_time, v: null };
    const window = candles.slice(index - windowSize + 1, index + 1);
    return { t: candle.open_time, v: Number((window.reduce((sum, item) => sum + item.close, 0) / window.length).toFixed(2)) };
  });
  return { name: "MA(50)", overlay_type: "moving_average_50", pane: "main", points, style: "solid" };
}

function defaultWindow(key: string, maximum: number, candles: Candle[] = [], executionMarkers: ExecutionMarker[] = []) {
  const defaultVisibleCandles = 80;
  const markerIndices = executionMarkers
    .map((marker) => candleIndexForTime(candles, marker.t))
    .filter((index): index is number => index >= 0);
  if (markerIndices.length === 0) {
    return { key, start: Math.max(0, maximum - defaultVisibleCandles + 1), end: maximum };
  }

  const markerStart = Math.min(...markerIndices);
  const markerEnd = Math.max(...markerIndices);
  const markerSpan = markerEnd - markerStart + 1;
  const visible = Math.min(maximum + 1, Math.max(defaultVisibleCandles, Math.min(markerSpan, 240)));
  const start = markerSpan <= 240
    ? markerStart - Math.floor((visible - markerSpan) / 2)
    : markerEnd - visible + 1;
  const boundedStart = Math.max(0, Math.min(maximum - visible + 1, start));
  return { key, start: boundedStart, end: boundedStart + visible - 1 };
}

function candleIndexForTime(candles: Candle[], value: string): number {
  const target = Date.parse(value);
  if (!Number.isFinite(target)) return -1;
  return candles.findIndex((candle) => {
    const open = Date.parse(candle.open_time);
    const close = Date.parse(candle.close_time);
    return Number.isFinite(open) && Number.isFinite(close) && target >= open && target <= close;
  });
}

function lastSeriesValue(series: OverlaySeries | undefined) {
  const points = series?.points ?? [];
  for (let index = points.length - 1; index >= 0; index -= 1) {
    if (points[index].v != null) return points[index].v;
  }
  return null;
}

function fmt(value: number) {
  return value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function isWithinWindow(value: string, from?: string, to?: string) {
  if (!from || !to) return false;
  const time = Date.parse(value);
  return Number.isFinite(time) && time >= Date.parse(from) && time <= Date.parse(to);
}

function formatWindowTime(value?: string) {
  if (!value) return "—";
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return value;
  return new Intl.DateTimeFormat("vi-VN", {
    timeZone: DISPLAY_TIME_ZONE,
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).format(date);
}
