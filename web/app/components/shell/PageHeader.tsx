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
  const { streamLabel } = useWorkspace();
  const meta = pageMeta(pathname);

  return (
    <header className={styles.pageHeader}>
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

      <div className={styles.headerActions}>
        <SourceStatus state={streamLabel} />
        <details className={styles.helpMenu}>
          <summary aria-label="Trợ giúp"><Icon name="help" /></summary>
          <div>
            <strong>Trạng thái dữ liệu</strong>
            <p>Live, Syncing và Degraded phản ánh kết nối thật. Hệ thống không tạo dữ liệu mẫu khi backend không khả dụng.</p>
          </div>
        </details>
        <span className={styles.headerIcon} role="img" aria-label="Không có thông báo mới" title="Không có thông báo mới">
          <Icon name="bell" />
        </span>
      </div>
    </header>
  );
}
