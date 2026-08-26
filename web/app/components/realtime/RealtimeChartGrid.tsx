"use client";

import { useWorkspace } from "../../providers/workspace";
import { RealtimeChartCard } from "./RealtimeChartCard";
import styles from "./realtime.module.css";

export function RealtimeChartGrid() {
  const { panels } = useWorkspace();

  return (
    <div className={styles.chartGrid} data-count={panels.length} aria-label={`${panels.length} biểu đồ theo khung thời gian`}>
      {panels.map((panel, index) => (
        <RealtimeChartCard key={panel.id} panel={panel} index={index} />
      ))}
    </div>
  );
}
