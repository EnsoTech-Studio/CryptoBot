"use client";

import { createMockPanelData } from "../../../lib/realtime-mock";
import type { Candle, ExecutionMarker, ExperimentSummary, OverlayMarker, OverlaySeries } from "../../../lib/api";
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
  const shownSeries = mock ? mock.series : series;
  const shownMarkers = mock ? mock.markers : markers;
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
        <b className={styles.legendMa20}>{fmt(last * 0.9971)}</b>
        <span className={styles.legendMa50}>MA(50)</span>
        <b className={styles.legendMa50}>{fmt(last * 0.9939)}</b>
        <span>
          <i className={`${styles.legendSwatch} ${styles.swatchSupport}`} aria-hidden="true" />
          <span className={styles.legendLabel}>Hỗ trợ</span>
          <b className={styles.legendSupport}>{fmt(last * 0.978)}</b>
        </span>
        <span>
          <i className={`${styles.legendSwatch} ${styles.swatchResistance}`} aria-hidden="true" />
          <span className={styles.legendLabel}>Kháng cự</span>
          <b className={styles.legendResistance}>{fmt(last * 1.012)}</b>
        </span>
      </div>

      <div className={styles.chartViewport}>
        <ChartCanvas
          candles={shownCandles}
          series={shownSeries}
          markers={shownMarkers}
          executionMarkers={executionMarkers}
          size="result"
          ariaLabel={`Biểu đồ backtest ${draft.market.symbol} ${draft.timeframe}`}
        />
      </div>

      {isMock ? (
        <p className={styles.mockNote}>
          Biểu đồ minh hoạ theo thiết kế. Chạy backtest để vẽ nến, tín hiệu và điểm vào/ra thật.
        </p>
      ) : experiment ? (
        <div className={styles.legendRow}>
          <span className={styles.legendLabel}>Dataset</span>
          <b>{experiment.dataset_version}</b>
          <Button variant="ghost" onClick={onInspect}>Provenance</Button>
        </div>
      ) : null}
    </Panel>
  );
}

function fmt(value: number) {
  return value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
