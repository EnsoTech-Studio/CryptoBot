"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useWorkspace } from "../providers/workspace";

const navItems: Array<{ href: string; number: string; label: string }> = [
  { href: "/", number: "01", label: "Dashboard" },
  { href: "/backtests", number: "02", label: "Backtests" },
  { href: "/search", number: "03", label: "Search" },
  { href: "/leaderboard", number: "04", label: "Leaderboard" },
  { href: "/news", number: "05", label: "News" },
];

export function LeftRail() {
  const pathname = usePathname();
  const { streamLabel, readyPanelCount, panels } = useWorkspace();

  return (
    <aside className="left-rail" aria-label="Workspace navigation">
      <div className="brand-block">
        <span className="brand-mark" aria-hidden="true">CL</span>
        <div>
          <strong>Crypto Strategy Lab</strong>
          <span>Research workspace</span>
        </div>
      </div>

      <p className="rail-label">Workspace</p>
      <nav className="rail-nav">
        {navItems.map((item) => {
          const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          return (
            <Link key={item.href} href={item.href} aria-current={active ? "page" : undefined}>
              <span>{item.number}</span> {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="rail-card">
        <div className="rail-status">
          <span className={`stream-dot ${streamLabel.toLowerCase()}`} />
          <span>{streamLabel}</span>
        </div>
        <div><span>Market</span><strong>ETH / USDT</strong></div>
        <div><span>Provider</span><strong>Binance USD-M</strong></div>
        <div><span>Panels</span><strong>{readyPanelCount}/{panels.length} active</strong></div>
        <small>UTC · simulation feed</small>
      </div>
    </aside>
  );
}
