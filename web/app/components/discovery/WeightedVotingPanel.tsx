"use client";

import { AGGREGATE_SIGNAL_MOCK } from "../../../lib/discovery-mock";
import { displayLabel, type DiscoveryDraft } from "../../../lib/discovery";
import type { OverlayMarker, Strategy } from "../../../lib/api";
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
   ignores them (app/domain/strategy/composite/contract.py), so the rows dim
   instead of pretending the value matters. */
export function WeightedVotingPanel({
  draft,
  strategies,
  markers,
  referenceMode,
  onWeight,
  onToggle,
}: {
  draft: DiscoveryDraft;
  strategies: Strategy[];
  markers: OverlayMarker[];
  referenceMode: boolean;
  onWeight: (strategyId: string, weight: number) => void;
  onToggle: (strategyId: string) => void;
}) {
  const weightsActive = draft.policy === "weighted_vote";
  const hasLiveSignal = liveSignal(markers);
  const signal = hasLiveSignal ?? (referenceMode ? AGGREGATE_SIGNAL_MOCK : { long: 0, hold: 0, short: 0, threshold: 0.3 });

  return (
    <Panel
      title="Weighted Voting (Tín hiệu tổng hợp)"
      info="Điểm tổng hợp = Σ(trọng số × tín hiệu) / Σ(trọng số). BUY = 1, HOLD = 0, SELL = -1."
    >
      <div className={styles.voteHead}>
        <span />
        <span>Indicator</span>
        <span>Trọng số</span>
        <span>Tín hiệu</span>
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
              <SignalCell value={signalFor(id, markers, referenceMode)} />
            </div>
          );
        })}
      </div>

      <div className={styles.aggregateCard}>
        <span className={styles.aggregateTitle}>Tín hiệu tổng hợp hiện tại</span>
        <div className={styles.aggregateTiles}>
          <div className={`${styles.aggregateTile} ${styles.tileLong}`}>
            <strong>LONG</strong>
            <Icon name="arrow-up" aria-hidden="true" />
            <b>{signal.long.toFixed(2)}</b>
          </div>
          <div className={`${styles.aggregateTile} ${styles.tileHold}`}>
            <strong>HOLD</strong>
            <Icon name="minus" aria-hidden="true" />
            <b>{signal.hold.toFixed(2)}</b>
          </div>
          <div className={`${styles.aggregateTile} ${styles.tileShort}`}>
            <strong>SHORT</strong>
            <Icon name="arrow-down" aria-hidden="true" />
            <b>{signal.short.toFixed(2)}</b>
          </div>
        </div>
        <div className={styles.aggregateFoot}>
          <span>Ngưỡng vào lệnh: |score| ≥ {signal.threshold.toFixed(2)}</span>
          <em>
            {hasLiveSignal ? "Cập nhật realtime" : "Chưa có tín hiệu realtime"}
            {hasLiveSignal ? <i className={styles.liveDot} aria-hidden="true" /> : null}
          </em>
        </div>
      </div>
    </Panel>
  );
}

function SignalCell({ value }: { value: "long" | "short" | "hold" }) {
  const tone = value === "long" ? styles.signalLong : value === "short" ? styles.signalShort : "";
  return (
    <span className={`${styles.voteSignal} ${tone}`} title={value.toUpperCase()}>
      <Icon name={value === "long" ? "arrow-up" : value === "short" ? "arrow-down" : "minus"} aria-hidden="true" />
      <span className="sr-only">{value.toUpperCase()}</span>
    </span>
  );
}

/* Overlay markers are the only real per-strategy signal the API exposes
   (GET /api/v1/markets/chart-overlays). It returns an empty array today, so
   every row falls back to HOLD rather than inventing a direction. */
function signalFor(strategyId: string, markers: OverlayMarker[], referenceMode: boolean): "long" | "short" | "hold" {
  const marker = markers.find((item) => item.overlay_type.startsWith(strategyId));
  if (!marker) return referenceMode && (strategyId === "ma_cross" || strategyId === "rsi") ? "long" : "hold";
  if (marker.overlay_type.includes("buy")) return "long";
  if (marker.overlay_type.includes("sell")) return "short";
  return "hold";
}

function liveSignal(markers: OverlayMarker[]) {
  const composite = markers.find((item) => item.overlay_type.includes("composite"));
  const score = typeof composite?.evidence?.score === "number" ? composite.evidence.score : null;
  if (score === null) return null;
  return { long: Math.max(0, score), hold: score, short: Math.min(0, score), threshold: 0.3 };
}
