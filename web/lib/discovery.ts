import type { MarketSelection } from "./market";

/* The discovery draft is the *whole* search request the user can see on screen.
   Before this existed, api.startSearch() shipped a hardcoded payload and the
   visible controls were decoration. Plan 03 §4 requires the submitted request
   and the visible draft to be the same object. */

export type DiscoveryMethod = "grid" | "random_search" | "domain_guided";

/* Genetic appears in the reference. There is no backend generator for it
   (server/internal/httpapi/contracts.go rejects it), so it is listed as a
   disabled option rather than silently mapped to something else. */
export type DiscoveryMethodOption = DiscoveryMethod | "genetic";

export type CombinationPolicy = "weighted_vote" | "majority_vote";

export type DiscoveryDraft = {
  selectedStrategyIds: string[];
  weights: Record<string, number>;
  policy: CombinationPolicy;
  method: DiscoveryMethod;
  maxCandidates: number;
  maxDurationSec: number;
  maxNonImproving: number;
  seed: number;
  market: MarketSelection;
  timeframe: string;
};

export const MIN_COMBINED = 2;
export const MAX_COMBINED = 5;

/* Bounds mirror the API validators exactly: contracts.go validateSearchStopConditions
   and app/schemas.py SearchStopConditions. Keeping them here means the UI rejects
   a bad draft before the network call instead of rendering a 422. */
export const STOP_LIMITS = {
  maxCandidates: { min: 1, max: 500 },
  maxDurationSec: { min: 1, max: 86_400 },
  maxNonImproving: { min: 1, max: 500 },
} as const;

export const DISCOVERY_METHODS: Array<{
  value: DiscoveryMethodOption;
  label: string;
  description: string;
  icon: "dice" | "target" | "dna" | "sliders";
  supported: boolean;
}> = [
  { value: "grid", label: "Grid Search", description: "Quét toàn bộ không gian tham số theo thứ tự xác định.", icon: "sliders", supported: true },
  { value: "random_search", label: "Random Search", description: "Sinh ngẫu nhiên các biến thể theo seed.", icon: "dice", supported: true },
  { value: "domain_guided", label: "Domain-guided Search", description: "Tìm kiếm dựa trên kiến thức và ràng buộc.", icon: "target", supported: true },
  { value: "genetic", label: "Genetic Search", description: "Tiến hóa qua chọn lọc và lai ghép.", icon: "dna", supported: false },
];

/* Short labels for chips. The registry display_name ("MA Cross (SMA)") is too
   long for a leaderboard cell, and the reference uses these abbreviations. */
const SHORT_LABELS: Record<string, string> = {
  ma_cross: "MA",
  ema_cross: "EMA",
  rsi: "RSI",
  bollinger: "Bollinger",
  macd: "MACD",
  support_resistance: "S/R",
  news_sentiment: "Sentiment",
  composite: "Composite",
};

export function shortLabel(strategyId: string): string {
  return SHORT_LABELS[strategyId] ?? strategyId;
}

export type FamilyTone = "brand" | "violet" | "green" | "amber" | "neutral";

export function familyTone(family?: string | null): FamilyTone {
  switch (family) {
    case "trend":
      return "brand";
    case "momentum":
      return "violet";
    case "volatility":
      return "green";
    case "structure":
      return "amber";
    case "information":
      return "violet";
    default:
      return "neutral";
  }
}

export function createDraft(market: MarketSelection, timeframe: string): DiscoveryDraft {
  return {
    selectedStrategyIds: [],
    weights: {},
    policy: "weighted_vote",
    method: "domain_guided",
    maxCandidates: 24,
    maxDurationSec: 900,
    maxNonImproving: 8,
    seed: 42,
    market,
    timeframe,
  };
}

/* Weights are held as raw numbers while the user drags, then normalized on
   submit. Six decimal places matches the tolerance the composite combiner and
   score policy validators use (1e-9 on a sum of 1.0). */
export function normalizeWeights(
  strategyIds: string[],
  weights: Record<string, number>,
): Record<string, number> {
  if (strategyIds.length === 0) return {};
  const raw = strategyIds.map((id) => Math.max(0, weights[id] ?? 0));
  const total = raw.reduce((sum, value) => sum + value, 0);
  const even = 1 / strategyIds.length;
  const shares = total > 0 ? raw.map((value) => value / total) : raw.map(() => even);
  const rounded = shares.map((value) => Number(value.toFixed(6)));
  /* Rounding six places can leave the sum a hair off 1.0. Push the residue into
     the largest share so the submitted weights sum to exactly 1.0. */
  const drift = Number((1 - rounded.reduce((sum, value) => sum + value, 0)).toFixed(6));
  if (drift !== 0) {
    const largest = rounded.indexOf(Math.max(...rounded));
    rounded[largest] = Number((rounded[largest] + drift).toFixed(6));
  }
  return Object.fromEntries(strategyIds.map((id, index) => [id, rounded[index]]));
}

export function draftIssues(draft: DiscoveryDraft): string[] {
  const issues: string[] = [];
  if (draft.selectedStrategyIds.length < MIN_COMBINED) {
    issues.push(`Chọn ít nhất ${MIN_COMBINED} strategy để tạo strategy kết hợp.`);
  }
  if (draft.selectedStrategyIds.length > MAX_COMBINED) {
    issues.push(`Chỉ kết hợp tối đa ${MAX_COMBINED} strategy.`);
  }
  if (draft.policy === "weighted_vote") {
    const total = draft.selectedStrategyIds.reduce((sum, id) => sum + Math.max(0, draft.weights[id] ?? 0), 0);
    if (total <= 0) issues.push("Tổng trọng số phải lớn hơn 0.");
  }
  const bounds: Array<[number, { min: number; max: number }, string]> = [
    [draft.maxCandidates, STOP_LIMITS.maxCandidates, "Số candidate tối đa"],
    [draft.maxDurationSec, STOP_LIMITS.maxDurationSec, "Thời lượng tối đa (giây)"],
    [draft.maxNonImproving, STOP_LIMITS.maxNonImproving, "Số vòng không cải thiện"],
  ];
  bounds.forEach(([value, limit, name]) => {
    if (!Number.isInteger(value) || value < limit.min || value > limit.max) {
      issues.push(`${name} phải là số nguyên trong [${limit.min}, ${limit.max}].`);
    }
  });
  return issues;
}
