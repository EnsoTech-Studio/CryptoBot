import type { LeaderboardEntry } from "./api";
import type { Strategy } from "./api";
import type { DiscoveryMethod } from "./discovery";

/* Reference-exact values for the parts of the Discovery screen that have no
   backend contract yet (aggregate live signal, SMC/Wyckoff catalog entries,
   iteration counters). Real API data replaces these the moment it arrives —
   see DiscoveryScreen, which prefers `leaderboard` from the workspace and only
   falls back here. */

export type CatalogEntry = {
  /* null = shown in the reference but not in the strategy registry, so it can
     be displayed and selected for layout parity but never submitted. */
  strategyId: string | null;
  label: string;
  description: string;
  icon: "activity" | "chart" | "target" | "candles" | "bar-chart" | "scale";
  tone: "violet" | "brand" | "green" | "amber" | "neutral";
};

export const STRATEGIES_MOCK: Strategy[] = [
  ["rsi", "momentum", "RSI"],
  ["ma_cross", "trend", "MA Cross (SMA)"],
  ["bollinger", "volatility", "Bollinger Bands"],
  ["support_resistance", "structure", "Support / Resistance"],
  ["smc", "structure", "Smart Money Concepts"],
  ["wyckoff", "structure", "Wyckoff"],
].map(([strategy_id, family, display_name]) => ({
  strategy_id,
  version: "1.0.0",
  family,
  display_name,
  description: `${display_name} mock strategy`,
  parameters_schema: {},
  overlay_types: [],
  warm_up_candles: 20,
  is_composite: false,
  code_fingerprint: `mock-${strategy_id}`,
}));

export const CATALOG_MOCK: CatalogEntry[] = [
  { strategyId: "rsi", label: "RSI", description: "Đo động lượng và xác định vùng quá mua / quá bán.", icon: "activity", tone: "violet" },
  { strategyId: "ma_cross", label: "MA", description: "Theo xu hướng bằng đường trung bình động.", icon: "chart", tone: "brand" },
  { strategyId: "bollinger", label: "Bollinger Bands", description: "Đo độ biến động và phát hiện phá vỡ dải.", icon: "target", tone: "green" },
  { strategyId: "support_resistance", label: "Support / Resistance", description: "Xác định vùng hỗ trợ và kháng cự quan trọng.", icon: "scale", tone: "amber" },
  { strategyId: "smc", label: "SMC", description: "Phân tích cấu trúc thị trường theo Smart Money Concepts.", icon: "candles", tone: "neutral" },
  { strategyId: "wyckoff", label: "Wyckoff", description: "Nhận diện giai đoạn tích lũy và phân phối.", icon: "bar-chart", tone: "violet" },
];

export const QUICK_COMBOS: Array<{ label: string; ids: string[] }> = [
  { label: "MA + RSI", ids: ["ma_cross", "rsi"] },
  { label: "RSI + Bollinger", ids: ["rsi", "bollinger"] },
  { label: "MA + RSI + S/R", ids: ["ma_cross", "rsi", "support_resistance"] },
];

export const LOOP_STEPS: Array<{ icon: "wand" | "candles" | "chart" | "bar-chart" | "trophy"; label: string; detail: string }> = [
  { icon: "wand", label: "Generate", detail: "Tạo biến thể strategy" },
  { icon: "candles", label: "Backtest", detail: "Kiểm tra hiệu suất trên lịch sử" },
  { icon: "chart", label: "Evaluate", detail: "Đánh giá theo chỉ số" },
  { icon: "bar-chart", label: "Rank", detail: "Xếp hạng các strategy" },
  { icon: "trophy", label: "Leaderboard", detail: "Hiển thị top strategy" },
];

export type MockSignal = { long: number; hold: number; short: number; threshold: number };

export const AGGREGATE_SIGNAL_MOCK: MockSignal = { long: 0.62, hold: -0.08, short: -0.54, threshold: 0.3 };

export type MockLeaderRow = { rank: number; parts: string[]; profitUsdt: number; winratePct: number };

export const LEADERBOARD_MOCK: MockLeaderRow[] = [
  { rank: 1, parts: ["MA", "RSI", "S/R"], profitUsdt: 2_342.18, winratePct: 68.21 },
  { rank: 2, parts: ["RSI", "Bollinger"], profitUsdt: 1_864.76, winratePct: 64.73 },
  { rank: 3, parts: ["MA", "RSI"], profitUsdt: 1_512.33, winratePct: 62.19 },
  { rank: 4, parts: ["MA", "RSI", "Bollinger"], profitUsdt: 1_102.47, winratePct: 59.48 },
  { rank: 5, parts: ["S/R", "Bollinger"], profitUsdt: 987.15, winratePct: 57.63 },
];

export const PROGRESS_MOCK = {
  iteration: 47,
  maxIterations: 500,
  tested: 2_350,
  best: { parts: ["MA", "RSI", "S/R"], profitUsdt: 2_342.18, winratePct: 68.21 },
  method: "random_search" as DiscoveryMethod,
};

/* A real leaderboard row carries a candidate hash, not a strategy-part list.
   Split the composite id back into display chips so real and mock rows render
   through the same cell. */
export function entryParts(entry: LeaderboardEntry): string[] {
  const children = entry.strategy_id === "composite" ? [] : [entry.strategy_id];
  return children.length > 0 ? children : [entry.strategy_id];
}
