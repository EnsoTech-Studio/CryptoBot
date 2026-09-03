"use client";

import { useState } from "react";

import { api, type NewsStrategyAnalysisModel } from "../../../lib/api";
import {
  AGGREGATE_MOCK,
  ANALYSIS_METRICS,
  EVENT_TYPES,
} from "../../../lib/news-mock";
import {
  NEWS_SENTIMENT_STRATEGY,
  newsStrategyEnginePrompt,
} from "../../../lib/news-strategy-export";
import { Button, Field, Panel, ProgressBar, Select } from "../ui/Foundation";
import { Icon } from "../ui/Icon";
import styles from "./news.module.css";

export type SentimentDistribution = {
  positive: number;
  neutral: number;
  negative: number;
};
type Coverage = {
  items_total: number;
  items_analyzed: number;
  items_unanalyzed: number;
};
type StrategyAnalysis = {
  trace: string;
  result: string;
  model: string;
};

const STRATEGY_MODELS: NewsStrategyAnalysisModel[] = [
  "gpt-4o-mini",
  "gpt-4o",
  "gpt-4.1-mini",
  "gpt-5-mini",
];

export function AnalysisRail({
  distribution,
  coverage,
  averageScore,
  referenceMode,
}: {
  distribution: SentimentDistribution | null;
  coverage: Coverage | null;
  averageScore: number | null;
  referenceMode: boolean;
}) {
  const [exportStatus, setExportStatus] = useState("");
  const [strategyBusy, setStrategyBusy] = useState(false);
  const [strategyModel, setStrategyModel] =
    useState<NewsStrategyAnalysisModel>("gpt-4o-mini");
  const [strategyAnalysis, setStrategyAnalysis] = useState<StrategyAnalysis>(
    () => ({
      trace: "",
      result: "",
      model: "",
    }),
  );
  const mix =
    distribution ??
    (referenceMode ? AGGREGATE_MOCK : { positive: 0, neutral: 0, negative: 0 });
  const coveragePct =
    coverage && coverage.items_total > 0
      ? Math.round((coverage.items_analyzed / coverage.items_total) * 100)
      : referenceMode
        ? ANALYSIS_METRICS.sourceCoveragePct
        : 0;
  const canAnalyzeStrategy =
    !referenceMode &&
    Boolean(distribution) &&
    Boolean(coverage) &&
    (coverage?.items_analyzed ?? 0) > 0 &&
    !strategyBusy;

  const analyzeStrategy = async () => {
    if (
      !distribution ||
      !coverage ||
      coverage.items_analyzed === 0 ||
      referenceMode
    ) {
      setExportStatus(
        "Chưa có sentiment thật từ tin đã chọn để phân tích strategy.",
      );
      return;
    }
    setStrategyBusy(true);
    setExportStatus("");
    try {
      const result = await api.analyzeNewsStrategy({
        sentimentMix: distribution,
        coverage,
        averageScore,
        model: strategyModel,
      });
      setStrategyAnalysis({
        trace: result.reasoning,
        result: result.result,
        model: `${result.model} · ${result.model_version}`,
      });
      setExportStatus(
        "Đã phân tích strategy bằng AI trên dữ liệu sentiment đã chọn.",
      );
    } catch {
      setExportStatus(
        "Không phân tích được strategy. Kiểm tra đăng nhập, AI service hoặc OpenAI key rồi thử lại.",
      );
    } finally {
      setStrategyBusy(false);
    }
  };

  const copyStrategy = async () => {
    try {
      await navigator.clipboard.writeText(
        strategyAnalysis.result || newsStrategyEnginePrompt(),
      );
      setExportStatus(
        strategyAnalysis.result
          ? "Đã sao chép kết quả phân tích."
          : "Đã sao chép prompt cho Strategy Engine.",
      );
    } catch {
      setExportStatus("Không thể sao chép. Hãy dùng nút lưu strategy.");
    }
  };

  const downloadStrategy = () => {
    const payload =
      strategyAnalysis.result ||
      JSON.stringify(NEWS_SENTIMENT_STRATEGY, null, 2);
    const file = new Blob([payload], { type: "application/json" });
    const url = URL.createObjectURL(file);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = strategyAnalysis.result
      ? "news-strategy-analysis.json"
      : "news-sentiment.strategy.json";
    anchor.click();
    URL.revokeObjectURL(url);
    setExportStatus(
      strategyAnalysis.result
        ? "Đã tải news-strategy-analysis.json."
        : "Đã tải news-sentiment.strategy.json.",
    );
  };

  return (
    <>
      <Panel
        title="Đầu ra phân tích"
        action={
          <span className={styles.headStamp}>
            <Icon name="refresh" aria-hidden="true" />
            Cập nhật: {referenceMode ? ANALYSIS_METRICS.updatedAt : "-"}
          </span>
        }
      >
        <span className={styles.railMetric}>
          <span>Sentiment tổng hợp (24h)</span>
        </span>

        <div
          className={styles.distributionBar}
          role="img"
          aria-label={`Tích cực ${mix.positive}%, trung tính ${mix.neutral}%, tiêu cực ${mix.negative}%`}
        >
          <span
            className={styles.barPositive}
            style={{ width: `${mix.positive}%` }}
          >
            {mix.positive}%
          </span>
          <span
            className={styles.barNeutral}
            style={{ width: `${mix.neutral}%` }}
          >
            {mix.neutral}%
          </span>
          <span
            className={styles.barNegative}
            style={{ width: `${mix.negative}%` }}
          >
            {mix.negative}%
          </span>
        </div>

        <div className={styles.distributionLegend}>
          <span>
            <b>
              <i className={styles.legendPositive} aria-hidden="true" />
              Positive
            </b>
            <em>({mix.positive}%)</em>
          </span>
          <span>
            <b>
              <i className={styles.legendNeutral} aria-hidden="true" />
              Neutral
            </b>
            <em>({mix.neutral}%)</em>
          </span>
          <span>
            <b>
              <i className={styles.legendNegative} aria-hidden="true" />
              Negative
            </b>
            <em>({mix.negative}%)</em>
          </span>
        </div>

        <span className={styles.railMetric}>
          <span>Event Type (Top)</span>
        </span>
        <div className={styles.eventChips}>
          {(referenceMode ? EVENT_TYPES : []).map((event) => (
            <span key={event.label} className={styles.eventChip}>
              {event.label}
              <b>{event.pct}%</b>
            </span>
          ))}
          {!referenceMode ? (
            <span className={styles.integrationCaption}>
              Chưa có dữ liệu phân loại sự kiện.
            </span>
          ) : null}
        </div>

        <div className={`${styles.railMetric} ${styles.railGood}`}>
          <span>Confidence Score (TB)</span>
          <b>
            {averageScore === null && !referenceMode
              ? "-"
              : (averageScore ?? ANALYSIS_METRICS.confidenceScore).toFixed(2)}
          </b>
        </div>
        <div className={`${styles.railMetric} ${styles.railBrand}`}>
          <span>Số lượng tin đã phân tích (24h)</span>
          <b>
            {(
              coverage?.items_analyzed ??
              (referenceMode ? ANALYSIS_METRICS.analyzedCount24h : 0)
            ).toLocaleString("en-US")}
          </b>
        </div>
        <div className={`${styles.railMetric} ${styles.railGood}`}>
          <span>Độ bao phủ nguồn</span>
          <b>{coveragePct}%</b>
        </div>
        <ProgressBar value={coveragePct} label="Độ bao phủ nguồn" />
        <span className={styles.coverageFoot}>
          Tin đã phân tích:{" "}
          <b>
            {coverage
              ? `${coverage.items_analyzed} / ${coverage.items_total}`
              : referenceMode
                ? `${ANALYSIS_METRICS.activeSources} / ${ANALYSIS_METRICS.totalSources}`
                : "-"}
          </b>
        </span>
      </Panel>

      <Panel title="Tích hợp với Strategy">
        <div className={styles.strategyAnalyzer}>
          <p className={styles.integrationCaption}>
            Phân tích strategy dùng trực tiếp sentiment của các tin đang được
            chọn.
          </p>

          <div className={styles.strategyControls}>
            <Field label="Model">
              <Select
                value={strategyModel}
                onChange={(event) =>
                  setStrategyModel(
                    event.target.value as NewsStrategyAnalysisModel,
                  )
                }
              >
                {STRATEGY_MODELS.map((model) => (
                  <option key={model} value={model}>
                    {model}
                  </option>
                ))}
              </Select>
            </Field>
            <Button
              type="button"
              variant="primary"
              onClick={() => void analyzeStrategy()}
              disabled={!canAnalyzeStrategy}
            >
              <Icon name="wand" aria-hidden="true" />
              {strategyBusy ? "Đang phân tích..." : "Phân tích"}
            </Button>
          </div>

          <label className={styles.strategyTextBlock}>
            <span>Quy trình suy luận AI</span>
            <textarea
              readOnly
              rows={6}
              className={styles.strategyTextarea}
              value={strategyAnalysis.trace}
              placeholder="AI sẽ hiển thị reasoning tóm tắt sau khi phân tích sentiment thật."
            />
          </label>

          <label className={styles.strategyTextBlock}>
            <span>Kết quả phân tích</span>
            <textarea
              readOnly
              rows={8}
              className={styles.strategyTextarea}
              value={strategyAnalysis.result}
              placeholder="Kết quả JSON để copy hoặc lưu về máy sẽ xuất hiện ở đây."
            />
          </label>

          <div className={styles.stripActions}>
            <Button type="button" onClick={copyStrategy}>
              <Icon name="copy" aria-hidden="true" />
              Sao chép
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={downloadStrategy}
            >
              <Icon name="download" aria-hidden="true" />
              Lưu kết quả
            </Button>
          </div>
          {strategyAnalysis.model ? (
            <p className={styles.integrationCaption}>
              {/* Model trả về: {strategyAnalysis.model} */}
            </p>
          ) : null}
          {exportStatus ? (
            <p className={styles.integrationCaption} role="status">
              {exportStatus}
            </p>
          ) : null}
        </div>
      </Panel>
    </>
  );
}
