"use client";

import { AGGREGATE_MOCK, ANALYSIS_METRICS, EVENT_TYPES, STRATEGY_LINK } from "../../../lib/news-mock";
import { Panel, ProgressBar } from "../ui/Foundation";
import { Icon } from "../ui/Icon";
import styles from "./news.module.css";

export type SentimentDistribution = { positive: number; neutral: number; negative: number };

/* Right rail. The 24h distribution is computed from the aggregate endpoint's
   label counts whenever it loaded — percentages are never hardcoded. Event type
   mix and confidence have no contract, so they carry a planned notice.

   The aggregate remains API-backed when available; the cold screen uses the
   deterministic values that complete the reference layout. */
export function AnalysisRail({
  distribution,
  coverage,
  averageScore,
}: {
  distribution: SentimentDistribution | null;
  coverage: { items_total: number; items_analyzed: number; items_unanalyzed: number } | null;
  averageScore: number | null;
}) {
  const mix = distribution ?? AGGREGATE_MOCK;
  const coveragePct = coverage && coverage.items_total > 0
    ? Math.round((coverage.items_analyzed / coverage.items_total) * 100)
    : ANALYSIS_METRICS.sourceCoveragePct;

  return (
    <>
      <Panel
        title="Đầu ra phân tích"
        action={
          <span className={styles.headStamp}>
            <Icon name="refresh" aria-hidden="true" />
            Cập nhật: {ANALYSIS_METRICS.updatedAt}
          </span>
        }
      >
        <span className={styles.railMetric}><span>Sentiment tổng hợp (24h)</span></span>

        <div className={styles.distributionBar} role="img" aria-label={`Tích cực ${mix.positive}%, trung tính ${mix.neutral}%, tiêu cực ${mix.negative}%`}>
          <span className={styles.barPositive} style={{ width: `${mix.positive}%` }}>{mix.positive}%</span>
          <span className={styles.barNeutral} style={{ width: `${mix.neutral}%` }}>{mix.neutral}%</span>
          <span className={styles.barNegative} style={{ width: `${mix.negative}%` }}>{mix.negative}%</span>
        </div>

        <div className={styles.distributionLegend}>
          <span>
            <b><i className={styles.legendPositive} aria-hidden="true" />Positive</b>
            <em>({mix.positive}%)</em>
          </span>
          <span>
            <b><i className={styles.legendNeutral} aria-hidden="true" />Neutral</b>
            <em>({mix.neutral}%)</em>
          </span>
          <span>
            <b><i className={styles.legendNegative} aria-hidden="true" />Negative</b>
            <em>({mix.negative}%)</em>
          </span>
        </div>

        <span className={styles.railMetric}><span>Event Type (Top)</span></span>
        <div className={styles.eventChips}>
          {EVENT_TYPES.map((event) => (
            <span key={event.label} className={styles.eventChip}>
              {event.label}
              <b>{event.pct}%</b>
            </span>
          ))}
        </div>

        <div className={`${styles.railMetric} ${styles.railGood}`}>
          <span>Confidence Score (TB)</span>
          <b>{(averageScore ?? ANALYSIS_METRICS.confidenceScore).toFixed(2)}</b>
        </div>
        <div className={`${styles.railMetric} ${styles.railBrand}`}>
          <span>Số lượng tin đã phân tích (24h)</span>
          <b>{(coverage?.items_analyzed ?? ANALYSIS_METRICS.analyzedCount24h).toLocaleString("en-US")}</b>
        </div>
        <div className={`${styles.railMetric} ${styles.railGood}`}>
          <span>Độ bao phủ nguồn</span>
          <b>{coveragePct}%</b>
        </div>
        <ProgressBar value={coveragePct} label="Độ bao phủ nguồn" />
        <span className={styles.coverageFoot}>
          Nguồn hoạt động: <b>{coverage ? `${coverage.items_analyzed} / ${coverage.items_total}` : `${ANALYSIS_METRICS.activeSources} / ${ANALYSIS_METRICS.totalSources}`}</b>
        </span>
      </Panel>

      <Panel title="Tích hợp với Strategy">
        <p className={styles.integrationCaption}>News Sentiment được sử dụng trong Strategy Engine</p>

        <div className={styles.diagram}>
          <div className={styles.diagramRow}>
            <span className={styles.diagramNode}>
              <Icon name="document" aria-hidden="true" />
              <strong>{STRATEGY_LINK.left.title}</strong>
              <span>{STRATEGY_LINK.left.caption}</span>
            </span>
            <span className={styles.diagramConnector}>
              <span>{STRATEGY_LINK.connector}</span>
              <i aria-hidden="true" />
            </span>
            <span className={styles.diagramNode}>
              <Icon name="strategy" aria-hidden="true" />
              <strong>{STRATEGY_LINK.right.title}</strong>
              <span>{STRATEGY_LINK.right.caption}</span>
            </span>
          </div>

          <span className={styles.diagramAlt}>
            <span>{STRATEGY_LINK.alternate}</span>
            <i aria-hidden="true" />
          </span>

          <span className={styles.diagramLeaf}>
            <Icon name="activity" aria-hidden="true" />
            <span>
              <strong>{STRATEGY_LINK.bottom.title}</strong>
              <span>{STRATEGY_LINK.bottom.caption}</span>
            </span>
          </span>
        </div>
      </Panel>
    </>
  );
}
