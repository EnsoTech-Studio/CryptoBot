"use client";

import { LOOP_STEPS } from "../../../lib/discovery-mock";
import { Panel, StepFlow } from "../ui/Foundation";
import { Icon } from "../ui/Icon";
import styles from "./discovery.module.css";

/* Column 3, top: the five-stage loop. Static process documentation, except the
   active stage which follows the real run status. */
export function DiscoveryWorkflow({ status }: { status?: string }) {
  return (
    <Panel title="Loop Discovery" info="Vòng lặp tự động: sinh biến thể, backtest, đánh giá, xếp hạng.">
      <div className={styles.loopFlow}>
        <StepFlow steps={LOOP_STEPS} current={stageIndex(status)} />
        <span className={styles.loopReturn} aria-hidden="true"><Icon name="arrow-up" /></span>
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
      return 4;
  }
}
