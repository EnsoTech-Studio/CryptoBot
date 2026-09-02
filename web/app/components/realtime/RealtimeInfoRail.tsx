"use client";

import { formatPrice } from "../../../lib/format";
import { dataSourceLabel } from "../../../lib/data-mode";
import { providerLabel } from "../../../lib/market";
import { useWorkspace, type ConnectionLabel } from "../../providers/workspace";
import { StatusDot } from "../ui/Foundation";
import { Icon } from "../ui/Icon";
import styles from "./realtime.module.css";

export function RealtimeInfoRail() {
  const {
    selectedMarket,
    streamLabel,
    dataMode,
    reconnectCount,
    recentTicks,
    marketStatusState,
    panels,
    chartCount,
  } = useWorkspace();
  const visiblePanels = panels.slice(0, chartCount);
  const statusCounts = visiblePanels.reduce<Record<string, number>>((counts, panel) => {
    counts[panel.liveState] = (counts[panel.liveState] ?? 0) + 1;
    return counts;
  }, {});

  return (
    <aside className={styles.infoRail} aria-label="Hướng dẫn và trạng thái realtime">
      <section className={styles.infoCard}>
        <div className={styles.connectionTitleRow}>
          <CardTitle icon="activity" title="Trạng thái kết nối" />
          <span className={styles.connectionMain} data-state={streamLabel.toLowerCase()}>
            <StatusDot tone={statusTone(streamLabel)} />
            {connectionStateLabel(streamLabel, dataMode)}
          </span>
        </div>
        <div className={styles.statusSummary} aria-label="Tóm tắt trạng thái các biểu đồ">
          <span data-state="live"><i aria-hidden="true" />{statusCounts.live ?? 0} Live</span>
          <span data-state="stale"><i aria-hidden="true" />{statusCounts.stale ?? 0} Stale</span>
          <span data-state="unavailable"><i aria-hidden="true" />{statusCounts.unavailable ?? 0} Unavailable</span>
          {statusCounts.connecting ? <span data-state="syncing"><i aria-hidden="true" />{statusCounts.connecting} Syncing</span> : null}
          {statusCounts.paused ? <span data-state="paused"><i aria-hidden="true" />{statusCounts.paused} Paused</span> : null}
        </div>
        <dl className={styles.telemetry}>
          <div><dt>Nguồn dữ liệu</dt><dd>{dataMode === "mock" ? dataSourceLabel(dataMode) : providerLabel(selectedMarket.provider)}</dd></div>
          <div><dt>Số biểu đồ</dt><dd>{visiblePanels.length}</dd></div>
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
          <span><i className={styles.maLine} /> SMA(20) - Đường trung bình động 20</span>
          <span><i className={styles.maLine50} /> SMA(50) - Đường trung bình động 50</span>
          <span><i className={styles.volumeBar} /> Volume - Khối lượng giao dịch</span>
        </div>
      </section>
    </aside>
  );
}

function CardTitle({ icon, title }: { icon: "info" | "activity" | "chart"; title: string }) {
  return <h2 className={styles.infoTitle}><Icon name={icon} />{title}</h2>;
}

function statusTone(label: ConnectionLabel) {
  if (label === "Live" || label === "Mock") return "live" as const;
  if (label === "Syncing") return "syncing" as const;
  if (label === "Paused") return "neutral" as const;
  return "error" as const;
}

function connectionStateLabel(label: ConnectionLabel, dataMode: "live" | "mock") {
  if (dataMode === "mock") return "Mock data";
  switch (label) {
    case "Live": return "Đã kết nối";
    case "Degraded": return "Stale / gián đoạn";
    case "Unavailable": return "Không khả dụng";
    case "Syncing": return "Đang đồng bộ";
    case "Paused": return "Đã tạm dừng";
    default: return label;
  }
}

function formatUtcTime(value: string, milliseconds = false) {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "—";
  const time = date.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit", timeZone: "Asia/Ho_Chi_Minh" });
  return milliseconds ? `${time}.${String(date.getMilliseconds()).padStart(3, "0")}` : time;
}
