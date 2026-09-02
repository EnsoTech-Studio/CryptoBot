"use client";

import { usePathname } from "next/navigation";
import type { RefObject } from "react";

import { useWorkspace } from "../../providers/workspace";
import { Icon } from "../ui/Icon";
import { pageMeta } from "./navigation";
import { SourceStatus } from "./SourceStatus";
import styles from "./shell.module.css";

export function PageHeader({ navigationOpen, onOpenNavigation, menuButtonRef }: { navigationOpen: boolean; onOpenNavigation: () => void; menuButtonRef: RefObject<HTMLButtonElement | null> }) {
  const pathname = usePathname();
  const { streamLabel, dataMode, inspectorOpen, inspectorTab, openInspector, closeInspector } = useWorkspace();
  const meta = pageMeta(pathname);

  return (
    <header className={styles.pageHeader} data-route={pathname}>
      <button
        ref={menuButtonRef}
        type="button"
        className={styles.menuButton}
        onClick={onOpenNavigation}
        aria-label="Mở menu"
        aria-controls="app-navigation"
        aria-expanded={navigationOpen}
      >
        <Icon name="menu" />
      </button>

      <div className={styles.pageTitle}>
        <h1>{meta.title}</h1>
        {meta.subtitle ? <p>{meta.subtitle}</p> : null}
      </div>

      <div className={styles.headerSource}>
        <SourceStatus state={streamLabel} dataMode={dataMode} />
      </div>

      <div className={styles.headerActions}>
        <button
          type="button"
          className={styles.inspectorToggle}
          onClick={() => (inspectorOpen ? closeInspector() : openInspector(inspectorTab))}
          aria-label={inspectorOpen ? "Ẩn Inspector" : "Mở Inspector"}
          aria-controls="workspace-inspector"
          aria-expanded={inspectorOpen}
          title={inspectorOpen ? "Ẩn Inspector" : "Mở Inspector"}
        >
          <Icon name={inspectorOpen ? "close" : "expand"} />
          <span>{inspectorOpen ? "Ẩn Inspector" : "Mở Inspector"}</span>
        </button>
        <details className={styles.helpMenu}>
          <summary aria-label="Trợ giúp"><Icon name="help" /></summary>
          <div>
            <strong>Trạng thái dữ liệu</strong>
            <p>Biểu đồ dùng dữ liệu thật từ market backend. Nếu nguồn không khả dụng, giao diện báo lỗi rõ ràng và không tự thay bằng dữ liệu mô phỏng.</p>
          </div>
        </details>
        <span className={styles.headerIcon} role="img" aria-label="Không có thông báo mới" title="Không có thông báo mới">
          <Icon name="bell" />
        </span>
      </div>
    </header>
  );
}
