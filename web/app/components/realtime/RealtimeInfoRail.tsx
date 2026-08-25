"use client";

import { formatPrice } from "../../../lib/format";
import { useWorkspace, type ConnectionLabel } from "../../providers/workspace";
import { StatusDot } from "../ui/Foundation";
import { Icon } from "../ui/Icon";
import styles from "./realtime.module.css";

export function RealtimeInfoRail() {
  const {
    selectedMarket,
    streamLabel,
    latencyMs,
    lastFrameAt,
    reconnectCount,
    recentMarketEvents,
    marketStatusState,
  } = useWorkspace();

  return (
    <aside className={styles.infoRail} aria-label="Hướng dẫn và trạng thái realtime">
      <section className={styles.infoCard}>
        <CardTitle icon="info" title="Candle Update Logic" />
        <div className={styles.guideList}>
          <GuideRow variant="forming" title="Nến đang hình thành" text="Giá OHLC và volume được cập nhật từ kline chưa đóng." />
          <GuideRow variant="closed" title="Nến đã đóng" text="Kline final chốt close time và trở thành dữ liệu lịch sử." />
          <GuideRow variant="next" title="Mở nến tiếp theo" text="Open time mới được thêm đúng thứ tự; trùng thời gian sẽ được thay thế." />
        </div>
      </section>

      <section className={styles.infoCard}>
        <CardTitle icon="activity" title="Connection Status" />
        <div className={styles.connectionSummary}>
          <span className={styles.connectionMain} data-state={streamLabel.toLowerCase()}>
            <StatusDot tone={statusTone(streamLabel)} /> {streamLabel}
          </span>
          <span>{selectedMarket.provider}</span>
        </div>
        <dl className={styles.telemetry}>
          <div><dt>Market</dt><dd>{selectedMarket.symbol}</dd></div>
          <div><dt>Latency</dt><dd>{latencyMs == null ? "—" : `${latencyMs} ms`}</dd></div>
          <div><dt>Last update</dt><dd>{lastFrameAt ? formatUtcTime(lastFrameAt) : "—"}</dd></div>
          <div><dt>Reconnects</dt><dd>{reconnectCount}</dd></div>
          <div><dt>Status API</dt><dd>{marketStatusState === "ready" ? "Synced" : marketStatusState === "loading" ? "Checking" : "Unavailable"}</dd></div>
        </dl>
      </section>

      <section className={styles.infoCard}>
        <CardTitle icon="activity" title="Recent BBO" />
        {recentMarketEvents.length > 0 ? (
          <div className={styles.bboTableWrap}>
            <table className={styles.bboTable}>
              <thead><tr><th>Time</th><th>Bid</th><th>Ask</th><th>Spread</th></tr></thead>
              <tbody>
                {recentMarketEvents.slice(0, 5).map((event) => (
                  <tr key={event.id}>
                    <td>{formatUtcTime(event.occurredAt)}</td>
                    <td className={styles.bid}>{formatPrice(event.bid)}</td>
                    <td className={styles.ask}>{formatPrice(event.ask)}</td>
                    <td>{formatSpread(event.ask - event.bid)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className={styles.emptyInfo}>Chưa nhận được best bid/offer từ stream hiện tại.</p>
        )}
      </section>

      <section className={styles.infoCard}>
        <CardTitle icon="chart" title="Chart Legend" />
        <div className={styles.legend}>
          <span><i className={styles.candleUp} /> Nến tăng</span>
          <span><i className={styles.candleDown} /> Nến giảm</span>
          <span><i className={styles.maLine} /> Overlay</span>
          <span><i className={styles.volumeBar} /> Volume</span>
          <span><i className={styles.buyMark} /> Buy signal</span>
          <span><i className={styles.sellMark} /> Sell signal</span>
        </div>
      </section>
    </aside>
  );
}

function CardTitle({ icon, title }: { icon: "info" | "activity" | "chart"; title: string }) {
  return <h2 className={styles.infoTitle}><Icon name={icon} />{title}</h2>;
}

function GuideRow({ variant, title, text }: { variant: "forming" | "closed" | "next"; title: string; text: string }) {
  return (
    <div className={styles.guideRow}>
      <span className={`${styles.miniCandle} ${styles[variant]}`} aria-hidden="true"><i /></span>
      <div><strong>{title}</strong><p>{text}</p></div>
    </div>
  );
}

function statusTone(label: ConnectionLabel) {
  if (label === "Live") return "live" as const;
  if (label === "Syncing") return "syncing" as const;
  if (label === "Paused") return "neutral" as const;
  return "error" as const;
}

function formatUtcTime(value: string) {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "—";
  return date.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit", timeZone: "UTC" });
}

function formatSpread(value: number) {
  if (!Number.isFinite(value)) return "—";
  return value < 0.01 ? value.toFixed(4) : value.toFixed(2);
}
