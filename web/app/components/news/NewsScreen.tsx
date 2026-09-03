"use client";

import { useEffect, useMemo, useState } from "react";

import { api, type NewsItem, type NewsSource } from "../../../lib/api";
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
  const [analysisBusy, setAnalysisBusy] = useState(false);
  const [analysisStatus, setAnalysisStatus] = useState<{ tone: "status" | "alert"; text: string } | null>(null);

  const selectedSourceKeys = useMemo(() => {
    const ids = new Set(selectedSourceIds);
    return new Set(sources.filter((source) => ids.has(source.id)).map((source) => source.source_key));
  }, [selectedSourceIds, sources]);

  const selectedCoins = useMemo(() => coinsFromAsset(asset), [asset]);
  const selectedCoinSet = useMemo(() => new Set(selectedCoins), [selectedCoins]);
  const isMock = process.env.NEXT_PUBLIC_UI_REFERENCE_MODE === "true" && news.length === 0;
  const items = isMock ? NEWS_MOCK : news;
  const visibleItems = useMemo(() => items.filter((item) => {
    const sourceMatches = selectedSourceKeys.size === 0 || selectedSourceKeys.has(item.source.key);
    const itemCoins = item.related_coins?.map((coin) => coin.toUpperCase()) ?? [];
    const coinMatches = selectedCoinSet.size === 0 || itemCoins.some((coin) => selectedCoinSet.has(coin));
    return sourceMatches && coinMatches;
  }), [items, selectedCoinSet, selectedSourceKeys]);
  const selectedAnalysis = useMemo(() => summarizeSelectedNews(visibleItems), [visibleItems]);

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

  async function analyzeSelectedNews() {
    if (user?.role !== "ADMIN") {
      setAnalysisStatus({ tone: "alert", text: "Bạn cần quyền quản trị để phân tích tin tức." });
      return;
    }

    const selectedSources = sources.filter((source) => selectedSourceIds.includes(source.id));
    if (selectedSources.length === 0) {
      setAnalysisStatus({ tone: "alert", text: "Hãy chọn ít nhất một nguồn tin trước khi phân tích." });
      return;
    }

    setAnalysisBusy(true);
    setAnalysisStatus(null);
    try {
      const failed: string[] = [];
      for (const source of selectedSources) {
        try {
          await api.collectNews(source.id);
        } catch {
          failed.push(source.display_name);
        }
      }

      const backfill = await api.backfillSentiment({
        sourceIds: selectedSources.map((source) => source.id),
        coins: selectedCoins,
        limit: 200,
      });
      await refreshStaticData();

      if (failed.length === selectedSources.length) {
        setAnalysisStatus({
          tone: "alert",
          text: `Không crawl được nguồn mới, nhưng đã phân tích ${backfill.analyzed}/${backfill.attempted} tin đang có trong lựa chọn.`,
        });
      } else if (failed.length > 0) {
        setAnalysisStatus({
          tone: "alert",
          text: `Đã phân tích ${backfill.analyzed}/${backfill.attempted} tin; lỗi nguồn: ${failed.join(", ")}.`,
        });
      } else {
        setAnalysisStatus({
          tone: "status",
          text: `Đã phân tích ${backfill.analyzed}/${backfill.attempted} tin thuộc nguồn và asset đang chọn.`,
        });
      }
    } catch {
      setAnalysisStatus({
        tone: "alert",
        text: "Không phân tích được các tin đã chọn. Hãy kiểm tra AI service, OpenAI key hoặc LangSmith/OpenAI network rồi thử lại.",
      });
    } finally {
      setAnalysisBusy(false);
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
          onAnalyze={() => void analyzeSelectedNews()}
          analyzeBusy={analysisBusy}
        />
        {analysisStatus ? (
          <p className={styles.integrationCaption} role={analysisStatus.tone}>
            {analysisStatus.text}
          </p>
        ) : null}

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
              distribution={selectedAnalysis.distribution}
              coverage={selectedAnalysis.coverage}
              averageScore={selectedAnalysis.averageScore}
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

function coinsFromAsset(asset: string): string[] {
  return asset
    .split(",")
    .map((coin) => coin.trim().toUpperCase())
    .filter(Boolean);
}

function summarizeSelectedNews(items: NewsItem[]): {
  distribution: SentimentDistribution | null;
  coverage: { items_total: number; items_analyzed: number; items_unanalyzed: number };
  averageScore: number | null;
} {
  const counts = { POSITIVE: 0, NEUTRAL: 0, NEGATIVE: 0 };
  let scoreTotal = 0;

  for (const item of items) {
    if (!item.sentiment) continue;
    counts[item.sentiment.label] += 1;
    scoreTotal += item.sentiment.score;
  }

  const analyzed = counts.POSITIVE + counts.NEUTRAL + counts.NEGATIVE;
  const positive = analyzed > 0 ? Math.round((counts.POSITIVE / analyzed) * 100) : 0;
  const neutral = analyzed > 0 ? Math.round((counts.NEUTRAL / analyzed) * 100) : 0;

  return {
    distribution: analyzed > 0
      ? { positive, neutral, negative: 100 - positive - neutral }
      : null,
    coverage: {
      items_total: items.length,
      items_analyzed: analyzed,
      items_unanalyzed: items.length - analyzed,
    },
    averageScore: analyzed > 0 ? scoreTotal / analyzed : null,
  };
}
