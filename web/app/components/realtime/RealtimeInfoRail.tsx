"use client";

import { formatPrice } from "../../../lib/format";
import { dataSourceLabel } from "../../../lib/data-mode";
import { useWorkspace, type ConnectionLabel } from "../../providers/workspace";
import { StatusDot } from "../ui/Foundation";
import { Icon } from "../ui/Icon";
import styles from "./realtime.module.css";

export function RealtimeInfoRail() {
  const {
    selectedMarket,
    streamLabel,
    dataMode,
    latencyMs,
    lastFrameAt,
    reconnectCount,
    recentTicks,
    marketStatusState,
  } = useWorkspace();

  return (
    <aside className={styles.infoRail} aria-label="Hướng dẫn và trạng thái realtime">
      <section className={styles.infoCard}>
        <CardTitle icon="info" title="Logic cập nhật candle" />
        <div className={styles.guideList}>
          <GuideRow variant="update" title="Trùng nến cuối" action="Update candle" text="Cùng open time: cập nhật OHLC và volume của nến hiện tại." />
          <GuideRow variant="append" title="Nến mới hoàn toàn" action="Append candle" text="Open time mới: thêm nến tiếp theo vào cuối chuỗi." />
        </div>
      </section>

      <section className={styles.infoCard}>
        <div className={styles.connectionTitleRow}>
          <CardTitle icon="activity" title="Trạng thái kết nối" />
          <span className={styles.connectionMain} data-state={streamLabel.toLowerCase()}>
            <StatusDot tone={statusTone(streamLabel)} />
            {dataMode === "mock" ? "Đã kết nối" : streamLabel === "Live" ? "Đã kết nối" : streamLabel}
          </span>
        </div>
        <dl className={styles.telemetry}>
          <div><dt>Nguồn dữ liệu</dt><dd>{dataMode === "mock" ? dataSourceLabel(dataMode) : selectedMarket.provider}</dd></div>
          <div><dt>Độ trễ (Latency)</dt><dd>{latencyMs == null ? "—" : `${latencyMs} ms`}</dd></div>
          <div><dt>Dữ liệu cuối</dt><dd>{lastFrameAt ? formatUtcTime(lastFrameAt) : "—"}</dd></div>
          <div><dt>Kết nối</dt><dd>{marketStatusState === "loading" ? "Đang kiểm tra" : reconnectCount === 0 ? "Ổn định" : `${reconnectCount} lần kết nối lại`}</dd></div>
        </dl>
      </section>

      <section className={styles.infoCard}>
        <CardTitle icon="activity" title={`Recent Ticks (${selectedMarket.symbol})`} />
        {recentTicks.length > 0 ? (
          <div className={styles.bboTableWrap}>
            <table className={styles.bboTable}>
              <thead><tr><th>Thời gian</th><th>Giá</th><th>Khối lượng</th><th>Loại</th></tr></thead>
              <tbody>
                {recentTicks.slice(0, 5).map((tick) => (
                  <tr key={tick.id}>
                    <td>{formatUtcTime(tick.occurredAt, true)}</td>
                    <td className={tick.side === "sell" ? styles.ask : styles.bid}>{formatPrice(tick.price)}</td>
                    <td>{tick.quantity.toFixed(3)}</td>
                    <td className={tick.side === "sell" ? styles.ask : tick.side === "buy" ? styles.bid : ""}>
                      {tick.side === "buy" ? "Mua" : tick.side === "sell" ? "Bán" : "BBO"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className={styles.emptyInfo}>Đang chờ tick hoặc best bid/offer từ stream.</p>
        )}
      </section>

      <section className={styles.infoCard}>
        <CardTitle icon="chart" title="Chú thích" />
        <div className={styles.legend}>
          <span><i className={styles.candleUp} /> Nến tăng (Close &gt; Open)</span>
          <span><b className={`${styles.signalBadge} ${styles.buy}`}>BUY</b> Tín hiệu Mua</span>
          <span><i className={styles.candleDown} /> Nến giảm (Close &lt; Open)</span>
          <span><b className={`${styles.signalBadge} ${styles.sell}`}>SELL</b> Tín hiệu Bán</span>
          <span><i className={styles.maLine} /> MA(20) - Đường trung bình động 20</span>
          <span><i className={styles.volumeBar} /> Volume - Khối lượng giao dịch</span>
        </div>
      </section>
    </aside>
  );
}

function CardTitle({ icon, title }: { icon: "info" | "activity" | "chart"; title: string }) {
  return <h2 className={styles.infoTitle}><Icon name={icon} />{title}</h2>;
}

function GuideRow({ variant, title, action, text }: { variant: "update" | "append"; title: string; action: string; text: string }) {
  return (
    <div className={styles.guideRow}>
      <div className={styles.guideCopy}>
        <strong>{title} <span>→ {action}</span></strong>
        <div className={styles.candleFlow} data-variant={variant} aria-hidden="true">
          <span className={styles.candleGroup}><i /><i /><i /><i /></span>
          <b />
          <span className={styles.candleGroup}><i /><i /><i /><i /></span>
        </div>
        <p>{text}</p>
      </div>
    </div>
  );
}

function statusTone(label: ConnectionLabel) {
  if (label === "Live" || label === "Mock") return "live" as const;
  if (label === "Syncing") return "syncing" as const;
  if (label === "Paused") return "neutral" as const;
  return "error" as const;
}

function formatUtcTime(value: string, milliseconds = false) {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "—";
  const time = date.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit", timeZone: "UTC" });
  return milliseconds ? `${time}.${String(date.getUTCMilliseconds()).padStart(3, "0")}` : time;
}
