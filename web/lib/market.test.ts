import assert from "node:assert/strict";
import test from "node:test";

import * as marketConfig from "./market";
import {
  DEFAULT_MARKET,
  MARKET_CONFIG_HASH,
  REFERENCE_MARKET,
  appendMarketEvent,
  buildSubscriptionKey,
  marketRequestPath,
  marketDisplayName,
  mergeOverlayDelta,
  normalizeRealtimeFrame,
  upsertCandle,
  type Candle,
  type MarketSelection,
  type RecentMarketEvent,
} from "./market";

const market: MarketSelection = { provider: "binance_usdm", symbol: "ethusdt" };

test("live startup uses the seeded replay market while reference mode keeps its BTC fixture", () => {
  assert.equal(DEFAULT_MARKET.symbol, "ETHUSDT");
  assert.equal(REFERENCE_MARKET.symbol, "BTCUSDT");
});

test("live dashboard starts its primary panel on the seeded replay interval", () => {
  assert.deepEqual(
    (marketConfig as Record<string, unknown>).DEFAULT_PANEL_TIMEFRAMES,
    ["5m", "15m", "1h", "4h"],
  );
});

test("marketRequestPath carries the selected market and request options", () => {
  const path = marketRequestPath("/api/v1/markets/candles", market, { timeframe: "15m", limit: 1_000 });
  assert.equal(path, "/api/v1/markets/candles?provider=binance_usdm&symbol=ETHUSDT&timeframe=15m&limit=1000");
});

test("buildSubscriptionKey matches the backend subscription contract", () => {
  assert.equal(
    buildSubscriptionKey(market, "5m", "ma_cross@v1"),
    `binance_usdm|ETHUSDT|5m|ma_cross@v1|${MARKET_CONFIG_HASH}`,
  );
});

test("marketDisplayName distinguishes duplicate symbols across providers", () => {
  assert.equal(marketDisplayName({ provider: "okx_swap", symbol: "ethusdt" }), "ETHUSDT · OKX Swap");
});

test("upsertCandle replaces an in-progress candle, sorts, and caps history", () => {
  const first = candle("2026-08-25T10:00:00Z", 100);
  const replacement = candle("2026-08-25T10:00:00Z", 102);
  const next = candle("2026-08-25T10:01:00Z", 104);

  assert.deepEqual(upsertCandle([first], replacement), [replacement]);
  assert.deepEqual(upsertCandle([next, first], replacement, 2), [replacement, next]);
  assert.deepEqual(upsertCandle([first, replacement], next, 1), [next]);
});

test("normalizeRealtimeFrame accepts flat kline frames with numeric strings", () => {
  const frame = normalizeRealtimeFrame({
    type: "kline",
    sequence: 9,
    server_time: "2026-08-25T10:01:01Z",
    final: true,
    kline: {
      open_time: "2026-08-25T10:00:00Z",
      close_time: "2026-08-25T10:00:59Z",
      open: "100",
      high: "105",
      low: "99",
      close: "104",
      volume: "12.5",
      trade_count: "8",
    },
  }, market);

  assert.equal(frame.type, "kline");
  assert.equal(frame.sequence, 9);
  assert.equal(frame.final, true);
  assert.equal(frame.kline?.close, 104);
  assert.equal(frame.kline?.tradeCount, 8);
});

test("normalizeRealtimeFrame accepts a same-sequence overlay delta", () => {
  const frame = normalizeRealtimeFrame({
    type: "overlay_delta",
    sequence: 9,
    revised_from: "2026-08-25T10:00:00Z",
    series: [{ name: "sma:20", overlay_type: "moving_average", pane: "main", points: [{ t: "2026-08-25T10:00:00Z", v: 104 }] }],
    markers: [],
  }, market);

  assert.equal(frame.type, "overlay_delta");
  assert.equal(frame.sequence, 9);
  assert.equal(frame.overlay?.revisedFrom, "2026-08-25T10:00:00Z");
  assert.equal(frame.overlay?.series[0].name, "sma:20");
  assert.equal(frame.overlay?.series[0].points?.[0].v, 104);
});

test("mergeOverlayDelta replaces revised points without dropping chart history", () => {
  const result = mergeOverlayDelta({
    series: [{
      name: "sma:20", overlay_type: "moving_average", pane: "main" as const,
      points: [{ t: "2026-08-25T09:59:00Z", v: 103 }, { t: "2026-08-25T10:00:00Z", v: 104 }],
    }],
    markers: [],
  }, {
    series: [{
      name: "sma:20", overlay_type: "moving_average", pane: "main",
      points: [{ t: "2026-08-25T10:00:00Z", v: 105 }],
    }],
    markers: [],
  });

  assert.deepEqual(result.series[0].points, [
    { t: "2026-08-25T09:59:00Z", v: 103 },
    { t: "2026-08-25T10:00:00Z", v: 105 },
  ]);
});

test("nested BBO payloads normalize and duplicate events are replaced", () => {
  const frame = normalizeRealtimeFrame({
    type: "bbo",
    seq: 12,
    payload: {
      server_time: "2026-08-25T10:01:01Z",
      event_time: "2026-08-25T10:01:00Z",
      bid: "3999.5",
      bid_qty: "2.5",
      ask: "4000",
      ask_qty: "1.75",
      source_sequence: 88,
    },
  }, market);

  assert.equal(frame.type, "bbo");
  assert.equal(frame.bbo?.id, "binance_usdm|ETHUSDT|88");
  assert.equal(frame.bbo?.ask, 4_000);
  assert.equal(frame.bbo?.bidQty, 2.5);

  const original = frame.bbo!;
  const changed = { ...original, ask: 4_001 };
  assert.deepEqual(appendMarketEvent([original], changed), [changed]);
});

test("recent BBO memory remains bounded", () => {
  const events = Array.from({ length: 55 }, (_, index): RecentMarketEvent => ({
    id: String(index),
    occurredAt: `2026-08-25T10:00:${String(index % 60).padStart(2, "0")}Z`,
    bid: index,
    ask: index + 1,
    bidQty: 1,
    askQty: 1,
  }));
  const newest = { ...events[54], id: "newest" };
  const result = appendMarketEvent(events, newest);
  assert.equal(result.length, 50);
  assert.equal(result[0].id, "newest");
});

function candle(openTime: string, close: number): Candle {
  return {
    provider: market.provider,
    symbol: market.symbol.toUpperCase(),
    timeframe: "1m",
    open_time: openTime,
    close_time: openTime,
    open: close - 1,
    high: close + 1,
    low: close - 2,
    close,
    volume: 10,
    trade_count: 1,
  };
}
