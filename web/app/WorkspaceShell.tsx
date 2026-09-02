"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { usePathname } from "next/navigation";

import { WorkspaceProvider, useWorkspace } from "./providers/workspace";
import { Inspector } from "./components/Inspector";
import { AppSidebar } from "./components/shell/AppSidebar";
import { PageHeader } from "./components/shell/PageHeader";
import styles from "./components/shell/shell.module.css";
import { StatusMessage } from "./components/ui/Foundation";

/* One shell for every route. The provider sits above it, so navigating between
   pages keeps the market sockets, polls and inspector state alive. */
export function WorkspaceShell({ children }: { children: ReactNode }) {
  return (
    <WorkspaceProvider>
      <Shell>{children}</Shell>
    </WorkspaceProvider>
  );
}

function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { inspectorOpen, notice } = useWorkspace();
  const [navigationOpen, setNavigationOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const navigationWasOpen = useRef(false);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      try { setSidebarCollapsed(window.localStorage.getItem("csl.sidebar-collapsed") === "true"); } catch { /* best effort */ }
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  function toggleSidebar() {
    setSidebarCollapsed((current) => {
      const next = !current;
      try { window.localStorage.setItem("csl.sidebar-collapsed", String(next)); } catch { /* best effort */ }
      return next;
    });
  }

  useEffect(() => {
    if (!navigationOpen) {
      if (navigationWasOpen.current) {
        navigationWasOpen.current = false;
        menuButtonRef.current?.focus();
      }
      return;
    }

    navigationWasOpen.current = true;
    const focusFrame = window.requestAnimationFrame(() => closeButtonRef.current?.focus());
    const keepFocusInDrawer = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setNavigationOpen(false);
        return;
      }
      if (event.key !== "Tab") return;
      const drawer = document.getElementById("app-navigation");
      const focusable = Array.from(drawer?.querySelectorAll<HTMLElement>("a[href], button:not(:disabled), input:not(:disabled), summary") ?? []);
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable.at(-1)!;
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", keepFocusInDrawer);
    return () => {
      window.cancelAnimationFrame(focusFrame);
      window.removeEventListener("keydown", keepFocusInDrawer);
    };
  }, [navigationOpen]);

  return (
    <div className={`${styles.shell} ${inspectorOpen ? styles.withInspector : ""} ${sidebarCollapsed ? styles.sidebarCollapsed : ""}`} data-route={pathname}>
      <a className="skip-link" href="#workspace-main">Đi đến nội dung chính</a>
      <AppSidebar
        open={navigationOpen}
        collapsed={sidebarCollapsed}
        onToggleCollapse={toggleSidebar}
        onClose={() => setNavigationOpen(false)}
        closeButtonRef={closeButtonRef}
      />
      {navigationOpen ? <button type="button" className={styles.drawerBackdrop} onClick={() => setNavigationOpen(false)} aria-label="Đóng menu" /> : null}
      <section className={styles.main} id="workspace-main" tabIndex={-1} inert={navigationOpen ? true : undefined}>
        <PageHeader navigationOpen={navigationOpen} onOpenNavigation={() => setNavigationOpen(true)} menuButtonRef={menuButtonRef} />
        {notice.tone === "error" ? <div className={styles.noticeSlot}><StatusMessage tone="error">{notice.text}</StatusMessage></div> : null}
        <div className={styles.content}>{children}</div>
      </section>
      <Inspector />
    </div>
  );
}
