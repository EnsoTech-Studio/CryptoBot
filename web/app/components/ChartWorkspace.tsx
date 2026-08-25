"use client";

import { useWorkspace } from "../providers/workspace";
import { ChartPanel } from "./ChartPanel";

export function ChartWorkspace() {
  const { panels, focusIndex, setFocusIndex, strategies, panelHandlers } = useWorkspace();

  return (
    <section className="chart-workspace" aria-label="Realtime market dashboard">
      <ChartPanel
        key={panels[focusIndex].id}
        panel={panels[focusIndex]}
        variant="primary"
        strategies={strategies}
        {...panelHandlers(focusIndex)}
      />
      <div className="chart-context">
        {panels.map((panel, index) => index === focusIndex ? null : (
          <ChartPanel
            key={panel.id}
            panel={panel}
            variant="context"
            strategies={strategies}
            onFocus={() => setFocusIndex(index)}
            {...panelHandlers(index)}
          />
        ))}
      </div>
    </section>
  );
}
