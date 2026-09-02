"use client";

import { recentImportRows, type ImportRow, type RecentImportDraft } from "../../../lib/strategy-authoring";
import { Panel } from "../ui/Foundation";
import { Icon } from "../ui/Icon";
import styles from "./strategy.module.css";

export function RecentImports({
  drafts,
  referenceMode,
  onRun,
}: {
  drafts: RecentImportDraft[];
  referenceMode: boolean;
  onRun: (strategyId: string) => void;
}) {
  const rows = recentImportRows(drafts, referenceMode);
  return (
    <Panel
      title="Chiến lược đã import gần đây"
      className={styles.importsPanel}
      action={
        <button type="button" className={styles.allLink}>
          Xem tất cả
          <Icon name="chevron-right" aria-hidden="true" />
        </button>
      }
    >
      <div className={styles.importsWrap}>
        <table className={styles.importsTable}>
          <thead>
            <tr>
              <th scope="col">Tên strategy</th>
              <th scope="col">Source</th>
              <th scope="col">Ngày tạo</th>
              <th scope="col">Version</th>
              <th scope="col">Tags</th>
              <th scope="col">Trạng thái</th>
              <th scope="col">Hành động</th>
            </tr>
          </thead>
          <tbody>
            {rows.length > 0 ? rows.map((row) => (
              <ImportTableRow key={`${row.draftId ?? row.strategyId ?? row.name}-${row.version}`} row={row} onRun={onRun} />
            )) : (
              <tr><td className={styles.emptyImports} colSpan={7}>Chưa có strategy nào được import.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function ImportTableRow({ row, onRun }: { row: ImportRow; onRun: (strategyId: string) => void }) {
  const canRun = row.status === "approved" && row.strategyId !== null;
  const statusLabel = row.status === "approved" ? "Hợp lệ" : row.status === "review" ? "Chờ duyệt" : row.status === "rejected" ? "Từ chối" : "Lỗi";
  return (
    <tr>
      <td className={styles.strategyName}>{row.name}</td>
      <td>
        <span className={`${styles.sourceTag} ${row.source === "USER_PROMPT" ? styles.sourcePrompt : row.source === "WEB_IMPORT" ? styles.sourceWeb : styles.sourceDsl}`}>
          {row.source}
        </span>
      </td>
      <td className={styles.timeCell}>{row.createdAt}</td>
      <td className={styles.versionCell}>{row.version}</td>
      <td>
        <span className={styles.tagCell}>
          {row.tags.map((tag) => (
            <span key={tag} className={styles.tagPill}>{tag}</span>
          ))}
        </span>
      </td>
      <td>
        <span className={styles.validCell} data-state={row.status}>
          <i aria-hidden="true" />
          {statusLabel}
        </span>
      </td>
      <td>
        <span className={styles.rowActions}>
          <button type="button" aria-label={`Chạy backtest ${row.name}`} disabled={!canRun} onClick={() => row.strategyId && onRun(row.strategyId)}>
            <Icon name="play" />
          </button>
          <button type="button" aria-label={`Tuỳ chọn khác cho ${row.name}`} disabled>
            <Icon name="more-vertical" />
          </button>
        </span>
      </td>
    </tr>
  );
}
