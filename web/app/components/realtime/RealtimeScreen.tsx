"use client";

import { MarketControls } from "./MarketControls";
import { RealtimeChartGrid } from "./RealtimeChartGrid";
import { RealtimeInfoRail } from "./RealtimeInfoRail";
import { useWorkspace } from "../../providers/workspace";
import styles from "./realtime.module.css";

export function RealtimeScreen() {
  const { chartCount } = useWorkspace();

  return (
    <section className={styles.screen} aria-label="Không gian biểu đồ thị trường theo thời gian thực">
      <div className={styles.workspace} data-chart-count={chartCount}>
        <div className={styles.marketColumn}>
          <MarketControls />
          <RealtimeChartGrid />
        </div>
        <RealtimeInfoRail />
      </div>
    </section>
  );
}
