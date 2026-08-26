import type { Trade } from "./api";

/* Reference-exact ledger and KPI figures for ui-reference/backtest.jpg. Used
   only while no experiment has completed — BacktestScreen prefers the real
   result bundle and only falls back here, with a visible mock label. */

export const MOCK_KPIS = {
  winratePct: 61.8,
  wins: 110,
  losses: 68,
  totalTrades: 178,
  totalProfitUsd: 8.42,
  totalProfitPct: 8.42,
  maxDrawdownUsd: -3.21,
  maxDrawdownPct: -3.21,
};

/* Ten rows matching the reference table, then repeated with shifted timestamps
   so pagination has something to page through (178 total, as the KPI claims). */
const SEED_ROWS: Array<Omit<Trade, "id" | "signal_t" | "quantity">> = [
  { sequence_no: 1, side: "LONG", entry_time: "2026-01-05T06:15:00Z", exit_time: "2026-01-05T08:15:00Z", entry_price: 68_120.5, exit_price: 69_120.0, fee_paid: 0.05, slippage_cost: 0.03, sl_price: 67_620.0, tp_price: 69_120.0, pnl: 0.83, pnl_pct: 0.83, exit_reason: "take_profit" },
  { sequence_no: 2, side: "SHORT", entry_time: "2026-01-05T09:40:00Z", exit_time: "2026-01-05T11:40:00Z", entry_price: 69_450.2, exit_price: 68_430.1, fee_paid: 0.05, slippage_cost: 0.03, sl_price: 69_950.0, tp_price: 68_450.0, pnl: 0.87, pnl_pct: 0.87, exit_reason: "take_profit" },
  { sequence_no: 3, side: "LONG", entry_time: "2026-01-05T12:25:00Z", exit_time: "2026-01-05T14:25:00Z", entry_price: 68_600.1, exit_price: 67_980.0, fee_paid: 0.05, slippage_cost: 0.03, sl_price: 68_100.0, tp_price: 69_600.0, pnl: -0.67, pnl_pct: -0.67, exit_reason: "stop_loss" },
  { sequence_no: 4, side: "SHORT", entry_time: "2026-01-05T16:10:00Z", exit_time: "2026-01-05T18:10:00Z", entry_price: 69_320.3, exit_price: 68_310.4, fee_paid: 0.05, slippage_cost: 0.03, sl_price: 69_820.0, tp_price: 68_320.0, pnl: 0.9, pnl_pct: 0.9, exit_reason: "take_profit" },
  { sequence_no: 5, side: "LONG", entry_time: "2026-01-06T03:50:00Z", exit_time: "2026-01-06T05:50:00Z", entry_price: 68_800.4, exit_price: 69_800.0, fee_paid: 0.05, slippage_cost: 0.03, sl_price: 68_300.0, tp_price: 69_800.0, pnl: 0.95, pnl_pct: 0.95, exit_reason: "take_profit" },
  { sequence_no: 6, side: "SHORT", entry_time: "2026-01-06T08:35:00Z", exit_time: "2026-01-06T10:35:00Z", entry_price: 69_900.8, exit_price: 70_430.0, fee_paid: 0.05, slippage_cost: 0.03, sl_price: 70_400.0, tp_price: 68_900.0, pnl: -0.58, pnl_pct: -0.58, exit_reason: "stop_loss" },
  { sequence_no: 7, side: "LONG", entry_time: "2026-01-06T13:05:00Z", exit_time: "2026-01-06T15:05:00Z", entry_price: 68_950.6, exit_price: 69_930.2, fee_paid: 0.05, slippage_cost: 0.03, sl_price: 68_450.0, tp_price: 69_950.0, pnl: 0.92, pnl_pct: 0.92, exit_reason: "take_profit" },
  { sequence_no: 8, side: "SHORT", entry_time: "2026-01-07T01:20:00Z", exit_time: "2026-01-07T03:20:00Z", entry_price: 69_120.7, exit_price: 68_110.3, fee_paid: 0.05, slippage_cost: 0.03, sl_price: 69_620.0, tp_price: 68_120.0, pnl: 0.86, pnl_pct: 0.86, exit_reason: "take_profit" },
  { sequence_no: 9, side: "LONG", entry_time: "2026-01-07T06:55:00Z", exit_time: "2026-01-07T08:55:00Z", entry_price: 68_520.3, exit_price: 68_020.0, fee_paid: 0.05, slippage_cost: 0.03, sl_price: 68_020.0, tp_price: 69_520.0, pnl: -0.55, pnl_pct: -0.55, exit_reason: "stop_loss" },
  { sequence_no: 10, side: "SHORT", entry_time: "2026-01-07T11:10:00Z", exit_time: "2026-01-07T13:10:00Z", entry_price: 69_010.2, exit_price: 68_005.5, fee_paid: 0.05, slippage_cost: 0.03, sl_price: 69_510.0, tp_price: 68_010.0, pnl: 0.95, pnl_pct: 0.95, exit_reason: "take_profit" },
];

const DAY_MS = 86_400_000;

export const MOCK_TRADES: Trade[] = Array.from({ length: MOCK_KPIS.totalTrades }, (_, index) => {
  const seed = SEED_ROWS[index % SEED_ROWS.length];
  const dayShift = Math.floor(index / SEED_ROWS.length) * 3 * DAY_MS;
  return {
    ...seed,
    id: `mock-trade-${index + 1}`,
    sequence_no: index + 1,
    quantity: 0.014,
    entry_time: new Date(Date.parse(seed.entry_time) + dayShift).toISOString(),
    exit_time: new Date(Date.parse(seed.exit_time) + dayShift).toISOString(),
    signal_t: new Date(Date.parse(seed.entry_time) + dayShift).toISOString(),
  };
});

export const PROFIT_FORMULA: Array<{ icon: "dollar" | "percent" | "sliders"; tone: "green" | "brand" | "amber"; label: string; caption: string; operator: "−" | "=" | null }> = [
  { icon: "dollar", tone: "green", label: "Gross Profit", caption: "Tổng lãi/lỗ trước phí", operator: "−" },
  { icon: "percent", tone: "brand", label: "Fee", caption: "Phí giao dịch", operator: "−" },
  { icon: "sliders", tone: "amber", label: "Slippage", caption: "Trượt giá", operator: "=" },
  { icon: "dollar", tone: "green", label: "Net Profit", caption: "Lợi nhuận ròng thực tế", operator: null },
];

export const ASSUMPTIONS = [
  "Hỗ trợ cả LONG và SHORT",
  "Xử lý SL/TP theo giá thực tế (OHLC)",
  "Kết quả có thể tái lập (reproducible)",
];
