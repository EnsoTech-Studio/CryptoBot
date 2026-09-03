"use client";

import type { NewsItem } from "../../../lib/api";
import { NEWS_SUMMARY_MOCK, assetTone } from "../../../lib/news-mock";
import type { LoadState } from "../../providers/workspace";
import { Skeleton, Unavailable } from "../States";
import { Panel } from "../ui/Foundation";
import { Icon } from "../ui/Icon";
import styles from "./news.module.css";

const MAX_VISIBLE_NEWS = 12;

export function NewsFeed({
  items,
  state,
  updatedAt,
  isMock,
  onShowAll,
}: {
  items: NewsItem[];
  state: LoadState;
  updatedAt: string;
  isMock: boolean;
  onShowAll: () => void;
}) {
  const visibleItems = items.slice(0, MAX_VISIBLE_NEWS);

  return (
    <Panel
      title="Tin tức đầu vào"
      action={
        <span className={styles.headStamp}>
          <Icon name="refresh" aria-hidden="true" />
          Cập nhật: {updatedAt}
        </span>
      }
    >
      {state === "loading" && items.length === 0 ? (
        <Skeleton lines={8} />
      ) : state === "unavailable" && items.length === 0 ? (
        <Unavailable title="Không tải được tin tức">
          Bộ thu thập không phản hồi. Biểu đồ và backtest không bị ảnh hưởng.
        </Unavailable>
      ) : items.length === 0 ? (
        <Unavailable title="Chưa có tin tức phù hợp">
          Chưa có dữ liệu đã thu thập. Hãy bấm Phân tích từ tài khoản quản trị hoặc thử lại sau.
        </Unavailable>
      ) : (
        <>
          <div className={styles.feedHead}>
            <span>Asset</span>
            <span>Tiêu đề</span>
            <span>Nguồn</span>
            <span>Thời gian</span>
          </div>

          <div className={styles.feedList}>
            {visibleItems.map((item) => (
              <FeedRow key={item.id} item={item} isMock={isMock} />
            ))}
          </div>

          <div className={styles.feedFooter}>
            <span className={styles.feedCount}>{visibleItems.length} / {items.length} tin</span>
            <button type="button" className={styles.feedMore} onClick={onShowAll}>
              Làm mới tin tức
              <Icon name="chevron-right" aria-hidden="true" />
            </button>
          </div>
        </>
      )}
    </Panel>
  );
}

function FeedRow({ item, isMock }: { item: NewsItem; isMock: boolean }) {
  const coin = item.related_coins?.[0] ?? "";
  const tone = assetTone(coin);
  const summary = isMock ? NEWS_SUMMARY_MOCK[item.id] : undefined;

  return (
    <article className={styles.feedRow}>
      <span className={`${styles.assetIcon} ${styles[`asset${tone[0].toUpperCase()}${tone.slice(1)}`]}`} aria-hidden="true">
        <Icon name={coinIcon(coin)} />
      </span>
      <div className={styles.feedBody}>
        <h3 className={styles.feedTitle}>
          <a href={item.url} target="_blank" rel="noreferrer">{item.title}</a>
        </h3>
        {summary ? <p className={styles.feedSummary}>{summary}</p> : null}
        <span className={`${styles.sentimentTag} ${sentimentClass(item.sentiment?.label)}`}>
          {item.sentiment ? item.sentiment.label : "CHƯA PHÂN TÍCH"}
        </span>
      </div>
      <span className={styles.feedMeta}>
        <span className={styles.feedSource}>{item.source.display_name}</span>
        <span className={styles.feedTime}>{timeOf(item.published_at)}</span>
      </span>
    </article>
  );
}

function coinIcon(coin: string) {
  switch (coin.toUpperCase()) {
    case "BTC":
      return "bitcoin" as const;
    case "ETH":
      return "ethereum" as const;
    case "SOL":
      return "solana" as const;
    default:
      return "coins" as const;
  }
}

function sentimentClass(label?: string) {
  switch (label) {
    case "POSITIVE":
      return styles.tagPositive;
    case "NEGATIVE":
      return styles.tagNegative;
    case "NEUTRAL":
      return styles.tagNeutral;
    default:
      return styles.tagPending;
  }
}

function timeOf(value: string) {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "-";
  return date.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "UTC" });
}
