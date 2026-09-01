import assert from "node:assert/strict";
import test from "node:test";

import { api } from "./api";
import { createDraft } from "./discovery";


test("strategy authoring keeps the browser request alive for the AI service budget", async () => {
  const originalFetch = globalThis.fetch;
  const originalTimeout = AbortSignal.timeout;
  let timeoutMs = 0;

  Object.defineProperty(AbortSignal, "timeout", {
    configurable: true,
    value: (milliseconds: number) => {
      timeoutMs = milliseconds;
      return new AbortController().signal;
    },
  });
  globalThis.fetch = async () => new Response("{}", {
    status: 202,
    headers: { "Content-Type": "application/json" },
  });

  try {
    await api.createStrategyDraft({ type: "text", text: "Use RSI 14." });
    assert.equal(timeoutMs, 30_000);
  } finally {
    globalThis.fetch = originalFetch;
    Object.defineProperty(AbortSignal, "timeout", {
      configurable: true,
      value: originalTimeout,
    });
  }
});

test("registration sends the supplied identity and creates an authenticated user", async () => {
  const originalFetch = globalThis.fetch;
  let submitted: Record<string, unknown> | undefined;
  globalThis.fetch = async (_input, init) => {
    submitted = JSON.parse(String(init?.body)) as Record<string, unknown>;
    return new Response(JSON.stringify({
      user: { id: "user-1", email: "new@example.com", display_name: "New User", role: "RESEARCHER" },
    }), { status: 201, headers: { "Content-Type": "application/json" } });
  };

  try {
    const response = await api.register("new@example.com", "TwelveChars!", "New User");
    assert.deepEqual(submitted, {
      email: "new@example.com",
      password: "TwelveChars!",
      display_name: "New User",
    });
    assert.equal(response.user.email, "new@example.com");
  } finally {
    globalThis.fetch = originalFetch;
  }
});


test("chart bootstrap requests the required 1000 closed candles by default", async () => {
  const originalFetch = globalThis.fetch;
  let requestedURL = "";
  globalThis.fetch = async (input) => {
    requestedURL = String(input);
    return new Response(JSON.stringify({ candles: [] }), {
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    await api.candles({ provider: "binance_usdm", symbol: "ETHUSDT" }, "5m");
    assert.match(requestedURL, /limit=1000/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("experiment submission preserves the catalog strategy version and defaults", async () => {
  const originalFetch = globalThis.fetch;
  const submitted: Array<Record<string, unknown>> = [];
  globalThis.fetch = async (input, init) => {
    const url = String(input);
    if (url.includes("/markets/datasets")) {
      return new Response(JSON.stringify({
        datasets: [{
          id: "dataset-1",
          dataset_version: "fixture:ETHUSDT:5m:v1",
          market: { provider: "binance_usdm", symbol: "ETHUSDT", timeframe: "5m" },
          range_from: "2026-01-01T00:00:00Z",
          range_to: "2026-01-02T00:00:00Z",
          revision_no: 1,
          candle_count: 288,
          content_hash: "candle-hash",
          bbo_content_hash: "bbo-hash",
        }],
      }), { headers: { "Content-Type": "application/json" } });
    }
    submitted.push(JSON.parse(String(init?.body)) as Record<string, unknown>);
    return new Response(JSON.stringify({ run_id: "run-1", experiment_id: "experiment-1", status: "queued" }), {
      status: 202,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    await api.createExperiment([
      { strategy_id: "generated.rsi-9f3c", strategy_version: "v2", parameters: { period: 21 }, weight: 1 },
    ]);
    assert.equal(submitted[0]?.strategy_version, "v2");
    assert.deepEqual(submitted[0]?.candidate_definition, {
      strategy_id: "generated.rsi-9f3c",
      version: "v2",
      parameters: { period: 21 },
    });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("experiment submission uses the market selected by the backtest form", async () => {
  const originalFetch = globalThis.fetch;
  const requested: string[] = [];
  let submitted: Record<string, unknown> | undefined;
  globalThis.fetch = async (input, init) => {
    const url = String(input);
    requested.push(url);
    if (url.includes("/markets/datasets")) {
      return new Response(JSON.stringify({
        datasets: [{
          id: "dataset-btc",
          dataset_version: "fixture:BTCUSDT:1h:v1",
          market: { provider: "binance_usdm", symbol: "BTCUSDT", timeframe: "1h" },
          range_from: "2026-01-01T00:00:00Z",
          range_to: "2026-01-02T00:00:00Z",
          revision_no: 1,
          candle_count: 24,
          content_hash: "candle-hash",
          bbo_content_hash: "bbo-hash",
        }],
      }), { headers: { "Content-Type": "application/json" } });
    }
    submitted = JSON.parse(String(init?.body)) as Record<string, unknown>;
    return new Response(JSON.stringify({ run_id: "run-btc", experiment_id: "experiment-btc", status: "queued" }), {
      status: 202,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    await api.createExperiment(
      [{ strategy_id: "ma_cross", strategy_version: "v1", parameters: {}, weight: 1 }],
      { provider: "binance_usdm", symbol: "BTCUSDT" },
      "1h",
    );
    assert.match(requested[0] ?? "", /symbol=BTCUSDT/);
    assert.equal(submitted?.symbol, "BTCUSDT");
    assert.equal(submitted?.timeframe, "1h");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("search submission preserves the catalog strategy version and defaults", async () => {
  const originalFetch = globalThis.fetch;
  const submitted: Array<Record<string, unknown>> = [];
  globalThis.fetch = async (input, init) => {
    const url = String(input);
    if (url.includes("/markets/datasets")) {
      return new Response(JSON.stringify({
        datasets: [{
          id: "dataset-1",
          dataset_version: "fixture:ETHUSDT:5m:v1",
          market: { provider: "binance_usdm", symbol: "ETHUSDT", timeframe: "5m" },
          range_from: "2026-01-01T00:00:00Z",
          range_to: "2026-01-02T00:00:00Z",
          revision_no: 1,
          candle_count: 288,
          content_hash: "candle-hash",
          bbo_content_hash: "bbo-hash",
        }],
      }), { headers: { "Content-Type": "application/json" } });
    }
    submitted.push(JSON.parse(String(init?.body)) as Record<string, unknown>);
    return new Response(JSON.stringify({
      search_run_id: "search-1",
      status: "queued",
      generator_id: "random_search",
      seed: 7,
      max_candidates: 20,
      max_duration_sec: 60,
      max_non_improving: 10,
      generated: 0,
      tested: 0,
      failed: 0,
      best_score: null,
      current_candidate_hash: null,
      dataset_version: "fixture:ETHUSDT:5m:v1",
      content_hash: "candle-hash",
      stop_reason: null,
      updated_at: "2026-01-01T00:00:00Z",
    }), { status: 202, headers: { "Content-Type": "application/json" } });
  };

  try {
    const draft = {
      ...createDraft({ provider: "binance_usdm", symbol: "ETHUSDT" }, "5m"),
      selectedStrategyIds: ["generated.rsi-9f3c"],
      weights: { "generated.rsi-9f3c": 1 },
    };
    await api.startSearch(draft, [
      { strategy_id: "generated.rsi-9f3c", strategy_version: "v2", parameters: { period: 21 }, weight: 1 },
    ]);
    assert.deepEqual((submitted[0]?.execution as { children: unknown[] }).children, [{
      strategy_id: "generated.rsi-9f3c",
      version: "v2",
      parameters: { period: 21 },
      weight: 1,
    }]);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
