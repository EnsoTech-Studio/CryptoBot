import assert from "node:assert/strict";
import test from "node:test";

import { createMockPanelData, createMockTicks, updateMockCandle } from "./realtime-mock";

const market = { provider: "binance_usdm", symbol: "BTCUSDT" };

test("mock panel data is deterministic and matches the requested timeframe", () => {
  const first = createMockPanelData(market, "5m", 180);
  const second = createMockPanelData(market, "5m", 180);

  assert.deepEqual(first, second);
  assert.equal(first.candles.length, 180);
  assert.equal(first.candles.at(-1)?.close, 69_318.42);
  assert.equal(first.candles.every((candle) => candle.timeframe === "5m"), true);
  assert.equal(first.series[0]?.name, "MA(20)");
  assert.equal(first.markers.at(-1)?.overlay_type, "buy_signal");
});

test("mock signal direction mirrors the reference screen", () => {
  const hourly = createMockPanelData(market, "1h", 180);
  assert.equal(hourly.markers.at(-1)?.overlay_type, "sell_signal");
});

test("mock ticks and candle updates remain valid market-shaped data", () => {
  const ticks = createMockTicks();
  const candle = createMockPanelData(market, "1m", 40).candles.at(-1)!;
  const updated = updateMockCandle(candle, 3);

  assert.equal(ticks.length, 5);
  assert.equal(ticks[0].price, 69_342.18);
  assert.equal(updated.high >= updated.close, true);
  assert.equal(updated.low <= updated.close, true);
  assert.equal(updated.volume > candle.volume, true);
});
