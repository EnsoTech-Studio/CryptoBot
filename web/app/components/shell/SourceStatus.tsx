import { StatusDot, type StatusTone } from "../ui/Foundation";
import { dataSourceLabel } from "../../../lib/data-mode";
import type { ConnectionLabel, DataMode } from "../../providers/workspace";
import styles from "./shell.module.css";

export function SourceStatus({ state, dataMode }: { state: ConnectionLabel; dataMode: DataMode }) {
  const tone: StatusTone = state === "Live" || state === "Mock" ? "live" : state === "Syncing" ? "syncing" : state === "Paused" ? "neutral" : "error";
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
    <div className={`${styles.sourceStatus} ${styles[`source${state}`]}`} title={dataMode === "mock" ? "Dữ liệu mô phỏng xác định; không phải giá thị trường thật" : `Nguồn dữ liệu ${stateLabel}`}>
      <StatusDot tone={tone} />
      <span>{dataSourceLabel(dataMode)}</span>
    </div>
  );
}
