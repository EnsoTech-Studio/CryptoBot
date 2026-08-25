import { StatusDot, type StatusTone } from "../ui/Foundation";
import type { ConnectionLabel } from "../../providers/workspace";
import styles from "./shell.module.css";

export function SourceStatus({ state }: { state: ConnectionLabel }) {
  const tone: StatusTone = state === "Live" ? "live" : state === "Syncing" ? "syncing" : state === "Paused" ? "neutral" : "error";
  const stateLabel = state === "Live"
    ? "đang trực tuyến"
    : state === "Syncing"
      ? "đang đồng bộ"
      : state === "Paused"
        ? "đang tạm dừng"
        : state === "Unavailable"
          ? "không khả dụng"
          : "kết nối gián đoạn";

  return (
    <div className={`${styles.sourceStatus} ${styles[`source${state}`]}`} title={`Nguồn dữ liệu ${stateLabel}`}>
      <StatusDot tone={tone} />
      <span>Nguồn dữ liệu: Binance API + WebSocket</span>
    </div>
  );
}
