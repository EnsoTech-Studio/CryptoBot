"use client";

import { compactDateTime, formatNumber, formatPrice } from "../../lib/format";
import type { ExperimentSummary } from "../../lib/api";
import { useWorkspace, type InspectorTab, type ResultBundle } from "../providers/workspace";
import { EquityChart } from "./charts/EquityChart";
import { EmptyState } from "./States";
import { Metric } from "./Metric";

export function Inspector() {
  const { inspectorOpen, inspectorTab, setInspectorTab, closeInspector, experiment, result, provenance } = useWorkspace();

  if (!inspectorOpen) return null;

  const tabs: Array<{ id: InspectorTab; label: string; ready: boolean }> = [
    { id: "metrics", label: "Metrics", ready: Boolean(experiment?.metrics) },
    { id: "trades", label: "Trades", ready: Boolean(result && result.trades.length > 0) },
    { id: "provenance", label: "Provenance", ready: Boolean(provenance) },
  ];

  return (
    <aside className="inspector" aria-label="Inspector">
      <div className="inspector-head">
        <div>
          <p className="eyebrow">Inspector</p>
          <strong>{experiment ? experiment.candidate_hash.slice(0, 12) : "no selection"}</strong>
        </div>
        <button className="icon-action" onClick={closeInspector} aria-label="Close inspector" title="Close (Esc)">×</button>
      </div>

      <div className="inspector-tabs" role="tablist" aria-label="Inspector sections">
        {tabs.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            id={`inspector-tab-${item.id}`}
            aria-selected={inspectorTab === item.id}
            aria-controls="inspector-panel"
            className={`inspector-tab ${inspectorTab === item.id ? "active" : ""}`}
            onClick={() => setInspectorTab(item.id)}
          >
            {item.label}
            {item.ready ? <i className="tab-dot" aria-hidden="true" /> : null}
          </button>
        ))}
      </div>

      <div className="inspector-body" id="inspector-panel" role="tabpanel" aria-labelledby={`inspector-tab-${inspectorTab}`}>
        {inspectorTab === "metrics" ? <MetricsTab experiment={experiment} result={result} /> : null}
        {inspectorTab === "trades" ? <TradesTab result={result} /> : null}
        {inspectorTab === "provenance" ? <ProvenanceTab data={provenance} /> : null}
      </div>
    </aside>
  );
}

function MetricsTab({ experiment, result }: { experiment: ExperimentSummary | null; result: ResultBundle | null }) {
  if (!experiment?.metrics) {
    return <EmptyState title="No evaluation">Run a backtest to populate metrics, the equity curve and drawdown.</EmptyState>;
  }
  const m = experiment.metrics;
  return (
    <>
      <div className="metric-grid">
        <Metric label="Return" value={`${formatNumber(m.total_return_pct)}%`} tone={m.total_return_pct >= 0 ? "positive" : "negative"} />
        <Metric label="Win rate" value={`${formatNumber(m.win_rate_pct)}%`} />
        <Metric label="Max drawdown" value={`${formatNumber(m.max_drawdown_pct)}%`} />
        <Metric label="Sharpe" value={formatNumber(m.sharpe_ratio)} />
        <Metric label="Profit factor" value={formatNumber(m.profit_factor)} />
        <Metric label="Score" value={formatNumber(m.score)} />
      </div>
      <p className="inspector-meta">evaluator {m.evaluator_version} · dataset {experiment.dataset_version}</p>
      {result ? <EquityChart points={result.equity} /> : null}
    </>
  );
}

function TradesTab({ result }: { result: ResultBundle | null }) {
  if (!result || result.trades.length === 0) {
    return <EmptyState title="No executions">The completed run produced no trades, or no run has completed yet.</EmptyState>;
  }
  return (
    <table>
      <thead>
        <tr><th>#</th><th>Entry</th><th>Exit</th><th>PnL</th><th>Reason</th></tr>
      </thead>
      <tbody>
        {result.trades.map((trade) => (
          <tr key={trade.id}>
            <td>{trade.sequence_no}</td>
            <td>{formatPrice(trade.entry_price)}<span>{compactDateTime(trade.entry_time)}</span></td>
            <td>{formatPrice(trade.exit_price)}<span>{compactDateTime(trade.exit_time)}</span></td>
            <td className={trade.pnl >= 0 ? "positive" : "negative"}>{trade.pnl.toFixed(3)}</td>
            <td>{trade.exit_reason}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/* Provenance used to be one JSON blob. Labelled rows make hashes and versions
   scannable; only nested objects fall back to JSON, scoped to their own key. */
function ProvenanceTab({ data }: { data: Record<string, unknown> | null }) {
  if (!data) {
    return <EmptyState title="Nothing traced">Choose Trace on a leaderboard row to load its dataset, evaluator and candidate hashes.</EmptyState>;
  }
  return (
    <dl className="kv-list">
      {Object.entries(data).map(([key, value]) => (
        <div key={key} className="kv-row">
          <dt>{key.replace(/_/g, " ")}</dt>
          <dd>{formatProvenanceValue(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

function formatProvenanceValue(value: unknown): string {
  if (value == null) return "—";
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}
