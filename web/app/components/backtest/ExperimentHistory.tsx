"use client";

import { useState } from "react";

import type { Metrics } from "../../../lib/api";
import { canCancelBacktest } from "../../../lib/backtest";
import { Button, Dialog, Panel, StatusDot } from "../ui/Foundation";
import styles from "./backtest.module.css";

export type ExperimentHistoryRecord = {
  id: string;
  status: string;
  createdAt: string;
  symbol: string;
  timeframe: string;
  strategy: string;
  strategyVersion: string;
  datasetVersion: string;
  rangeFrom: string;
  rangeTo: string;
  parameters: Record<string, unknown>;
  execution: Record<string, unknown>;
  metrics: Metrics | null;
};

export function ExperimentHistory({
  records,
  selectedIds,
  onToggle,
  onCancel,
}: {
  records: ExperimentHistoryRecord[];
  selectedIds: string[];
  onToggle: (id: string) => void;
  onCancel: (id: string) => void;
}) {
  const [detailId, setDetailId] = useState<string | null>(null);
  const detail = records.find((record) => record.id === detailId) ?? null;
  const selected = records.filter((record) => selectedIds.includes(record.id));

  return (
    <>
      <Panel
        title="Experiment history"
        info="Các experiment đã tạo trong phiên làm việc này. Backend hiện chưa có endpoint list experiments."
        action={selected.length > 1 ? <span className={styles.compareHint}>{selected.length} đã chọn để so sánh</span> : null}
      >
        {records.length === 0 ? (
          <p className={styles.emptyHistory}>Chưa có experiment trong phiên này. Hãy chạy backtest để tạo experiment.</p>
        ) : (
          <div className={styles.historyWrap}>
            <table className={styles.historyTable}>
              <thead>
                <tr>
                  <th aria-label="Chọn" />
                  <th>Experiment</th>
                  <th>Trạng thái</th>
                  <th>Pair / TF</th>
                  <th>Strategy</th>
                  <th>Dataset</th>
                  <th>Return</th>
                  <th>Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {records.map((record) => (
                  <tr key={record.id}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(record.id)}
                        onChange={() => onToggle(record.id)}
                        aria-label={`Chọn ${record.id} để so sánh`}
                      />
                    </td>
                    <td className={styles.historyId}>{record.id.slice(0, 12)}</td>
                    <td><Status status={record.status} /></td>
                    <td>{record.symbol} · {record.timeframe}</td>
                    <td>{record.strategy}<small>{record.strategyVersion}</small></td>
                    <td className={styles.historyDataset}>{record.datasetVersion || "—"}</td>
                    <td className={record.metrics && record.metrics.total_return_pct >= 0 ? styles.gain : styles.loss}>
                      {record.metrics ? `${record.metrics.total_return_pct >= 0 ? "+" : ""}${record.metrics.total_return_pct.toFixed(2)}%` : "—"}
                    </td>
                    <td className={styles.historyActions}>
                      <Button variant="ghost" onClick={() => setDetailId(record.id)}>Chi tiết</Button>
                      {canCancelBacktest(record.status) ? <Button variant="danger" onClick={() => onCancel(record.id)}>Hủy</Button> : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {selected.length > 1 ? <Comparison records={selected} /> : null}

      <Dialog open={detail !== null} title="Chi tiết experiment" onClose={() => setDetailId(null)}>
        {detail ? <ExperimentDetail record={detail} /> : null}
      </Dialog>
    </>
  );
}

function Comparison({ records }: { records: ExperimentHistoryRecord[] }) {
  const metrics: Array<[string, (value: Metrics) => string]> = [
    ["Total Return", (value) => `${value.total_return_pct.toFixed(2)}%`],
    ["Total Profit/Loss", (value) => value.net_profit.toFixed(2)],
    ["Win Rate", (value) => `${value.win_rate_pct.toFixed(2)}%`],
    ["Trades", (value) => String(value.trade_count)],
    ["Max Drawdown", (value) => `${value.max_drawdown_pct.toFixed(2)}%`],
    ["Profit Factor", (value) => value.profit_factor.toFixed(2)],
    ["Sharpe Ratio", (value) => value.sharpe_ratio.toFixed(2)],
  ];
  return (
    <Panel title="So sánh experiment" info="So sánh các experiment đã chọn trong phiên hiện tại.">
      <div className={styles.compareWrap}>
        <table className={styles.compareTable}>
          <thead><tr><th>Metric</th>{records.map((record) => <th key={record.id}>{record.id.slice(0, 12)}</th>)}</tr></thead>
          <tbody>{metrics.map(([label, format]) => <tr key={label}><th scope="row">{label}</th>{records.map((record) => <td key={record.id}>{record.metrics ? format(record.metrics) : "—"}</td>)}</tr>)}</tbody>
        </table>
      </div>
    </Panel>
  );
}

function ExperimentDetail({ record }: { record: ExperimentHistoryRecord }) {
  return (
    <div className={styles.detailGrid}>
      <Detail label="ID" value={record.id} />
      <Detail label="Trạng thái" value={record.status} />
      <Detail label="Pair / timeframe" value={`${record.symbol} · ${record.timeframe}`} />
      <Detail label="Khoảng thời gian" value={`${record.rangeFrom} → ${record.rangeTo}`} />
      <Detail label="Strategy version" value={`${record.strategy} · ${record.strategyVersion}`} />
      <Detail label="Dataset version" value={record.datasetVersion || "Chưa chọn"} />
      <Detail label="Parameters đã lưu" value={JSON.stringify(record.parameters)} wide />
      <Detail label="Execution config" value={JSON.stringify(record.execution)} wide />
      {record.metrics ? <Detail label="Metrics" value={`Return ${record.metrics.total_return_pct.toFixed(2)}% · Win rate ${record.metrics.win_rate_pct.toFixed(2)}% · PF ${record.metrics.profit_factor.toFixed(2)} · Sharpe ${record.metrics.sharpe_ratio.toFixed(2)}`} wide /> : null}
    </div>
  );
}

function Detail({ label, value, wide = false }: { label: string; value: string; wide?: boolean }) {
  return <div className={`${styles.detailItem} ${wide ? styles.detailWide : ""}`}><span>{label}</span><strong>{value}</strong></div>;
}

function Status({ status }: { status: string }) {
  const tone = status === "completed" ? "live" : status === "failed" || status === "cancelled" ? "error" : status === "queued" || status === "running" ? "syncing" : "neutral";
  return <span className={styles.historyStatus}><StatusDot tone={tone} />{status}</span>;
}
