/* Reference-exact defaults for the Strategy Engine authoring screen. Live
   authoring rows come from the owner's draft list; fixtures are only for the
   explicit UI-reference mode. */

export const SAMPLE_PROMPT =
  "Khi RSI dưới 30 và giá nằm dưới Bollinger Lower Band thì LONG. Stop loss 2%, take profit 4%.";

export const SAMPLE_URL = "https://www.tradingview.com/script/abc123-example/";

export const URL_HINT = "Hỗ trợ: TradingView, Blogger, Medium, GitHub Gist, Docs…";

export const PARSED_BLOCKS: Array<{
  icon: "target" | "shield" | "clock" | "coins";
  tone: "green" | "red" | "violet" | "brand";
  title: string;
  lines: string[];
}> = [
  {
    icon: "target",
    tone: "green",
    title: "Điều kiện LONG",
    lines: ["RSI (14) < 30", "Giá đóng cửa nằm dưới Bollinger Lower Band (20, 2)"],
  },
  {
    icon: "target",
    tone: "red",
    title: "Điều kiện SHORT",
    lines: ["RSI (14) > 70", "Giá đóng cửa nằm trên Bollinger Upper Band (20, 2)"],
  },
  {
    icon: "shield",
    tone: "violet",
    title: "Quản trị rủi ro",
    lines: ["Stop Loss: 2%", "Take Profit: 4%"],
  },
  {
    icon: "clock",
    tone: "brand",
    title: "Khung thời gian",
    lines: ["1h (mặc định)"],
  },
  {
    icon: "coins",
    tone: "brand",
    title: "Áp dụng cho cặp",
    lines: ["Tất cả cặp USDT (Có thể tùy chọn)"],
  },
];

export const DEFINITION_JSON = `{
  "name": "RSI_BB_LB_LONG_SL2_TP4",
  "version": "1.0.0",
  "description": "LONG khi RSI < 30 và giá dưới Bollinger Lower Band. SL 2%, TP 4%.",
  "indicators": [
    { "name": "RSI", "period": 14 },
    { "name": "BollingerBands", "period": 20, "stdDev": 2 }
  ],
  "conditions": {
    "long": [
      { "indicator": "RSI", "operator": "<", "value": 30 },
      { "indicator": "Close", "position": "<", "indicatorRef": "BB_Lower" }
    ],
    "short": [
      { "indicator": "RSI", "operator": ">", "value": 70 },
      { "indicator": "Close", "position": ">", "indicatorRef": "BB_Upper" }
    ]
  },
  "riskManagement": {
    "stopLoss": { "type": "percent", "value": 2 },
    "takeProfit": { "type": "percent", "value": 4 }
  },
  "timeframe": "1h",
  "applicability": {
    "pairs": "USDT_ALL",
    "market": "spot"
  }
}`;

export const VALIDATION_CHECKS: Array<{ icon: "shield" | "scale" | "chart"; title: string; detail: string }> = [
  { icon: "shield", title: "Thiếu trường bắt buộc", detail: "Không có" },
  { icon: "scale", title: "Kiểm tra logic", detail: "Logic hợp lệ" },
  { icon: "chart", title: "Chỉ báo hỗ trợ", detail: "Tất cả chỉ báo được hỗ trợ" },
];

export const SAVE_FORM = {
  name: "RSI_BB_LB_LONG_SL2_TP4",
  version: "1.0.0",
  tags: ["RSI", "Bollinger", "Mean Reversion", "Long"],
  source: "USER_PROMPT",
};

export const SOURCE_OPTIONS = ["USER_PROMPT", "WEB_IMPORT", "MANUAL_JSON"] as const;

export type ImportRow = {
  draftId?: string;
  strategyId: string | null;
  name: string;
  source: "USER_PROMPT" | "WEB_IMPORT" | "MANUAL_DSL";
  createdAt: string;
  version: string;
  tags: string[];
  status: "approved" | "processing" | "review" | "rejected" | "failed";
};

export type RecentImportDraft = {
  draft_id?: string;
  source_type: "text" | "approved_url" | "dsl";
  status: string;
  name_hint: string | null;
  current_revision: number;
  created_at: string;
  strategy_spec: {
    strategy_id: string;
    display_name: string;
    indicators: Array<Record<string, unknown>>;
  } | null;
};

export const IMPORT_ROWS: ImportRow[] = [
  {
    strategyId: null,
    name: "RSI_BB_LB_LONG_SL2_TP4",
    source: "USER_PROMPT",
    createdAt: "20/05/2025 10:42",
    version: "1.0.0",
    tags: ["RSI", "BB", "Long"],
    status: "approved",
  },
  {
    strategyId: null,
    name: "MACD_Cross_TrendFollow",
    source: "WEB_IMPORT",
    createdAt: "19/05/2025 16:30",
    version: "1.2.1",
    tags: ["MACD", "Trend", "Swing"],
    status: "approved",
  },
];

export function recentImportRows(drafts: RecentImportDraft[], useReferenceFixtures = false): ImportRow[] {
  if (drafts.length === 0) return useReferenceFixtures ? IMPORT_ROWS : [];
  return drafts.map((draft) => ({
    draftId: draft.draft_id,
    strategyId: draft.strategy_spec?.strategy_id ?? null,
    name: draft.strategy_spec?.display_name ?? draft.name_hint ?? "Strategy draft",
    source: draft.source_type === "approved_url" ? "WEB_IMPORT" : draft.source_type === "dsl" ? "MANUAL_DSL" : "USER_PROMPT",
    createdAt: formatImportedAt(draft.created_at),
    version: `v${draft.current_revision}`,
    tags: tagsForDraft(draft),
    status: draft.status === "APPROVED"
      ? "approved"
      : draft.status === "REVIEW_REQUIRED"
        ? "review"
        : draft.status === "REJECTED"
          ? "rejected"
          : draft.status === "FAILED"
            ? "failed"
            : "processing",
  }));
}

function tagsForDraft(draft: RecentImportDraft): string[] {
  const aliases: Record<string, string> = { bollinger: "BB", support_resistance: "S/R" };
  const tags = (draft.strategy_spec?.indicators ?? [])
    .map((indicator) => typeof indicator.kind === "string" ? indicator.kind : "")
    .filter(Boolean)
    .map((kind) => aliases[kind] ?? kind.toUpperCase());
  return [...new Set(tags)].slice(0, 3);
}

function formatImportedAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("vi-VN", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(date);
}

export const PROMPT_LIMIT = 1000;
