"use client";

import { useState } from "react";
import type { ReactNode } from "react";

import type { Metrics } from "../../../lib/api";
import { canCancelBacktest } from "../../../lib/backtest";
import { Button, Dialog, Panel, StatusDot } from "../ui/Foundation";
import { Pagination } from "../ui/Pagination";
import styles from "./backtest.module.css";

const HISTORY_PAGE_SIZE = 5;

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
  onVisualize,
}: {
  records: ExperimentHistoryRecord[];
  selectedIds: string[];
  onToggle: (id: string) => void;
  onCancel: (id: string) => void;
  onVisualize: (id: string) => void;
}) {
  const [detailId, setDetailId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const detail = records.find((record) => record.id === detailId) ?? null;
  const selected = records.filter((record) => selectedIds.includes(record.id));
  const totalPages = Math.max(1, Math.ceil(records.length / HISTORY_PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const pageStart = (currentPage - 1) * HISTORY_PAGE_SIZE;
  const visibleRecords = records.slice(pageStart, pageStart + HISTORY_PAGE_SIZE);

  return (
    <>
      <Panel
        title="Experiment history"
        info="Các experiment đã tạo trên thiết bị này khi đăng nhập tài khoản hiện tại."
        action={selected.length > 1 ? <span className={styles.compareHint}>{selected.length} đã chọn để so sánh</span> : null}
      >
        {records.length === 0 ? (
          <p className={styles.emptyHistory}>Chưa có experiment đã lưu trên thiết bị này. Hãy chạy backtest để tạo experiment.</p>
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
                {visibleRecords.map((record) => (
                  <tr key={record.id}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(record.id)}
                        onChange={() => onToggle(record.id)}
                        aria-label={`Chọn ${record.id} để so sánh`}
                      />
                    </td>
                    <td className={styles.historyId}>
                      <button type="button" className={styles.historyOpen} onClick={() => onVisualize(record.id)} aria-label={`Xem biểu đồ experiment ${record.id}`}>
                        {record.id.slice(0, 12)}
                      </button>
                    </td>
                    <td><Status status={record.status} /></td>
                    <td>{record.symbol} · {record.timeframe}</td>
                    <td>{record.strategy}<small>{record.strategyVersion}</small></td>
                    <td className={styles.historyDataset}>{record.datasetVersion || "—"}</td>
                    <td className={record.metrics && record.metrics.total_return_pct >= 0 ? styles.gain : styles.loss}>
                      {record.metrics ? `${record.metrics.total_return_pct >= 0 ? "+" : ""}${record.metrics.total_return_pct.toFixed(2)}%` : "—"}
                    </td>
                    <td className={styles.historyActions}>
                      <div className={styles.historyActionButtons}>
                        <Button variant="ghost" onClick={() => setDetailId(record.id)}>Chi tiết</Button>
                        {canCancelBacktest(record.status) ? <Button variant="danger" onClick={() => onCancel(record.id)}>Hủy</Button> : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {records.length > 0 ? (
          <div className={styles.historyFoot}>
            <span>{pageStart + 1}–{Math.min(pageStart + HISTORY_PAGE_SIZE, records.length)} của {records.length} experiment</span>
            <Pagination page={currentPage} totalPages={totalPages} onPage={setPage} ariaLabel="Phân trang experiment history" />
          </div>
        ) : null}
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
    ["Total Return", (value) => `${formatMetric(value.total_return_pct)}%`],
    ["Total Profit/Loss", (value) => formatMetric(value.net_profit)],
    ["Win Rate", (value) => `${formatMetric(value.win_rate_pct)}%`],
    ["Trades", (value) => String(value.trade_count)],
    ["Max Drawdown", (value) => `${formatMetric(value.max_drawdown_pct)}%`],
    ["Profit Factor", (value) => formatMetric(value.profit_factor)],
    ["Sharpe Ratio", (value) => formatMetric(value.sharpe_ratio)],
  ];
  return (
    <Panel title="So sánh experiment" info="So sánh các experiment đã lưu trên thiết bị này.">
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
      <Detail label="Strategy" value={`${record.strategy} · ${record.strategyVersion}`} />
      <Detail label="Dataset version" value={record.datasetVersion || "Chưa chọn"} />
      <Detail label="Strategy definition" value={<JsonValue value={record.parameters} />} wide />
      <Detail label="Execution config" value={<JsonValue value={record.execution} />} wide />
      {record.metrics ? <Detail label="Metrics" value={`Return ${formatMetric(record.metrics.total_return_pct)}% · Win rate ${formatMetric(record.metrics.win_rate_pct)}% · PF ${formatMetric(record.metrics.profit_factor)} · Sharpe ${formatMetric(record.metrics.sharpe_ratio)}`} wide /> : null}
    </div>
  );
}

function formatMetric(value: number | null | undefined): string {
  return value == null || !Number.isFinite(value) ? "—" : value.toFixed(2);
}

function JsonValue({ value }: { value: unknown }) {
  return <pre className={styles.detailJson}>{JSON.stringify(value, null, 2)}</pre>;
}

function Detail({ label, value, wide = false }: { label: string; value: ReactNode; wide?: boolean }) {
  return <div className={`${styles.detailItem} ${wide ? styles.detailWide : ""}`}><span>{label}</span><strong>{value}</strong></div>;
}

function Status({ status }: { status: string }) {
  const tone = status === "completed" ? "live" : status === "failed" || status === "cancelled" ? "error" : status === "queued" || status === "running" ? "syncing" : "neutral";
  return <span className={styles.historyStatus}><StatusDot tone={tone} />{status}</span>;
}
