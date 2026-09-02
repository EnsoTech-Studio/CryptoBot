"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { RefObject } from "react";

import { Icon } from "../ui/Icon";
import { isActiveRoute, navigationItems } from "./navigation";
import styles from "./shell.module.css";
import { UserMenu } from "./UserMenu";

export function AppSidebar({ open, collapsed, onToggleCollapse, onClose, closeButtonRef }: { open: boolean; collapsed: boolean; onToggleCollapse: () => void; onClose: () => void; closeButtonRef: RefObject<HTMLButtonElement | null> }) {
  const pathname = usePathname();

  return (
    <aside id="app-navigation" className={`${styles.sidebar} ${open ? styles.sidebarOpen : ""}`} aria-label="Điều hướng workspace">
      <div className={styles.sidebarHead}>
        <Link href="/" className={styles.brand} onClick={onClose} aria-label="Crypto Strategy Lab - Realtime">
          <span className={styles.brandMark}><Icon name="flask" /></span>
          <span><strong>Crypto<br />Strategy Lab</strong></span>
        </Link>
        <button
          type="button"
          className={styles.collapseToggle}
          onClick={onToggleCollapse}
          aria-label={collapsed ? "Mở rộng panel điều hướng" : "Thu gọn panel điều hướng"}
          aria-expanded={!collapsed}
          title={collapsed ? "Mở rộng panel" : "Thu gọn panel"}
        >
          <Icon name={collapsed ? "chevron-right" : "chevron-left"} />
        </button>
        <button ref={closeButtonRef} type="button" className={styles.drawerClose} onClick={onClose} aria-label="Đóng menu">
          <Icon name="close" />
        </button>
      </div>

      <nav className={styles.navigation} aria-label="Các màn hình chính">
        {navigationItems.map((item) => {
          const active = isActiveRoute(pathname, item);
          const content = <><Icon name={item.icon} /><span>{item.label}</span>{!item.available ? <small>Sớm</small> : null}</>;
          return item.available ? (
            <Link key={item.href} href={item.href} title={collapsed ? item.label : undefined} aria-current={active ? "page" : undefined} onClick={onClose}>{content}</Link>
          ) : (
            <span key={item.href} className={styles.disabledNav} aria-disabled="true" title={`${item.label} sẽ được triển khai ở bước tiếp theo`}>{content}</span>
          );
        })}
      </nav>

      <div className={styles.sidebarFooter}>
        <div className={styles.planCard}>
          <span className={styles.planIcon}><Icon name="graduation" /></span>
          <div><strong>Pro Student</strong><p>Gói đang dùng</p><small>Hết hạn: 20/06/2025</small></div>
        </div>
        <UserMenu />
      </div>
    </aside>
  );
}
