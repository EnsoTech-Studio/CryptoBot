"use client";

import { MarketControls } from "./MarketControls";
import { RealtimeChartGrid } from "./RealtimeChartGrid";
import { RealtimeInfoRail } from "./RealtimeInfoRail";
import styles from "./realtime.module.css";

export function RealtimeScreen() {
  return (
    <section className={styles.screen} aria-label="Không gian biểu đồ thị trường theo thời gian thực">
      <MarketControls />
      <div className={styles.workspace}>
        <RealtimeChartGrid />
        <RealtimeInfoRail />
      </div>
    </section>
  );
}
