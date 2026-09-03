"use client";

import { useEffect, useMemo, useState } from "react";

import { api, type NewsSource } from "../../../lib/api";
import { NEWS_MOCK } from "../../../lib/news-mock";
import { useWorkspace } from "../../providers/workspace";
import { Button, Dialog } from "../ui/Foundation";
import { AnalysisRail, type SentimentDistribution } from "./AnalysisRail";
import { NewsControls } from "./NewsControls";
import { NewsFeed } from "./NewsFeed";
import styles from "./news.module.css";

type SourceLoadState = "loading" | "ready" | "error";

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

  const [asset, setAsset] = useState<string>("BTC, ETH, SOL");
  const [refreshMinutes, setRefreshMinutes] = useState(1);
  const [sources, setSources] = useState<NewsSource[]>([]);
  const [sourcesState, setSourcesState] = useState<SourceLoadState>("loading");
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);
  const [analyzeOpen, setAnalyzeOpen] = useState(false);
  const [crawlBusy, setCrawlBusy] = useState(false);
  const [crawlError, setCrawlError] = useState<string | null>(null);

  const selectedSourceKeys = useMemo(() => {
    const ids = new Set(selectedSourceIds);
    return new Set(sources.filter((source) => ids.has(source.id)).map((source) => source.source_key));
  }, [selectedSourceIds, sources]);

  const isMock = process.env.NEXT_PUBLIC_UI_REFERENCE_MODE === "true" && news.length === 0;
  const items = isMock ? NEWS_MOCK : news;
  const visibleItems = selectedSourceKeys.size > 0
    ? items.filter((item) => selectedSourceKeys.has(item.source.key))
    : items;
  const distribution: SentimentDistribution | null = newsDistribution;

  useEffect(() => {
    let cancelled = false;

    api.newsSources()
      .then((payload) => {
        if (cancelled) return;
        setSources(payload.sources);
        setSelectedSourceIds((current) => {
          const available = new Set(payload.sources.map((source) => source.id));
          const kept = current.filter((sourceId) => available.has(sourceId));
          return kept.length > 0 ? kept : payload.sources.map((source) => source.id);
        });
        setSourcesState("ready");
      })
      .catch(() => {
        if (!cancelled) setSourcesState("error");
      });

    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => void refreshStaticData(), refreshMinutes * 60_000);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshMinutes]);

  function toggleSource(sourceId: string) {
    setSelectedSourceIds((current) => (
      current.includes(sourceId)
        ? current.filter((item) => item !== sourceId)
        : [...current, sourceId]
    ));
  }

  function toggleAllSources() {
    setSelectedSourceIds((current) => (
      current.length === sources.length ? [] : sources.map((source) => source.id)
    ));
  }

  async function crawl() {
    if (user?.role !== "ADMIN") {
      setCrawlError("Bạn cần quyền quản trị để bắt đầu một lượt crawl.");
      return;
    }

    const selectedSources = sources.filter((source) => selectedSourceIds.includes(source.id));
    if (selectedSources.length === 0) {
      setCrawlError("Hãy chọn ít nhất một nguồn tin trước khi crawl.");
      return;
    }

    setCrawlBusy(true);
    setCrawlError(null);
    try {
      const failed: string[] = [];
      for (const source of selectedSources) {
        try {
          await api.collectNews(source.id);
        } catch {
          failed.push(source.display_name);
        }
      }

      await refreshStaticData();
      if (failed.length === selectedSources.length) {
        setCrawlError("Không crawl được các nguồn đã chọn. Hãy kiểm tra API hoặc thử lại sau.");
      } else if (failed.length > 0) {
        setCrawlError(`Đã crawl xong, nhưng lỗi nguồn: ${failed.join(", ")}.`);
      }
    } finally {
      setCrawlBusy(false);
    }
  }

  return (
    <section className={styles.screen} aria-label="Không gian thu thập tin tức và phân tích sentiment">
      <div className={styles.stack}>
        <NewsControls
          asset={asset}
          refreshMinutes={refreshMinutes}
          onAsset={setAsset}
          onRefresh={setRefreshMinutes}
          sources={sources}
          selectedSourceIds={selectedSourceIds}
          sourcesState={sourcesState}
          onToggleSource={toggleSource}
          onToggleAllSources={toggleAllSources}
          onCrawl={() => void crawl()}
          crawlBusy={crawlBusy}
        />
        {crawlError ? <p className={styles.integrationCaption} role="alert">{crawlError}</p> : null}

        <div className={styles.mainRow}>
          <NewsFeed
            items={visibleItems}
            state={newsState}
            updatedAt={isMock ? "10:45:18" : new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
            isMock={isMock}
            onShowAll={() => void refreshStaticData()}
          />

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
