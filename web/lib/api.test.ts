import assert from "node:assert/strict";
import test from "node:test";

import { api } from "./api";
import { createDraft } from "./discovery";


test("strategy authoring command uses the standard request timeout", async () => {
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
    assert.equal(timeoutMs, 8_000);
  } finally {
    globalThis.fetch = originalFetch;
    Object.defineProperty(AbortSignal, "timeout", {
      configurable: true,
      value: originalTimeout,
    });
  }
});

test("custom Python authoring command explicitly keeps the advanced mode", async () => {
  const originalFetch = globalThis.fetch;
  let submitted: Record<string, unknown> | undefined;
  globalThis.fetch = async (_input, init) => {
    submitted = JSON.parse(String(init?.body)) as Record<string, unknown>;
    return new Response("{}", { status: 202, headers: { "Content-Type": "application/json" } });
  };

  try {
    await api.createStrategyDraft(
      { type: "text", text: "class Strategy:\n    def analyze(self, candles): return []" },
      "Custom review",
      "custom_python",
    );
    assert.equal(submitted?.mode, "custom_python");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("strategy draft lookup requests the exact durable draft", async () => {
  const originalFetch = globalThis.fetch;
  let requestedURL = "";
  globalThis.fetch = async (input) => {
    requestedURL = String(input);
    return new Response(JSON.stringify({}), { headers: { "Content-Type": "application/json" } });
  };

  try {
    await api.strategyDraft("draft-123");
    assert.match(requestedURL, /\/api\/v1\/strategy-drafts\/draft-123$/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("trade result requests use the stable sequence cursor", async () => {
  const originalFetch = globalThis.fetch;
  let requestedURL = "";
  globalThis.fetch = async (input) => {
    requestedURL = String(input);
    return new Response(JSON.stringify({ trades: [], next_cursor: null }), {
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    await api.experimentTrades("experiment-1", 47, 20);
    assert.match(requestedURL, /after_sequence=47/);
    assert.match(requestedURL, /limit=20/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("experiment overlays preserve execution markers for trade inspection", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({
    overlays: [],
    execution_markers: [{ sequence_no: 7, t: "2026-01-01T00:00:00Z", overlay_type: "long_entry", price: 100 }],
  }), { headers: { "Content-Type": "application/json" } });

  try {
    const payload = await api.experimentOverlays("experiment-1");
    assert.deepEqual(payload.execution_markers, [
      { sequence_no: 7, t: "2026-01-01T00:00:00Z", overlay_type: "long_entry", price: 100 },
    ]);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("strategy draft cancel posts the fixed cancel action", async () => {
  const originalFetch = globalThis.fetch;
  let requestedURL = "";
  let submitted: Record<string, unknown> | undefined;
  globalThis.fetch = async (input, init) => {
    requestedURL = String(input);
    submitted = JSON.parse(String(init?.body)) as Record<string, unknown>;
    return new Response(JSON.stringify({}), { headers: { "Content-Type": "application/json" } });
  };

  try {
    await api.cancelStrategyDraft("draft-123");
    assert.match(requestedURL, /\/api\/v1\/strategy-drafts\/draft-123\/actions$/);
    assert.deepEqual(submitted, { action: "cancel" });
  } finally {
    globalThis.fetch = originalFetch;
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
      method: "random_search" as const,
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

test("discovery submission uses the durable generator and archive endpoint", async () => {
  const originalFetch = globalThis.fetch;
  const requested: string[] = [];
  const submitted: Record<string, unknown>[] = [];
  globalThis.fetch = async (input, init) => {
    const url = String(input);
    requested.push(url);
    if (url.includes("/markets/datasets")) {
      return new Response(JSON.stringify({
        datasets: [{
          id: "dataset-sol",
          dataset_version: "binance_usdm:SOLUSDT:1m:2026-03-04",
          market: { provider: "binance_usdm", symbol: "SOLUSDT", timeframe: "1m" },
          range_from: "2026-03-04T00:00:00Z",
          range_to: "2026-03-05T00:00:00Z",
          revision_no: 1,
          candle_count: 1443,
          content_hash: "candle-hash",
          bbo_content_hash: "bbo-hash",
        }],
      }), { headers: { "Content-Type": "application/json" } });
    }
    if (url.includes("/archive")) {
      return new Response(JSON.stringify({
        search_run_id: "discovery-1",
        state: { final_candidate_id: "candidate-1" },
        candidates: [{
          candidate_id: "candidate-1",
          ordinal: 1,
          candidate_hash: "candidate-hash",
          candidate_definition: { strategy_id: "rsi", version: "v1", parameters: {} },
          lineage: { generator: "random", phase: "terminal" },
          score: 0.42,
          accepted: true,
          rejection_reason: null,
          assessment: { score: 0.42 },
          assessed_at: "2026-03-04T01:00:00Z",
        }],
      }), { headers: { "Content-Type": "application/json" } });
    }
    submitted.push(JSON.parse(String(init?.body)) as Record<string, unknown>);
    return new Response(JSON.stringify({
      search_run_id: "discovery-1",
      status: "running",
      generator_id: "discovery",
      generated: 1,
      tested: 0,
      failed: 0,
      best_score: null,
      current_candidate_hash: "candidate-hash",
      dataset_version: "binance_usdm:SOLUSDT:1m:2026-03-04",
      content_hash: "candle-hash",
      stop_reason: null,
      updated_at: "2026-03-04T00:00:00Z",
    }), { status: 202, headers: { "Content-Type": "application/json" } });
  };

  try {
    const draft = {
      ...createDraft({ provider: "binance_usdm", symbol: "SOLUSDT" }, "1m"),
      selectedStrategyIds: ["ma_cross", "rsi"],
      weights: { ma_cross: 0.5, rsi: 0.5 },
      method: "discovery" as const,
      maxCandidates: 3,
    };
    const run = await api.startSearch(draft);
    const archive = await api.discoveryArchive(run.search_run_id);
    assert.equal(submitted[0]?.generator_id, "discovery");
    assert.equal((submitted[0]?.market as { dataset_version: string }).dataset_version, "binance_usdm:SOLUSDT:1m:2026-03-04");
    assert.equal(archive.candidates[0]?.accepted, true);
    assert.ok(requested.some((url) => url.endsWith("/api/v1/search-runs/discovery-1/archive")));
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("discovery session history uses the owner-scoped search run collection", async () => {
  const originalFetch = globalThis.fetch;
  let requestedURL = "";
  globalThis.fetch = async (input) => {
    requestedURL = String(input);
    return new Response(JSON.stringify({
      runs: [{
        search_run_id: "run-history", generator_id: "discovery", status: "completed",
        generated: 2, tested: 2, failed: 0, best_score: 1.1,
        current_candidate_hash: null, dataset_version: "fixture:SOLUSDT:1h:v1",
        content_hash: "a".repeat(64), stop_reason: "final_test_completed",
        updated_at: "2026-09-02T00:00:00Z",
      }],
    }), { headers: { "Content-Type": "application/json" } });
  };

  try {
    const sessions = await api.discoveryRuns();
    assert.match(requestedURL, /\/api\/v1\/search-runs$/);
    assert.equal(sessions[0]?.search_run_id, "run-history");
    assert.equal(sessions[0]?.candidates.tested, 2);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("leaderboard requests the selected market and timeframe", async () => {
  const originalFetch = globalThis.fetch;
  let requestedURL = "";
  globalThis.fetch = async (input) => {
    requestedURL = String(input);
    return new Response(JSON.stringify({ entries: [] }), { headers: { "Content-Type": "application/json" } });
  };

  try {
    await api.leaderboard({ provider: "binance_usdm", symbol: "SOLUSDT" }, "1m");
    assert.match(requestedURL, /provider=binance_usdm/);
    assert.match(requestedURL, /symbol=SOLUSDT/);
    assert.match(requestedURL, /timeframe=1m/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
