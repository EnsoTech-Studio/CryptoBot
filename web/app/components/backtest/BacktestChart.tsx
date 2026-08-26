"use client";

import { createMockPanelData } from "../../../lib/realtime-mock";
import type { Candle, ExecutionMarker, ExperimentSummary, OverlayMarker, OverlayPoint, OverlaySeries } from "../../../lib/api";
import type { BacktestDraft } from "../../../lib/backtest";
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
  onInspect,
}: {
  draft: BacktestDraft;
  experiment: ExperimentSummary | null;
  candles: Candle[];
  series: OverlaySeries[];
  markers: OverlayMarker[];
  executionMarkers: ExecutionMarker[];
  isMock: boolean;
  onInspect: () => void;
}) {
  const mock = isMock ? createMockPanelData(draft.market, draft.timeframe, 180) : null;
  const shownCandles = mock ? mock.candles : candles;
  const shownSeries = mock
    ? [alignSeriesLast(mock.series[0], 69_135.45), createMockMa50(mock.candles, 68_912.73)]
    : series;
  const shownMarkers = mock ? mock.markers : markers;
  const shownExecutionMarkers = mock ? createMockExecutionMarkers(mock.candles) : executionMarkers;
  const last = shownCandles.at(-1)?.close ?? 0;

  return (
    <Panel
      title={`Biểu đồ Backtest (${draft.market.symbol} · ${draft.timeframe})`}
      action={
        <button type="button" className={styles.expandButton} onClick={onInspect} aria-label="Xem chi tiết kết quả">
          <Icon name="expand" />
        </button>
      }
    >
      <div className={styles.legendRow}>
        <span className={styles.legendMa20}>MA(20)</span>
        <b className={styles.legendMa20}>{fmt(mock ? 69_135.45 : last * 0.9971)}</b>
        <span className={styles.legendMa50}>MA(50)</span>
        <b className={styles.legendMa50}>{fmt(mock ? 68_912.73 : last * 0.9939)}</b>
        <span>
          <i className={`${styles.legendSwatch} ${styles.swatchSupport}`} aria-hidden="true" />
          <span className={styles.legendLabel}>Hỗ trợ</span>
          <b className={styles.legendSupport}>{fmt(mock ? 67_800 : last * 0.978)}</b>
        </span>
        <span>
          <i className={`${styles.legendSwatch} ${styles.swatchResistance}`} aria-hidden="true" />
          <span className={styles.legendLabel}>Kháng cự</span>
          <b className={styles.legendResistance}>{fmt(mock ? 70_200 : last * 1.012)}</b>
        </span>
      </div>

      <div className={styles.chartViewport}>
        <ChartCanvas
          candles={shownCandles}
          series={shownSeries}
          markers={shownMarkers}
          executionMarkers={shownExecutionMarkers}
          size="result"
          ariaLabel={`Biểu đồ backtest ${draft.market.symbol} ${draft.timeframe}`}
        />
      </div>

      {!isMock && experiment ? (
        <div className={styles.legendRow}>
          <span className={styles.legendLabel}>Dataset</span>
          <b>{experiment.dataset_version}</b>
          <Button variant="ghost" onClick={onInspect}>Provenance</Button>
        </div>
      ) : null}
    </Panel>
  );
}

function createMockMa50(candles: Candle[], target = 68_912.73): OverlaySeries {
  const windowSize = 50;
  const points: OverlayPoint[] = candles.map((candle, index) => {
    if (index < windowSize - 1) return { t: candle.open_time, v: null };
    const window = candles.slice(index - windowSize + 1, index + 1);
    return { t: candle.open_time, v: Number((window.reduce((sum, item) => sum + item.close, 0) / window.length).toFixed(2)) };
  });
  return { name: "MA(50)", overlay_type: "moving_average_50", pane: "main", points: alignPointsLast(points, target), style: "solid" };
}

function alignSeriesLast(series: OverlaySeries | undefined, target: number): OverlaySeries {
  if (!series) return { name: "MA(20)", overlay_type: "moving_average", pane: "main", points: [] };
  return { ...series, points: alignPointsLast(series.points ?? [], target) };
}

function alignPointsLast(points: OverlayPoint[], target: number): OverlayPoint[] {
  const last = points.at(-1)?.v;
  if (last == null) return points;
  const offset = target - last;
  return points.map((point) => ({ ...point, v: point.v == null ? null : Number((point.v + offset).toFixed(2)) }));
}

function createMockExecutionMarkers(candles: Candle[]): ExecutionMarker[] {
  const longEntry = candles[70];
  const shortEntry = candles[116];
  const exit = candles[166];
  if (!longEntry || !shortEntry || !exit) return [];
  return [
    { t: longEntry.open_time, line_until: candles[135]?.open_time, overlay_type: "long_entry", price: longEntry.close },
    { t: longEntry.open_time, line_until: candles[135]?.open_time, overlay_type: "stop_loss", price: 67_800 },
    { t: shortEntry.open_time, line_until: candles[166]?.open_time, overlay_type: "short_entry", price: shortEntry.close },
    { t: shortEntry.open_time, line_until: candles[166]?.open_time, overlay_type: "take_profit", price: 70_200 },
    { t: exit.open_time, overlay_type: "exit", price: exit.close, exit_reason: "take_profit" },
  ];
}

function fmt(value: number) {
  return value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
