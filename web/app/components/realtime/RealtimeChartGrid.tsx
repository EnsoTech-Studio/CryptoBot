"use client";

import { useWorkspace } from "../../providers/workspace";
import { RealtimeChartCard } from "./RealtimeChartCard";
import styles from "./realtime.module.css";

export function RealtimeChartGrid() {
  const { panels, chartCount } = useWorkspace();
  const visiblePanels = panels.slice(0, chartCount);

  return (
    <div className={styles.chartGrid} data-count={visiblePanels.length} aria-label={`${visiblePanels.length} biểu đồ theo khung thời gian`}>
      {visiblePanels.map((panel, index) => (
        <RealtimeChartCard key={panel.id} panel={panel} index={index} />
      ))}
    </div>
  );
}
