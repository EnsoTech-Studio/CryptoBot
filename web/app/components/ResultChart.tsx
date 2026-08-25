"use client";

import { formatNumber } from "../../lib/format";
import { useWorkspace } from "../providers/workspace";
import { ChartCanvas } from "./charts/ChartCanvas";
import { EmptyState } from "./States";

export function ResultChart() {
  const { result, experiment, openInspector } = useWorkspace();

  if (!result || !experiment) {
    return (
      <section className="surface result-chart" aria-label="Backtest visualization">
        <div className="surface-head">
          <div>
            <p className="eyebrow">Backtest visualization</p>
            <h2>No completed run</h2>
          </div>
        </div>
        <EmptyState title="Awaiting a run">
          Queue a backtest to render its candles, signals, entries, exits and risk lines here.
        </EmptyState>
      </section>
    );
  }

  return (
    <section className="surface result-chart" aria-label="Backtest visualization">
      <div className="surface-head">
        <div>
          <p className="eyebrow">Backtest visualization</p>
          <h2>{experiment.candidate_hash.slice(0, 12)}</h2>
          <p className="surface-subtitle">
            {result.trades.length} executions · return {formatNumber(experiment.metrics?.total_return_pct)}% on the locked snapshot.
          </p>
        </div>
        <div className="head-actions">
          <span className="dataset-pill">{experiment.dataset_version}</span>
          <button className="ghost-action compact-action" onClick={() => openInspector("metrics")}>Inspect</button>
        </div>
      </div>
      <ChartCanvas
        candles={result.candles}
        series={result.series}
        markers={result.signalMarkers}
        executionMarkers={result.executionMarkers}
        size="result"
      />
    </section>
  );
}
