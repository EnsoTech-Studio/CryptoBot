import type { Candle, ExecutionMarker, MarketDataset, Trade } from "./api";

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

export const MOCK_DATASETS: MarketDataset[] = [{
  id: "mock-dataset-btc-5m",
  dataset_version: "reference:BTCUSDT:5m:v1",
  market: { provider: "binance_usdm", symbol: "BTCUSDT", timeframe: "5m" },
  range_from: "2025-05-01T00:00:00Z",
  range_to: "2025-05-16T00:00:00Z",
  revision_no: 1,
  candle_count: 4_320,
  content_hash: "reference-candle-hash",
  bbo_content_hash: "reference-bbo-hash",
}];

/* Ten rows matching the reference table, then repeated with shifted timestamps
   so pagination has something to page through (178 total, as the KPI claims). */
const SEED_ROWS: Array<Omit<Trade, "id" | "signal_t" | "quantity" | "symbol" | "quote_currency" | "entry_notional" | "exit_notional" | "spread_cost" | "gross_pnl" | "net_pnl">> = [
  { sequence_no: 1, side: "LONG", entry_time: "2025-05-01T06:15:00Z", exit_time: "2025-05-01T08:15:00Z", entry_price: 68_120.5, exit_price: 69_120.0, fee_paid: 0.05, slippage_cost: 0.03, sl_price: 67_620.0, tp_price: 69_120.0, pnl: 0.83, pnl_pct: 0.83, exit_reason: "take_profit" },
  { sequence_no: 2, side: "SHORT", entry_time: "2025-05-01T09:40:00Z", exit_time: "2025-05-01T11:40:00Z", entry_price: 69_450.2, exit_price: 68_430.1, fee_paid: 0.05, slippage_cost: 0.03, sl_price: 69_950.0, tp_price: 68_450.0, pnl: 0.87, pnl_pct: 0.87, exit_reason: "take_profit" },
  { sequence_no: 3, side: "LONG", entry_time: "2025-05-01T12:25:00Z", exit_time: "2025-05-01T14:25:00Z", entry_price: 68_600.1, exit_price: 67_980.0, fee_paid: 0.05, slippage_cost: 0.03, sl_price: 68_100.0, tp_price: 69_600.0, pnl: -0.67, pnl_pct: -0.67, exit_reason: "stop_loss" },
  { sequence_no: 4, side: "SHORT", entry_time: "2025-05-01T16:10:00Z", exit_time: "2025-05-01T18:10:00Z", entry_price: 69_320.3, exit_price: 68_310.4, fee_paid: 0.05, slippage_cost: 0.03, sl_price: 69_820.0, tp_price: 68_320.0, pnl: 0.9, pnl_pct: 0.9, exit_reason: "take_profit" },
  { sequence_no: 5, side: "LONG", entry_time: "2025-05-02T03:50:00Z", exit_time: "2025-05-02T05:50:00Z", entry_price: 68_800.4, exit_price: 69_800.0, fee_paid: 0.05, slippage_cost: 0.03, sl_price: 68_300.0, tp_price: 69_800.0, pnl: 0.95, pnl_pct: 0.95, exit_reason: "take_profit" },
  { sequence_no: 6, side: "SHORT", entry_time: "2025-05-02T08:35:00Z", exit_time: "2025-05-02T10:35:00Z", entry_price: 69_900.8, exit_price: 70_430.0, fee_paid: 0.05, slippage_cost: 0.03, sl_price: 70_400.0, tp_price: 68_900.0, pnl: -0.58, pnl_pct: -0.58, exit_reason: "stop_loss" },
  { sequence_no: 7, side: "LONG", entry_time: "2025-05-02T13:05:00Z", exit_time: "2025-05-02T15:05:00Z", entry_price: 68_950.6, exit_price: 69_930.2, fee_paid: 0.05, slippage_cost: 0.03, sl_price: 68_450.0, tp_price: 69_950.0, pnl: 0.92, pnl_pct: 0.92, exit_reason: "take_profit" },
  { sequence_no: 8, side: "SHORT", entry_time: "2025-05-03T01:20:00Z", exit_time: "2025-05-03T03:20:00Z", entry_price: 69_120.7, exit_price: 68_110.3, fee_paid: 0.05, slippage_cost: 0.03, sl_price: 69_620.0, tp_price: 68_120.0, pnl: 0.86, pnl_pct: 0.86, exit_reason: "take_profit" },
  { sequence_no: 9, side: "LONG", entry_time: "2025-05-03T06:55:00Z", exit_time: "2025-05-03T08:55:00Z", entry_price: 68_520.3, exit_price: 68_020.0, fee_paid: 0.05, slippage_cost: 0.03, sl_price: 68_020.0, tp_price: 69_520.0, pnl: -0.55, pnl_pct: -0.55, exit_reason: "stop_loss" },
  { sequence_no: 10, side: "SHORT", entry_time: "2025-05-03T11:10:00Z", exit_time: "2025-05-03T13:10:00Z", entry_price: 69_010.2, exit_price: 68_005.5, fee_paid: 0.05, slippage_cost: 0.03, sl_price: 69_510.0, tp_price: 68_010.0, pnl: 0.95, pnl_pct: 0.95, exit_reason: "take_profit" },
];

const DAY_MS = 86_400_000;

export const MOCK_TRADES: Trade[] = Array.from({ length: MOCK_KPIS.totalTrades }, (_, index) => {
  const seed = SEED_ROWS[index % SEED_ROWS.length];
  const dayShift = Math.floor(index / SEED_ROWS.length) * 3 * DAY_MS;
  return {
    ...seed,
    id: `mock-trade-${index + 1}`,
    sequence_no: index + 1,
    symbol: "BTCUSDT",
    quote_currency: "USDT",
    quantity: 0.014,
    entry_notional: seed.entry_price * 0.014,
    exit_notional: seed.exit_price * 0.014,
    spread_cost: 0,
    gross_pnl: seed.pnl + seed.fee_paid + seed.slippage_cost,
    net_pnl: seed.pnl,
    entry_time: new Date(Date.parse(seed.entry_time) + dayShift).toISOString(),
    exit_time: new Date(Date.parse(seed.exit_time) + dayShift).toISOString(),
    signal_t: new Date(Date.parse(seed.entry_time) + dayShift).toISOString(),
  };
});

/* Mock chart markers deliberately point at the same ledger rows as live
   execution markers, so selection is demonstrable without a completed run. */
export function mockExecutionMarkers(candles: Candle[]): ExecutionMarker[] {
  const longEntry = candles[70];
  const shortEntry = candles[116];
  const exit = candles[166];
  if (!longEntry || !shortEntry || !exit) return [];
  return [
    { sequence_no: 1, t: longEntry.open_time, line_until: candles[135]?.open_time, overlay_type: "long_entry", price: longEntry.close },
    { sequence_no: 1, t: longEntry.open_time, line_until: candles[135]?.open_time, overlay_type: "stop_loss", price: 67_800 },
    { sequence_no: 2, t: shortEntry.open_time, line_until: candles[166]?.open_time, overlay_type: "short_entry", price: shortEntry.close },
    { sequence_no: 2, t: shortEntry.open_time, line_until: candles[166]?.open_time, overlay_type: "take_profit", price: 70_200 },
    { sequence_no: 2, t: exit.open_time, overlay_type: "exit", price: exit.close, exit_reason: "take_profit" },
  ];
}

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
