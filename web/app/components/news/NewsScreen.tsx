"use client";

import { useEffect, useState } from "react";

import { api } from "../../../lib/api";
import { NEWS_MOCK, type SourceMode } from "../../../lib/news-mock";
import { useWorkspace } from "../../providers/workspace";
import { Button, Dialog } from "../ui/Foundation";
import { AnalysisRail, type SentimentDistribution } from "./AnalysisRail";
import { ExtractionWorkspace, SelfHealingPanel } from "./ExtractionWorkspace";
import { NewsControls } from "./NewsControls";
import { NewsFeed } from "./NewsFeed";
import styles from "./news.module.css";

export function NewsScreen() {
  const {
    news,
    newsState,
    coverage,
    newsDistribution,
    newsAverageScore,
    refreshStaticData,
    prediction,
    predictionText,
    setPredictionText,
    testSentiment,
    user,
  } = useWorkspace();

  const [mode, setMode] = useState<SourceMode>("website");
  const [asset, setAsset] = useState<string>("BTC, ETH, SOL");
  const [refreshMinutes, setRefreshMinutes] = useState(1);
  const [selfHealing, setSelfHealing] = useState(true);
  const [analyzeOpen, setAnalyzeOpen] = useState(false);
  const [crawlBusy, setCrawlBusy] = useState(false);
  const [crawlError, setCrawlError] = useState<string | null>(null);

  async function crawl() {
    if (user?.role !== "ADMIN") {
      setCrawlError("Bạn cần quyền quản trị để bắt đầu một lượt crawl.");
      return;
    }
    setCrawlBusy(true);
    setCrawlError(null);
    try {
      await api.collectNews();
      await refreshStaticData();
    } catch {
      setCrawlError("Không thể bắt đầu crawl. Hãy thử lại sau.");
    } finally {
      setCrawlBusy(false);
    }
  }

  const isMock = process.env.NEXT_PUBLIC_UI_REFERENCE_MODE === "true" && news.length === 0;
  const items = isMock ? NEWS_MOCK : news;
  const distribution: SentimentDistribution | null = newsDistribution;

  /* Auto refresh honours the selected interval. The reference offers 1-5
     minutes; the timer is cleared on unmount so navigating away stops it. */
  useEffect(() => {
    const timer = window.setInterval(() => void refreshStaticData(), refreshMinutes * 60_000);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshMinutes]);

  return (
    <section className={styles.screen} aria-label="Không gian thu thập tin tức và phân tích sentiment">
      <div className={styles.stack}>
        <NewsControls
          mode={mode}
          asset={asset}
          refreshMinutes={refreshMinutes}
          onMode={setMode}
          onAsset={setAsset}
          onRefresh={setRefreshMinutes}
          onCrawl={() => void crawl()}
          crawlBusy={crawlBusy}
        />
        {crawlError ? <p className={styles.integrationCaption} role="alert">{crawlError}</p> : null}

        <div className={styles.mainRow}>
          <NewsFeed
            items={items}
            state={newsState}
            updatedAt={isMock ? "10:45:18" : new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
            isMock={isMock}
            onShowAll={() => void refreshStaticData()}
          />

          <div className={styles.centreColumn}>
            <ExtractionWorkspace />
            <SelfHealingPanel enabled={selfHealing} onToggle={setSelfHealing} />
          </div>

          <div className={styles.railColumn}>
            <AnalysisRail
            distribution={distribution}
            coverage={coverage}
            averageScore={newsAverageScore}
            referenceMode={isMock}
          />
          </div>
        </div>

        <div className={styles.manualAction}>
          <Button variant="secondary" onClick={() => setAnalyzeOpen(true)}>
            Phân tích một đoạn văn bản
          </Button>
        </div>
      </div>

      {/* Manual sentiment analysis is real (POST /api/v1/ai/predict). Plan 05
          requires keeping it, so it lives in a dialog instead of being dropped. */}
      <Dialog open={analyzeOpen} title="Phân tích sentiment thủ công" onClose={() => setAnalyzeOpen(false)}>
        <label className={styles.integrationCaption} htmlFor="sentiment-copy">
          Nhập một đoạn tin hoặc ghi chú thị trường
        </label>
        <textarea
          id="sentiment-copy"
          rows={5}
          value={predictionText}
          onChange={(event) => setPredictionText(event.target.value)}
          style={{ width: "100%", marginTop: 8 }}
        />
        <div className={styles.stripActions} style={{ marginTop: 12 }}>
          <Button variant="primary" disabled={!user} onClick={() => void testSentiment()}>
            Phân tích
          </Button>
          {prediction ? (
            <span className={`${styles.sentimentTag} ${prediction.label === "POSITIVE" ? styles.tagPositive : prediction.label === "NEGATIVE" ? styles.tagNegative : styles.tagNeutral}`}>
              {prediction.label} · {Math.round(prediction.score * 100)}%
            </span>
          ) : (
            <span className={styles.integrationCaption}>
              {user ? "Sẵn sàng phân tích." : "Đăng nhập để dùng dịch vụ AI."}
            </span>
          )}
        </div>
      </Dialog>
    </section>
  );
}
