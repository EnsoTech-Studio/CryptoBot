"use client";

import { useState } from "react";

import { formatCompact, formatPrice } from "../../lib/format";
import { useWorkspace } from "../providers/workspace";
import { Stat } from "./Metric";

function SunIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="3.5" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.42 1.42M17.65 17.65l1.42 1.42M2 12h2M20 12h2M4.93 19.07l1.42-1.42M17.65 6.35l1.42-1.42" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M20.2 15.1A8.5 8.5 0 0 1 8.9 3.8 8.6 8.6 0 1 0 20.2 15.1Z" />
    </svg>
  );
}

export function InstrumentHeader() {
  const {
    user, login, logout, theme, chooseTheme,
    latestCandle, headerChange, streamLabel,
    readyPanelCount, panels, activeStrategyCount, signalCount,
    experiment, coverage, notice, runBacktest, startSearch,
  } = useWorkspace();

  const [email, setEmail] = useState("researcher@example.com");
  const [password, setPassword] = useState("Research#2026");

  return (
    <header className="instrument-header">
      <div className="instrument-row">
        <div className="instrument-identity">
          <h1 className="instrument-pair">ETHUSDT<span>perp</span></h1>
          <p className="instrument-provider">Binance USD-M · simulation only</p>
        </div>
        <div className="instrument-quote">
          <strong>{latestCandle ? formatPrice(latestCandle.close) : "—"}</strong>
          <span className={`delta ${headerChange == null || headerChange >= 0 ? "positive" : "negative"}`}>
            {headerChange == null ? "awaiting feed" : `${headerChange >= 0 ? "+" : ""}${headerChange.toFixed(2)}%`}
          </span>
          <span className={`status-pill ${streamLabel.toLowerCase()}`}><i />{streamLabel}</span>
        </div>
        <div className="instrument-actions">
          <div className="theme-toggle" role="group" aria-label="Chọn giao diện sáng hoặc tối">
            <button
              className={theme === "light" ? "active" : ""}
              type="button"
              onClick={() => chooseTheme("light")}
              aria-label="Bật light mode"
              aria-pressed={theme === "light"}
              title="Light mode"
            >
              <SunIcon />
            </button>
            <button
              className={theme === "dark" ? "active" : ""}
              type="button"
              onClick={() => chooseTheme("dark")}
              aria-label="Bật dark mode"
              aria-pressed={theme === "dark"}
              title="Dark mode"
            >
              <MoonIcon />
            </button>
          </div>
          {user ? (
            <div className="session-panel">
              <div className="user-copy"><span>{user.display_name}</span><strong>{user.role}</strong></div>
              <button className="ghost-action compact-action" onClick={() => void logout()}>Logout</button>
            </div>
          ) : (
            <form
              className="session-panel"
              onSubmit={(event) => {
                event.preventDefault();
                void login(email, password);
              }}
            >
              <input value={email} onChange={(event) => setEmail(event.target.value)} type="email" autoComplete="email" aria-label="Email" placeholder="email" required />
              <input value={password} onChange={(event) => setPassword(event.target.value)} type="password" autoComplete="current-password" aria-label="Password" placeholder="password" required />
              <button className="primary-action compact-action" type="submit">Login</button>
            </form>
          )}
        </div>
      </div>

      <div className="instrument-row">
        <div className="instrument-stats">
          <Stat label="Last close" value={latestCandle ? formatPrice(latestCandle.close) : "waiting"} />
          <Stat label="Volume" value={latestCandle ? formatCompact(latestCandle.volume) : "0"} />
          <Stat label="Panels live" value={`${readyPanelCount}/${panels.length}`} />
          <Stat label="Strategies" value={String(activeStrategyCount)} />
          <Stat label="Signals" value={String(signalCount)} />
          <Stat label="Backtest" value={experiment?.status ?? "idle"} />
          <Stat label="News coverage" value={coverage ? `${coverage.items_analyzed}/${coverage.items_total}` : "0/0"} />
        </div>
        <div className="instrument-actions">
          <button className="primary-action" onClick={() => void runBacktest()} disabled={!user}>Run backtest</button>
          <button className="ghost-action" onClick={() => void startSearch()} disabled={!user}>Start search</button>
        </div>
      </div>

      <p className={`notice-bar ${notice.tone}`} role="status" aria-live="polite">
        <span className={`stream-dot ${streamLabel.toLowerCase()}`} />
        {notice.text}
      </p>
    </header>
  );
}
