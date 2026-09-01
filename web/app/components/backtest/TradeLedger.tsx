"use client";

import { useEffect, useRef, useState } from "react";

import { needsMoreTradesForPage, PAGE_SIZES } from "../../../lib/backtest";
import { api, type Trade } from "../../../lib/api";
import { Panel, Select } from "../ui/Foundation";
import { Icon } from "../ui/Icon";
import styles from "./backtest.module.css";

/* Trade ledger uses cursor pagination after the initial result page. */
export function TradeLedger({
  trades,
  symbol,
  csvExportUrl,
  selectedTradeSequence,
  onSelectTrade,
  experimentId,
  nextTradeCursor,
  totalTrades,
}: {
  trades: Trade[];
  symbol: string;
  csvExportUrl?: string;
  selectedTradeSequence: number | null;
  onSelectTrade: (sequenceNo: number) => void;
  experimentId?: string;
  nextTradeCursor: number | null;
  totalTrades?: number;
}) {
  const [pageSize, setPageSize] = useState<number>(10);
  const [page, setPage] = useState(1);
  const [loadedTrades, setLoadedTrades] = useState(trades);
  const [cursor, setCursor] = useState(nextTradeCursor);
  const [loadingMore, setLoadingMore] = useState(false);
  const loadingRef = useRef(false);

  const knownTotal = cursor === null ? loadedTrades.length : Math.max(loadedTrades.length, totalTrades ?? 0);
  const totalPages = Math.max(1, Math.ceil(knownTotal / pageSize));
  const currentPage = Math.min(page, totalPages);
  const start = (currentPage - 1) * pageSize;
  const rows = loadedTrades.slice(start, start + pageSize);

  useEffect(() => {
    if (!experimentId || loadingRef.current || !needsMoreTradesForPage(loadedTrades.length, currentPage, pageSize, cursor)) return;
    let cancelled = false;
    loadingRef.current = true;
    void Promise.resolve().then(() => {
      if (!cancelled) setLoadingMore(true);
      return api.experimentTrades(experimentId, cursor ?? undefined);
    }).then((next) => {
      if (!cancelled) {
        setLoadedTrades((current) => [...current, ...next.trades.filter((trade) => !current.some((item) => item.sequence_no === trade.sequence_no))]);
        setCursor(next.next_cursor);
      }
    }).catch(() => undefined).finally(() => {
      loadingRef.current = false;
      if (!cancelled) setLoadingMore(false);
    });
    return () => { cancelled = true; };
  }, [cursor, currentPage, experimentId, loadedTrades.length, pageSize]);

  return (
    <Panel
      title="Danh sách lệnh giao dịch"
      action={csvExportUrl ? (
        <a className={styles.expandButton} href={csvExportUrl} download>
          <Icon name="download" aria-hidden="true" /> Xuất CSV
        </a>
      ) : null}
    >
      <div className={styles.ledgerWrap}>
        <table className={styles.ledger}>
          <thead>
            <tr>
              <th scope="col">#</th>
              <th scope="col">Pair / Coin</th>
              <th scope="col">Thời gian vào lệnh</th>
              <th scope="col">Hướng</th>
              <th scope="col">Giá vào</th>
              <th scope="col">Stoploss</th>
              <th scope="col">TakeProfit</th>
              <th scope="col">Giá kết thúc</th>
              <th scope="col">Phí</th>
              <th scope="col">Slippage</th>
              <th scope="col">Profit (USD)</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={11} className={styles.mockNote}>
                  Run này không phát sinh lệnh nào.
                </td>
              </tr>
            ) : (
              rows.map((trade) => (
                <tr
                  key={trade.id}
                  className={trade.sequence_no === selectedTradeSequence ? styles.ledgerSelected : undefined}
                  onClick={() => onSelectTrade(trade.sequence_no)}
                  onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") onSelectTrade(trade.sequence_no); }}
                  role="button"
                  tabIndex={0}
                  aria-label={`Highlight trade ${trade.sequence_no} on chart`}
                  aria-pressed={trade.sequence_no === selectedTradeSequence}
                >
                  <td className={styles.numeric}>{trade.sequence_no}</td>
                  <td>{trade.symbol || symbol}</td>
                  <td>{ledgerDate(trade.entry_time)}</td>
                  <td>
                    <span className={`${styles.sideTag} ${isLong(trade.side) ? styles.sideLong : styles.sideShort}`}>
                      {isLong(trade.side) ? "LONG" : "SHORT"}
                    </span>
                  </td>
                  <td className={styles.numeric}>{price(trade.entry_price)}</td>
                  <td className={styles.numeric}>{trade.sl_price === null ? "—" : price(trade.sl_price)}</td>
                  <td className={styles.numeric}>{trade.tp_price === null ? "—" : price(trade.tp_price)}</td>
                  <td className={styles.numeric}>{price(trade.exit_price)}</td>
                  <td className={styles.cost}>-{trade.fee_paid.toFixed(2)}</td>
                  <td className={styles.cost}>-{trade.slippage_cost.toFixed(2)}</td>
                  <td className={`${styles.money} ${trade.pnl >= 0 ? styles.gain : styles.loss}`}>
                    {trade.pnl >= 0 ? "+" : ""}{trade.pnl.toFixed(2)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className={styles.ledgerFoot}>
        <span className={styles.pageSizeGroup}>
          <span>Hiển thị</span>
          <span className={styles.pageSizeSelect}>
            <Select
              value={pageSize}
              aria-label="Số lệnh mỗi trang"
              onChange={(event) => {
                setPageSize(Number(event.target.value));
                setPage(1);
              }}
            >
              {PAGE_SIZES.map((size) => (
                <option key={size} value={size}>{size}</option>
              ))}
            </Select>
          </span>
          <span className={styles.rangeLabel}>
            {loadedTrades.length === 0 ? "0 lệnh" : `${start + 1}–${Math.min(start + pageSize, knownTotal)} của ${knownTotal} lệnh${loadingMore ? " (đang tải…)" : ""}`}
          </span>
        </span>

        <Pager page={currentPage} totalPages={totalPages} onPage={setPage} />
      </div>

    </Panel>
  );
}

function ledgerDate(value: string) {
  return new Date(value).toLocaleString("en-GB", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "UTC",
  }).replace(",", "");
}

function Pager({ page, totalPages, onPage }: { page: number; totalPages: number; onPage: (page: number) => void }) {
  return (
    <nav className={styles.pager} aria-label="Phân trang danh sách lệnh">
      <button type="button" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Trang trước">
        <Icon name="chevron-left" />
      </button>
      {pageWindow(page, totalPages).map((item, index) =>
        item === null ? (
          <button key={`gap-${index}`} type="button" className={styles.pageGap} disabled aria-hidden="true">…</button>
        ) : (
          <button
            key={item}
            type="button"
            className={item === page ? styles.pageActive : ""}
            aria-current={item === page ? "page" : undefined}
            onClick={() => onPage(item)}
          >
            {item}
          </button>
        ),
      )}
      <button type="button" disabled={page >= totalPages} onClick={() => onPage(page + 1)} aria-label="Trang sau">
        <Icon name="chevron-right" />
      </button>
    </nav>
  );
}

/* 1 2 3 … last, as in the reference footer. */
function pageWindow(page: number, totalPages: number): Array<number | null> {
  if (totalPages <= 5) return Array.from({ length: totalPages }, (_, index) => index + 1);
  const head = [1, 2, 3].filter((value) => value <= totalPages);
  const window = new Set<number>(head);
  window.add(page);
  window.add(totalPages);
  const sorted = [...window].filter((value) => value >= 1 && value <= totalPages).sort((a, b) => a - b);
  const output: Array<number | null> = [];
  sorted.forEach((value, index) => {
    if (index > 0 && value - sorted[index - 1] > 1) output.push(null);
    output.push(value);
  });
  return output;
}

function isLong(side: string) {
  return side.toUpperCase().startsWith("LONG") || side.toUpperCase() === "BUY";
}

function price(value: number) {
  return value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
