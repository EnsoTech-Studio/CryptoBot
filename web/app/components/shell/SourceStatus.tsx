import { StatusDot, type StatusTone } from "../ui/Foundation";
import styles from "./shell.module.css";

export function SourceStatus({ state }: { state: "Live" | "Syncing" | "Degraded" }) {
  const tone: StatusTone = state === "Live" ? "live" : state === "Syncing" ? "syncing" : "error";
  const stateLabel = state === "Live" ? "đang trực tuyến" : state === "Syncing" ? "đang đồng bộ" : "kết nối gián đoạn";

  return (
    <div className={`${styles.sourceStatus} ${styles[`source${state}`]}`} title={`Nguồn dữ liệu ${stateLabel}`}>
      <StatusDot tone={tone} />
      <span>Nguồn dữ liệu: Binance API + WebSocket</span>
    </div>
  );
}
