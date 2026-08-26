"use client";

import { LOOP_STEPS } from "../../../lib/discovery-mock";
import { Panel, StepFlow } from "../ui/Foundation";
import styles from "./discovery.module.css";

/* Column 3, top: the five-stage loop. Static process documentation, except the
   active stage which follows the real run status. */
export function DiscoveryWorkflow({ status }: { status?: string }) {
  return (
    <Panel title="Loop Discovery" info="Vòng lặp tự động: sinh biến thể, backtest, đánh giá, xếp hạng.">
      <div className={styles.loopFlow}>
        <StepFlow steps={LOOP_STEPS} current={stageIndex(status)} />
      </div>
    </Panel>
  );
}

function stageIndex(status?: string): number | undefined {
  switch (status) {
    case "queued":
      return 0;
    case "running":
      return 1;
    case "paused":
      return 2;
    case "completed":
      return 4;
    default:
      return undefined;
  }
}
