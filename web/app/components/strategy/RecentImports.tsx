"use client";

import { IMPORT_ROWS, type ImportRow } from "../../../lib/strategy-authoring";
import { Panel } from "../ui/Foundation";
import { Icon } from "../ui/Icon";
import styles from "./strategy.module.css";

/* Bottom row. The strategy registry response has no source, tags or creation
   timestamp, so these rows are illustrative until an authored-strategy list
   endpoint exists. Run and menu actions are disabled for the same reason. */
export function RecentImports() {
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
            {IMPORT_ROWS.map((row) => (
              <ImportTableRow key={row.name} row={row} />
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function ImportTableRow({ row }: { row: ImportRow }) {
  return (
    <tr>
      <td className={styles.strategyName}>{row.name}</td>
      <td>
        <span className={`${styles.sourceTag} ${row.source === "USER_PROMPT" ? styles.sourcePrompt : styles.sourceWeb}`}>
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
        <span className={styles.validCell}>
          <i aria-hidden="true" />
          {row.valid ? "Hợp lệ" : "Không hợp lệ"}
        </span>
      </td>
      <td>
        <span className={styles.rowActions}>
          <button type="button" aria-label={`Chạy backtest ${row.name}`}>
            <Icon name="play" />
          </button>
          <button type="button" aria-label={`Tuỳ chọn khác cho ${row.name}`}>
            <Icon name="more-vertical" />
          </button>
        </span>
      </td>
    </tr>
  );
}
