"use client";

import { displayLabel, type DiscoveryDraft } from "../../../lib/discovery";
import type { Strategy } from "../../../lib/api";
import { Panel, WeightSlider } from "../ui/Foundation";
import { Icon, type IconName } from "../ui/Icon";
import styles from "./discovery.module.css";

const PARAM_SUMMARY: Record<string, string> = {
  ma_cross: "(20, 50)",
  ema_cross: "(20, 50)",
  rsi: "(14)",
  bollinger: "(20, 2)",
  macd: "(12, 26, 9)",
};

const ROW_ICON: Record<string, IconName> = {
  ma_cross: "ma",
  ema_cross: "chart",
  rsi: "activity",
  bollinger: "bollinger",
  macd: "bar-chart",
  support_resistance: "support-resistance",
  news_sentiment: "document",
};

/* Column 2, middle: the weight editor plus the aggregate signal tiles.
   Weights only apply to weighted_vote — the backend majority_vote combiner
   ignores them, so only the controls are visually subdued while the configured
   strategy names and numeric values remain readable. */
export function WeightedVotingPanel({
  draft,
  strategies,
  onWeight,
  onToggle,
}: {
  draft: DiscoveryDraft;
  strategies: Strategy[];
  onWeight: (strategyId: string, weight: number) => void;
  onToggle: (strategyId: string) => void;
}) {
  const weightsActive = draft.policy === "weighted_vote";

  return (
    <Panel
      title="Weighted Voting"
      info="Điểm tổng hợp = Σ(trọng số × tín hiệu) / Σ(trọng số). BUY = 1, HOLD = 0, SELL = -1."
    >
      <div className={styles.voteHead}>
        <span />
        <span>Indicator</span>
        <span>Trọng số</span>
      </div>

      <div className={weightsActive ? "" : styles.disabledWeights}>
        {draft.selectedStrategyIds.map((id) => {
          const label = displayLabel(id);
          const display = strategies.find((item) => item.strategy_id === id);
          return (
            <div key={id} className={styles.voteRow}>
              <input
                type="checkbox"
                checked
                aria-label={`Bỏ ${label} khỏi strategy kết hợp`}
                onChange={() => onToggle(id)}
              />
              <span className={styles.voteName}>
                <span className={styles.voteIcon}>
                  <Icon name={ROW_ICON[id] ?? "strategy"} aria-hidden="true" />
                </span>
                {label} {PARAM_SUMMARY[id] ?? ""}
                {display?.is_composite ? " (composite)" : ""}
              </span>
              <WeightSlider
                label={label}
                value={draft.weights[id] ?? 0}
                disabled={!weightsActive}
                onChange={(value) => onWeight(id, value)}
              />
            </div>
          );
        })}
      </div>

    </Panel>
  );
}
