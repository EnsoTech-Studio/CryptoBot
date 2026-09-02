import type {
  Candle,
  MarketPair,
  MarketSelection,
  OverlayMarker,
  OverlaySeries,
} from "./api";
import { PANEL_BOOTSTRAP_CANDLE_LIMIT } from "./market";

export type DisplayTick = {
  id: string;
  occurredAt: string;
  price: number;
  quantity: number;
  side: "buy" | "sell" | "bbo";
};

export const MOCK_MARKET_PAIRS: MarketPair[] = [
  {
    provider: "binance_usdm",
    symbol: "BTCUSDT",
    base_asset: "BTC",
    quote_asset: "USDT",
    timeframes: ["1s", "1m", "5m", "15m", "1h", "4h", "1d"],
  },
  {
    provider: "binance_usdm",
    symbol: "ETHUSDT",
    base_asset: "ETH",
    quote_asset: "USDT",
    timeframes: ["1s", "1m", "5m", "15m", "1h", "4h", "1d"],
  },
];

const timeframeMinutes: Record<string, number> = {
  "1s": 1 / 60,
  "1m": 1,
  "5m": 5,
  "15m": 15,
  "1h": 60,
  "4h": 240,
  "1d": 1_440,
};

const referenceClose: Record<string, number> = {
  "1s": 69_342.18,
  "1m": 69_342.18,
  "5m": 69_342.18,
  "15m": 69_342.18,
  "1h": 69_342.18,
  "4h": 69_214.82,
  "1d": 69_214.82,
};

const referenceMovingAverage: Record<string, number> = {
  "1s": 69_342.18,
  "1m": 69_315.45,
  "5m": 69_182.73,
  "15m": 68_912.35,
  "1h": 68_215.66,
};

export function createMockPanelData(
  market: MarketSelection,
  timeframe: string,
  limit = PANEL_BOOTSTRAP_CANDLE_LIMIT,
): { candles: Candle[]; series: OverlaySeries[]; markers: OverlayMarker[] } {
  const count = Math.max(40, Math.min(limit, 1_000));
  const minutes = timeframeMinutes[timeframe] ?? 1;
  const symbol = market.symbol.toUpperCase();
  const isBitcoin = symbol.startsWith("BTC");
  const target = isBitcoin ? (referenceClose[timeframe] ?? 69_342.18) : 3_782.46;
  const displayRangeByTimeframe: Record<string, number> = {
    "1s": 240,
    "1m": 470,
    "5m": 880,
    "15m": 3_350,
    "1h": 8_200,
    "4h": 10_400,
    "1d": 18_000,
  };
  const marketScale = isBitcoin ? 1 : 0.055;
  const displayRange = (displayRangeByTimeframe[timeframe] ?? 520) * marketScale;
  const trendRange = displayRange * 2.2;
  const waveSize = displayRange * 0.18;
  const stepMs = minutes * 60_000;
  const anchor = Date.parse(timeframe === "1s"
    ? "2025-05-16T10:45:59.000Z"
    : timeframe === "1m"
    ? "2025-05-16T10:45:00.000Z"
    : timeframe === "5m"
      ? "2025-05-16T10:00:00.000Z"
      : "2025-05-16T09:00:00.000Z");
  const raw = Array.from({ length: count }, (_, index) => {
    const progress = index / Math.max(1, count - 1);
    const wave = Math.sin(index * 0.39 + minutes * 0.03) * waveSize;
    const micro = Math.cos(index * 0.17 + 1.2) * waveSize * 0.48;
    const pullback = Math.sin(progress * Math.PI * 5.2) * waveSize * 1.1;
    const trend = -trendRange * (1 - progress);
    return trend + wave + micro + pullback;
  });
  const offset = target - raw.at(-1)!;

  const candles = raw.map((value, index): Candle => {
    const close = roundPrice(value + offset);
    const previous = index === 0 ? close - waveSize * 0.12 : roundPrice(raw[index - 1] + offset);
    const open = roundPrice(previous + Math.sin(index * 0.81) * displayRange * 0.045);
    const wick = displayRange * (0.016 + ((index * 7) % 9) / 520);
    const openTime = new Date(anchor - (count - 1 - index) * stepMs);
    return {
      provider: market.provider,
      symbol,
      timeframe,
      open_time: openTime.toISOString(),
      close_time: new Date(openTime.getTime() + stepMs - 1).toISOString(),
      open,
      high: roundPrice(Math.max(open, close) + wick),
      low: roundPrice(Math.min(open, close) - wick * 0.88),
      close,
      volume: Math.round(volumeBase(timeframe) * (0.22 + Math.abs(Math.sin(index * 0.37)) * 0.63 + ((index * 29) % 100) / 500)),
      trade_count: 118 + ((index * 17) % 420),
    };
  });

  const movingAverage = alignMovingAverage(createMovingAverage(candles), referenceMovingAverage[timeframe]);
  return {
    candles,
    series: [movingAverage],
    markers: createSignalMarkers(candles, timeframe),
  };
}

export function createMockTicks(symbol = "BTCUSDT"): DisplayTick[] {
  const base = symbol.toUpperCase().startsWith("BTC") ? 69_342.18 : 3_782.46;
  const rows = [
    { timestamp: "38.123", delta: 0, quantity: 0.012, side: "buy" as const },
    { timestamp: "38.087", delta: -0.01, quantity: 0.005, side: "buy" as const },
    { timestamp: "38.051", delta: -0.02, quantity: 0.01, side: "sell" as const },
    { timestamp: "38.015", delta: -0.03, quantity: 0.007, side: "buy" as const },
    { timestamp: "37.979", delta: -0.04, quantity: 0.02, side: "sell" as const },
  ];
  return rows.map((row, index) => ({
    id: `mock-tick-${index}`,
    occurredAt: `2025-04-29T10:45:${row.timestamp}Z`,
    price: roundPrice(base + row.delta),
    quantity: row.quantity,
    side: row.side,
  }));
}

export function updateMockCandle(candle: Candle, tick: number): Candle {
  const movement = Math.sin(tick * 0.72) * Math.max(0.18, candle.close * 0.000008);
  const close = roundPrice(candle.close + movement);
  return {
    ...candle,
    close,
    high: Math.max(candle.high, close),
    low: Math.min(candle.low, close),
    volume: tick % 40 === 0 ? 24 : candle.volume + 1 + (tick % 3),
    trade_count: candle.trade_count + 1,
  };
}

export function displayTickFromBbo(
  id: string,
  occurredAt: string,
  bid: number,
  ask: number,
  bidQty: number,
  askQty: number,
): DisplayTick {
  return {
    id,
    occurredAt,
    price: roundPrice((bid + ask) / 2),
    quantity: Number((bidQty + askQty).toFixed(4)),
    side: "bbo",
  };
}

function createMovingAverage(candles: Candle[]): OverlaySeries {
  const windowSize = 20;
  const points = candles.map((candle, index) => {
    if (index < windowSize - 1) return { t: candle.open_time, v: null };
    const window = candles.slice(index - windowSize + 1, index + 1);
    const average = window.reduce((sum, item) => sum + item.close, 0) / window.length;
    return { t: candle.open_time, v: roundPrice(average) };
  });
  return {
    name: "MA(20)",
    overlay_type: "moving_average",
    pane: "main",
    points,
  };
}

function alignMovingAverage(series: OverlaySeries, target?: number): OverlaySeries {
  const last = series.points?.at(-1)?.v;
  if (target == null || last == null) return series;
  const offset = target - last;
  return {
    ...series,
    points: series.points?.map((point) => ({ ...point, v: point.v == null ? null : roundPrice(point.v + offset) })),
  };
}

function createSignalMarkers(candles: Candle[], timeframe: string): OverlayMarker[] {
  const side = timeframe === "1h" || timeframe === "4h" ? "sell" : "buy";
  const indices = [Math.max(8, candles.length - 48), Math.max(16, candles.length - 18)];
  return indices.map((index) => ({
    t: candles[Math.min(index, candles.length - 1)].open_time,
    overlay_type: `${side}_signal`,
    confidence: 0.78,
    evidence: { source: "deterministic-ui-mock" },
  }));
}

function roundPrice(value: number) {
  return Number(value.toFixed(2));
}

function volumeBase(timeframe: string) {
  return ({ "1m": 1_000, "5m": 5_000, "15m": 10_000, "1h": 40_000, "4h": 70_000 } as Record<string, number>)[timeframe] ?? 900;
}
