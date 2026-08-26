import type { NewsItem } from "./api";

/* Reference-exact content for the News Crawler panels that have no backend
   contract: LLM extraction stages, self-healing telemetry, event-type mix and
   source-coverage counters. Real news and the sentiment aggregate come from the
   API — only these documentation panels are fixed. */

export type SourceMode = "website" | "rss" | "html";

export const SOURCE_MODES: Array<{ value: SourceMode; label: string; icon: "globe" | "rss" | "code"; supported: boolean }> = [
  { value: "website", label: "Website", icon: "globe", supported: true },
  { value: "rss", label: "RSS", icon: "rss", supported: true },
  { value: "html", label: "HTML", icon: "code", supported: true },
];

export const REFRESH_OPTIONS = [1, 2, 3, 4, 5] as const;

export const ASSET_PRESETS = ["BTC, ETH, SOL", "BTC", "ETH", "SOL"] as const;

export const EXTRACTION_STAGES = [
  { label: "HTML thô", detail: "Thu thập nội dung HTML từ nguồn" },
  { label: "LLM hiểu tag HTML", detail: "LLM đọc & hiểu cấu trúc, nhận diện vùng nội dung" },
  { label: "Sinh Extraction Template", detail: "Tạo template trích xuất được đề xuất" },
  { label: "Lưu version template", detail: "Lưu lại và quản lý các phiên bản" },
];

export const SELF_HEALING_STAGES = [
  { label: "Validate kết quả", detail: "Kiểm tra chất lượng kết quả trích xuất" },
  { label: "Lỗi cao?", detail: "Nếu lỗi > ngưỡng (VD: 10%)" },
  { label: "LLM sửa template", detail: "LLM phân tích lỗi & đề xuất template mới" },
  { label: "Lưu version mới", detail: "Lưu và chuyển sang version mới" },
];

export const RAW_HTML_SAMPLE = `<html>
 <head>...</head>
 <body>
  <div class="article">
   <h1>BlackRock's
   Bitcoin ETF...</h1>
   <p>Dòng tiền vào
   các quỹ ETF...</p>
  </div>
 </body>
</html>`;

export const FIELD_MAP_SAMPLE: Array<[string, string]> = [
  ["title", "<h1>"],
  ["summary", "<p class=\"...\">"],
  ["source", "<span class=\"...\">"],
  ["time", "<time>"],
  ["asset", "context"],
];

export const TEMPLATE_JSON_SAMPLE = `{
  "title": "h1.article-title",
  "summary": "p.summary",
  "source": "span.source",
  "time": "time",
  "asset": "meta[content=\\"asset\\"]"
}`;

export const TEMPLATE_VERSIONS = [
  { version: "v1.4.2", stamp: "10:32 · 18/05/2025", current: true },
  { version: "v1.4.1", stamp: "09:10 · 17/05/2025", current: false },
  { version: "v1.4.0", stamp: "16:22 · 16/05/2025", current: false },
];

export const EXTRACTION_METRICS = {
  templateVersion: "v1.4.2",
  confidence: 0.92,
  fields: 5,
  score: 0.92,
  emptyFieldsPct: 8.7,
  malformedPct: 3.2,
  averageConfidence: 0.76,
  totalErrorPct: 11.9,
  threshold: 10,
};

export const REPAIR_PROPOSAL = {
  version: "v1.4.3 (draft)",
  errorBefore: 11.9,
  errorAfter: 4.1,
  expectedConfidence: 0.93,
  savedVersion: "v1.4.3",
  savedAt: "10:45 · 18/05/2025",
};

export const EVENT_TYPES = [
  { label: "ETF / Fund Flow", pct: 28 },
  { label: "Protocol Upgrade", pct: 22 },
  { label: "Regulation", pct: 15 },
  { label: "Partnership", pct: 12 },
  { label: "Market Trend", pct: 23 },
];

export const ANALYSIS_METRICS = {
  confidenceScore: 0.78,
  analyzedCount24h: 1_248,
  sourceCoveragePct: 92,
  activeSources: 23,
  totalSources: 25,
  updatedAt: "10:45",
};

export const STRATEGY_LINK = {
  left: { title: "News Sentiment", caption: "(Real-time)" },
  right: { title: "Strategy Engine", caption: "(Điều kiện vào lệnh)" },
  bottom: { title: "NewsSentimentStrategy", caption: "(Chiến lược mẫu)" },
  connector: "API / Stream",
  alternate: "Hoặc sử dụng trực tiếp",
};

const ASSET_ICON_TONE: Record<string, "amber" | "violet" | "green"> = {
  BTC: "amber",
  ETH: "violet",
  SOL: "green",
};

export function assetTone(coin: string): "amber" | "violet" | "green" {
  return ASSET_ICON_TONE[coin.toUpperCase()] ?? "violet";
}

/* Six stories matching the reference feed, with the sentiment field left null
   where the reference shows no label — null is how the API represents "the AI
   service has not analyzed this yet". */
export const NEWS_MOCK: NewsItem[] = [
  {
    id: "mock-news-1",
    title: "BlackRock's Bitcoin ETF sees $200M inflows as BTC holds above $69K",
    url: "https://www.coindesk.com/",
    published_at: "2026-08-26T10:40:00Z",
    source: { key: "coindesk", display_name: "CoinDesk" },
    related_coins: ["BTC"],
    sentiment: { label: "POSITIVE", score: 0.86, model: "sentiment-v1", model_version: "2026-08-01", analyzed_at: "2026-08-26T10:41:00Z" },
  },
  {
    id: "mock-news-2",
    title: "Ethereum Pectra testnet upgrade live, developers eye final launch",
    url: "https://www.theblock.co/",
    published_at: "2026-08-26T10:32:00Z",
    source: { key: "theblock", display_name: "The Block" },
    related_coins: ["ETH"],
    sentiment: { label: "POSITIVE", score: 0.74, model: "sentiment-v1", model_version: "2026-08-01", analyzed_at: "2026-08-26T10:33:00Z" },
  },
  {
    id: "mock-news-3",
    title: "Solana network fees drop 60% amid lower memecoin activity",
    url: "https://decrypt.co/",
    published_at: "2026-08-26T10:28:00Z",
    source: { key: "decrypt", display_name: "Decrypt" },
    related_coins: ["SOL"],
    sentiment: { label: "NEUTRAL", score: 0.52, model: "sentiment-v1", model_version: "2026-08-01", analyzed_at: "2026-08-26T10:29:00Z" },
  },
  {
    id: "mock-news-4",
    title: "CME Bitcoin futures open interest hits new all-time high",
    url: "https://cointelegraph.com/",
    published_at: "2026-08-26T10:20:00Z",
    source: { key: "cointelegraph", display_name: "Cointelegraph" },
    related_coins: ["BTC"],
    sentiment: { label: "POSITIVE", score: 0.81, model: "sentiment-v1", model_version: "2026-08-01", analyzed_at: "2026-08-26T10:21:00Z" },
  },
  {
    id: "mock-news-5",
    title: "Vitalik outlines roadmap for Ethereum scaling post-Pectra",
    url: "https://www.bankless.com/",
    published_at: "2026-08-26T10:15:00Z",
    source: { key: "bankless", display_name: "Bankless" },
    related_coins: ["ETH"],
    sentiment: null,
  },
  {
    id: "mock-news-6",
    title: "Solana mobile Chapter 2 pre-order starts, token BONK spikes",
    url: "https://thedefiant.io/",
    published_at: "2026-08-26T10:05:00Z",
    source: { key: "thedefiant", display_name: "The Defiant" },
    related_coins: ["SOL"],
    sentiment: { label: "POSITIVE", score: 0.69, model: "sentiment-v1", model_version: "2026-08-01", analyzed_at: "2026-08-26T10:06:00Z" },
  },
];

export const NEWS_SUMMARY_MOCK: Record<string, string> = {
  "mock-news-1": "Dòng tiền vào các quỹ ETF Bitcoin giao ngay tại Mỹ tiếp tục tăng, dẫn dắt bởi BlackRock IBIT…",
  "mock-news-2": "Bản nâng cấp Pectra trên testnet Sepolia đã hoạt động ổn định, mục tiêu triển khai mainnet vào cuối tháng 5…",
  "mock-news-3": "Phí giao dịch trên Solana giảm mạnh khi hoạt động memecoin chậm lại, giúp cải thiện trải nghiệm người dùng…",
  "mock-news-4": "OI hợp đồng tương lai Bitcoin trên CME đạt mức cao kỷ lục, cho thấy nhu cầu từ tổ chức tăng mạnh…",
  "mock-news-5": "Vitalik Buterin chia sẻ định hướng mở rộng quy mô Ethereum sau khi hoàn tất bản nâng cấp Pectra…",
  "mock-news-6": "Đơn đặt trước Solana Mobile Chapter 2 đã bắt đầu, BONK tăng mạnh theo kỳ vọng cộng đồng…",
};

/* The aggregate endpoint returns label counts; the reference shows a 58/27/15
   split. Percentages are always computed from counts, never hardcoded — this
   is only the fallback when no aggregate has loaded. */
export const AGGREGATE_MOCK = { positive: 58, neutral: 27, negative: 15 };
