"use client";

import { formatNumber } from "../../lib/format";
import type { ExperimentSummary, SearchRun } from "../../lib/api";
import { useWorkspace } from "../providers/workspace";
import { EmptyState } from "./States";
import { Metric } from "./Metric";

export function BacktestPanel() {
  const { experiment, user, runBacktest, openInspector, result } = useWorkspace();

  return (
    <section id="backtest" className="surface operation-panel">
      <div className="surface-head">
        <div>
          <p className="eyebrow">Experiment / 01</p>
          <h2>Async backtest</h2>
          <p className="surface-subtitle">Immutable snapshot, deterministic execution.</p>
        </div>
        <button className="primary-action" onClick={() => void runBacktest()} disabled={!user}>Run</button>
      </div>
      <div className="operation-body">
        <ExecutionTimeline status={experiment?.status} />
        <div className="operation-stats">
          {experiment ? (
            <>
              <div className="metric-grid">
                <Metric label="Status" value={experiment.status} />
                <Metric label="Signals" value={String(experiment.signals_count)} />
                <Metric label="Trades" value={String(experiment.metrics?.trade_count ?? 0)} />
                <Metric label="Score" value={formatNumber(experiment.metrics?.score)} />
              </div>
              {result ? (
                <div className="button-row">
                  <button className="ghost-action" onClick={() => openInspector("metrics")}>View metrics</button>
                  <button className="ghost-action" onClick={() => openInspector("trades")}>View trades</button>
                </div>
              ) : null}
            </>
          ) : (
            <EmptyState title="Ready">
              No active experiment. Queue a composite snapshot to inspect trades, equity and provenance.
            </EmptyState>
          )}
        </div>
      </div>
    </section>
  );
}

export function ExecutionTimeline({ status }: { status?: ExperimentSummary["status"] }) {
  const stages = [
    { key: "queued", label: "Snapshot locked", detail: "Dataset + candidate hash" },
    { key: "running", label: "Execution engine", detail: "Signals + trade simulation" },
    { key: "completed", label: "Evaluation complete", detail: "Metrics + provenance" },
  ] as const;
  const stageIndex = status === "completed" ? 2 : status === "running" ? 1 : status === "queued" ? 0 : -1;

  return (
    <ol className="execution-timeline" aria-label="Backtest progress">
      {stages.map((stage, index) => {
        const state = index < stageIndex ? "complete" : index === stageIndex ? "active" : "pending";
        return (
          <li key={stage.key} className={state}>
            <span className="timeline-marker">{index < stageIndex || status === "completed" ? "✓" : String(index + 1).padStart(2, "0")}</span>
            <div><strong>{stage.label}</strong><span>{stage.detail}</span></div>
          </li>
        );
      })}
      {status === "failed" || status === "cancelled" ? (
        <li className="failed"><span className="timeline-marker">!</span><div><strong>{status}</strong><span>Review the run status and retry.</span></div></li>
      ) : null}
    </ol>
  );
}

export function SearchPanel() {
  const { search, user, startSearch, searchAction } = useWorkspace();

  return (
    <section id="search" className="surface operation-panel">
      <div className="surface-head">
        <div>
          <p className="eyebrow">Search loop / 02</p>
          <h2>Generate, queue, rank</h2>
          <p className="surface-subtitle">Explore candidate strategies against the locked dataset.</p>
        </div>
        <button className="primary-action" onClick={() => void startSearch()} disabled={!user}>Start</button>
      </div>
      <div className="search-overview">
        <SearchProgress search={search} />
        <div className="operation-stats">
          {search ? (
            <>
              <div className="metric-grid">
                <Metric label="Generated" value={String(search.candidates.generated)} />
                <Metric label="Tested" value={String(search.candidates.tested)} />
                <Metric label="Failed" value={String(search.candidates.failed)} />
                <Metric label="Best" value={formatNumber(search.best_score)} />
              </div>
              <div className="button-row">
                <button className="ghost-action" onClick={() => void searchAction("pause")}>Pause</button>
                <button className="ghost-action" onClick={() => void searchAction("resume")}>Resume</button>
                <button className="ghost-action danger" onClick={() => void searchAction("cancel")}>Cancel</button>
              </div>
            </>
          ) : (
            <EmptyState title="Awaiting run">
              No active loop. Search results will update the Top-K board as candidates finish.
            </EmptyState>
          )}
        </div>
      </div>
    </section>
  );
}

export function SearchProgress({ search }: { search: SearchRun | null }) {
  const generated = search?.candidates.generated ?? 0;
  const tested = search?.candidates.tested ?? 0;
  const progress = generated > 0 ? Math.min(100, Math.round((tested / generated) * 100)) : 0;
  const circumference = 2 * Math.PI * 38;

  return (
    <div className="search-progress" aria-label={`Search progress ${progress}%`}>
      <svg viewBox="0 0 100 100" aria-hidden="true">
        <circle className="progress-track" cx="50" cy="50" r="38" />
        <circle className="progress-value" cx="50" cy="50" r="38" strokeDasharray={circumference} strokeDashoffset={circumference * (1 - progress / 100)} />
      </svg>
      <div><strong>{progress}%</strong><span>{search?.status ?? "idle"}</span></div>
    </div>
  );
}
