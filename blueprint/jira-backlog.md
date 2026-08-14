# CryptoBot Jira backlog

Blueprint-only backlog. No implementation included.

Import rules: every item is a Jira `Story`; Summary starts with external ID;
assignees are `Member 1`–`Member 5`; points are Fibonacci; each `Depends on`
entry becomes a Jira `blocks` link from dependency to dependent task. Existing
active blueprint and Go skeleton are the contract baseline. Verification-spec
restoration is intentionally not a separate task.

## Member 3 — Infrastructure

### M3-01 — Create PostgreSQL migrations, projections, and seeds

- **Assignee / points:** Member 3 / 21 SP
- **Depends on:** M1-01, M2-01, M2-02
- **Purpose:** Make PostgreSQL source of truth for domain facts and views.
- **Scope:** `server/migrations/`, `server/seeds/`; users, sessions, markets,
  candles, BBO, datasets, strategies, experiments, jobs, runs, trades,
  equity, evaluations, search, leaderboard, news, sentiment, event
  consumption, and outbox schemas.
- **Description:** Add fresh-install migrations, immutable snapshots,
  constraints, uniqueness rules, lease columns, append-only facts, indexes,
  projections, and deterministic seed data supporting readiness and ranking.
- **Tests:** Fresh PostgreSQL migration; invalid status/duplicate dataset/mixed
  sentiment-version rejection; stale-lease checks; readiness and leaderboard
  seed queries; snapshot UPDATE/DELETE rejection.

### M3-02 — Implement PostgreSQL repositories, queue, and outbox

- **Assignee / points:** Member 3 / 21 SP
- **Depends on:** M3-01, M2-01, M2-02
- **Purpose:** Connect persistence ports and provide safe jobs/events.
- **Scope:** `server/internal/platform/database/`,
  `infrastructure/postgres/`, `ports/persistence.go`, `ports/job.go`, outbox
  and event-consumption adapters.
- **Description:** Add pools, transactions, idempotent writes,
  `FOR UPDATE SKIP LOCKED`, lease tokens, heartbeat, completion/failure guards,
  retries, and atomic result-plus-outbox commits.
- **Tests:** Repository integration; duplicate event idempotency; expired lease
  reclaim; heartbeat only for matching token; old worker cannot write after
  takeover; atomic result/outbox commit.

### M3-03 — Consolidate runtime configuration and observability

- **Assignee / points:** Member 3 / 13 SP
- **Depends on:** M3-01, M3-02
- **Purpose:** Make startup, health, readiness, metrics, and compose behavior
  production-safe.
- **Scope:** `server/internal/platform/config/`, API/worker entrypoints,
  observability, `docker-compose.yml`, `docker-compose.prod.yml`.
- **Description:** Support `CORS_ALLOWED_ORIGINS` with `CORS_ORIGIN` scaffold
  compatibility; expose `/health`, `/ready`, `/metrics`; keep AI optional for
  core readiness; remove AI host publishing in production compose.
- **Tests:** Health without DB; readiness `503` before DB/migration; AI outage
  does not fail core readiness; invalid origins rejected; compose validation.

### M3-04 — Register target HTTP transport and middleware

- **Assignee / points:** Member 3 / 13 SP
- **Depends on:** M3-03
- **Purpose:** Replace scaffold-only routing with target transport.
- **Scope:** `server/internal/transport/httpapi/`, middleware, route manifest,
  and migration from `server/internal/httpapi/`.
- **Description:** Register every manifest route with a handler or explicit
  `501`; add stable errors, request/correlation IDs, structured logs, body
  limits, timeouts, and exact allowlist CORS; async commands return `202`.
- **Tests:** Every route registered; stable code/message/request ID/field
  errors; arbitrary origin never echoed; limit/timeout behavior; canonical
  `/health` and `/ready`; async `202` responses.

### M3-05 — Implement authentication, authorization, CSRF, and quotas

- **Assignee / points:** Member 3 / 13 SP
- **Depends on:** M3-02, M3-04
- **Purpose:** Secure sessions, ownership, roles, and expensive operations.
- **Scope:** `server/internal/auth/`, session persistence, auth middleware,
  CSRF, RBAC, ownership, AI/search quota middleware.
- **Description:** Add register/login/refresh/logout, refresh-cookie rotation,
  role and ownership checks, CSRF validation, inactive-user rejection, and
  per-principal AI/search quotas.
- **Tests:** Anonymous/owner/operator/admin matrix; cross-user denial;
  refresh-token rotation/reuse; CSRF errors; stable quota errors; inactive
  account rejection.

### M3-06 — Integrate public APIs, internal events, and WebSocket transport

- **Assignee / points:** Member 3 / 13 SP
- **Depends on:** M1-06, M2-04, M3-04, M3-05
- **Purpose:** Connect application services to REST, events, and realtime UI.
- **Scope:** `transport/httpapi/`, `transport/ws/`, application services,
  market/strategy/experiment/search/leaderboard/news/AI handlers, and
  `/internal/events`.
- **Description:** Implement public resource routes, internal event intake,
  versioned WS frames, sequence numbers, reconnect, and resync.
- **Tests:** `httptest`/WebSocket integration for schemas, auth, ownership,
  reconnect, ordering, route errors, and no provisional candles in backtests.

## Member 1 — Market, indicators, strategy

### M1-01 — Implement canonical market and domain primitives

- **Assignee / points:** Member 1 / 8 SP
- **Depends on:** none
- **Purpose:** Establish validated deterministic domain values.
- **Scope:** `server/internal/domain/common/`, `domain/market/`, causal
  strategy inputs, canonical hash helpers.
- **Description:** Implement decimal `Candle`, transient `KlineUpdate`, BBO,
  `CandleQuery`, subscription, validation, stable serialization, and immutable
  `CausalCandles`; provisional data cannot become `Candle`.
- **Tests:** Invalid symbol/timeframe/provider rejection; future access returns
  `LookAheadError`; deterministic hash; provisional exclusion; decimal-stable
  serialization.

### M1-02 — Implement causal indicator library

- **Assignee / points:** Member 1 / 8 SP
- **Depends on:** M1-01
- **Purpose:** Provide reusable causal calculations.
- **Scope:** `server/internal/domain/indicator/`.
- **Description:** Implement SMA/MA cross, RSI, Bollinger Bands, and Go MACD
  (`macd.go`) with warm-up, aligned series, decimal precision, and causal
  `IndicatorView`.
- **Tests:** Known vectors; warm-up; decimal precision; index bounds;
  look-ahead rejection; MACD is not implemented in Python.

### M1-03 — Implement strategy registry and technical plugins

- **Assignee / points:** Member 1 / 13 SP
- **Depends on:** M1-01
- **Purpose:** Make strategies versioned, immutable, and discoverable.
- **Scope:** `domain/strategy/registry.go`, contract, and `plugins/` for MA
  Cross, RSI, Bollinger, Support/Resistance, and MACD.
- **Description:** Implement `Register(definition, factory)`, `Resolve`, sorted
  immutable listing, fingerprint/version validation, parameter schemas,
  warm-up metadata, and pure plugins. Plugin addition must require no core
  branch.
- **Tests:** Duplicate/unknown version failure; invalid definition/missing
  warm-up failure; fingerprint/version check; plugins run without DB/network;
  deterministic listing; no registry/engine/API/UI branch for new plugin.

### M1-04 — Implement composite signal combiners

- **Assignee / points:** Member 1 / 5 SP
- **Depends on:** M1-03
- **Purpose:** Combine resolved child signals deterministically.
- **Scope:** `server/internal/domain/strategy/composite/`.
- **Description:** Implement `weighted_vote` and `majority_vote`; validate
  cardinality, weights, threshold, encoding, and prices; preserve evidence and
  propagate child errors.
- **Tests:** Weighted threshold/boundary; majority tie; HOLD; invalid policy;
  child error; deterministic evidence/output independent of child ordering.

### M1-05 — Implement Binance REST/WebSocket adapters

- **Assignee / points:** Member 1 / 13 SP
- **Depends on:** M1-01
- **Purpose:** Normalize historical klines, realtime klines, and BBO.
- **Scope:** `server/internal/infrastructure/market/binance.go`, private REST/
  WS payloads, limiter, reconnect client.
- **Description:** Parse Binance REST, kline WS, and bookTicker; normalize SOL
  to SOLUSDT; use decimals; enforce final semantics; validate malformed/future
  data; add weight limiting/backoff; keep BBO separate.
- **Tests:** Mock parsing, malformed payloads, final/non-final events, BBO order,
  rate limits, reconnect; opt-in live test with `BINANCE_LIVE=1`.

### M1-06 — Implement market service, reconnect, checkpoints, and datasets

- **Assignee / points:** Member 1 / 13 SP
- **Depends on:** M1-05
- **Purpose:** Produce reliable closed-candle/BBO datasets and events.
- **Scope:** Market service, checkpoint ports, dataset builder, event
  envelopes, market integration tests.
- **Description:** Convert callbacks, backfill reconnect gaps, deduplicate by
  provider/symbol/timeframe/open time, persist checkpoints, publish stale/
  recovered/closed events, and create immutable content-hashed datasets.
- **Tests:** 60-second disconnect has zero missing/duplicate closed candles;
  provisional exclusion; stable dataset hash; idempotent repeated backfill;
  deterministic BBO sequence; provider isolation.

## Member 2 — Backtest, evaluation, jobs, search

### M2-01 — Implement chronological backtest engine

- **Assignee / points:** Member 2 / 21 SP
- **Depends on:** M1-01, M1-02, M1-03, M1-04
- **Purpose:** Produce deterministic raw trade/order/signal/equity facts.
- **Scope:** `domain/backtest/`, `ports.BacktestEngine` implementation, event
  merger, position simulator, BBO replay.
- **Description:** Run chronologically on closed candles; BBO precedes same-time
  candle; fixed notional, one-net position, BBO LIMIT, final-BBO exit, initial
  100 USDT, notional 10 USDT, leverage 1, fee 10 bps, zero slippage.
- **Tests:** Synthetic golden replay; warm-up/no-lookahead; deterministic facts;
  fill-side/fee; opposite and same-side behavior; missing final BBO; invalid
  snapshot with no partial result.

### M2-02 — Implement evaluation metrics and score policy

- **Assignee / points:** Member 2 / 8 SP
- **Depends on:** M2-01
- **Purpose:** Calculate reproducible metrics from immutable facts.
- **Scope:** `server/internal/domain/evaluation/` and evaluation service.
- **Description:** Calculate return, drawdown, volatility/Sharpe, win rate,
  trade count, profit factor, average trade, and policy/version provenance;
  undefined values stay null.
- **Tests:** Empty/no-trade; zero variance; missing equity; decimal determinism;
  invalid policy; evaluator/score provenance; minimum-trade eligibility.

### M2-03 — Execute and document SOL fixture backtest

- **Assignee / points:** Member 2 / 8 SP
- **Depends on:** M1-06, M2-01, M2-02
- **Purpose:** Verify the market-to-evaluation chain with supplied fixture.
- **Scope:** Fixture loaders/replay and
  `blueprint/verification/sol-2026-03-04-ma20-50.md`.
- **Description:** Load the SOL OHLCV/BBO files; record hashes, configuration,
  structural outputs, metrics, and reproducibility. Record PnL only when engine
  produces it.
- **Tests:** 1,443 candles and 800,692 BBO rows; 29 strict MA20/MA50 signals;
  15 settled trades under fixed policy; five identical result hashes; no
  invented PnL.

### M2-04 — Implement experiments, worker execution, and lease lifecycle

- **Assignee / points:** Member 2 / 21 SP
- **Depends on:** M2-01, M2-02, M3-02
- **Purpose:** Execute immutable snapshots asynchronously and safely.
- **Scope:** `application/experiment.go`, `application/worker.go`, job ports,
  worker command, persistence, retry/cancel, lease heartbeat.
- **Description:** Implement snapshot creation, async enqueue, claim/heartbeat/
  complete/fail, retries, cancellation, stale-worker rejection, idempotent
  completion, and atomic facts/run/outbox commit.
- **Tests:** Snapshot immutability; retry; heartbeat; takeover; stale commit
  rejection; cancellation; duplicate completion; restart recovery.

### M2-05 — Implement search loop and candidate generators

- **Assignee / points:** Member 2 / 13 SP
- **Depends on:** M1-03, M1-04, M2-04
- **Purpose:** Search strategy combinations reproducibly and with bounds.
- **Scope:** `domain/search/`, `infrastructure/search/`, candidate hashes,
  generators, search-run service, progress and stop state.
- **Description:** Implement seeded random search, `SearchSpace`,
  `SearchHistory`, `CandidateStrategy`, canonical dedup, bounded attempts,
  stop conditions, progress events, and experiment enqueueing.
- **Tests:** Same seed; duplicate skip; max candidates/duration/non-improvement/
  failure-rate stops; exhausted-space detection; failed candidates continue;
  progress survives restart.

### M2-06 — Implement ranking, leaderboard, and provenance

- **Assignee / points:** Member 2 / 13 SP
- **Depends on:** M2-02, M3-02
- **Purpose:** Rank valid completed runs with traceable policy.
- **Scope:** `domain/ranking/`, ranking service, leaderboard repository/projection,
  tie-breaking, provenance DTOs.
- **Description:** Apply active score policy, exclude incomplete runs, rank
  deterministically, and expose dataset/snapshot/strategy/evaluator/policy
  provenance.
- **Tests:** Missing policy fails readiness/ranking; deterministic ties;
  incomplete exclusion; min-trade rule; exact hash provenance; duplicate event
  idempotency.

## Member 4 — News and AI

### M4-01 — Define and implement AI sentiment service contract

- **Assignee / points:** Member 4 / 8 SP
- **Depends on:** none
- **Purpose:** Stabilize Python inference boundary.
- **Scope:** `ai/app/main.py`, `schemas.py`, `services/predictor.py`, health and
  inference tests.
- **Description:** Preserve internal `POST /predict`; add model version;
  validate bounded text and confidence; keep health separate; report model
  failure explicitly.
- **Tests:** Health; valid prediction; blank/oversized text; score bounds;
  malformed output; model/model-version presence; no fallback sentiment.

### M4-02 — Implement Go sentiment model adapter

- **Assignee / points:** Member 4 / 5 SP
- **Depends on:** M4-01
- **Purpose:** Adapt Python inference to `ports.SentimentAnalyzer`.
- **Scope:** `server/internal/infrastructure/ai/analyzer.go`, HTTP client,
  timeout/error mapping, tests.
- **Description:** Call internal `/predict`, map to `sentiment.Result`, carry
  model version, bound payload/timeouts, and never synthesize `NEUTRAL/0.5`.
- **Tests:** `httptest` success, timeout, 4xx/5xx, malformed JSON, bounds,
  version mapping, unavailable error, no fallback row.

### M4-03 — Implement approved news collection and SSRF controls

- **Assignee / points:** Member 4 / 13 SP
- **Depends on:** M3-01, M3-02
- **Purpose:** Collect trusted news safely and idempotently.
- **Scope:** `domain/news/`, `infrastructure/news/`, RSS provider, canonical
  URL/sanitization, source persistence, worker job, news events.
- **Description:** Use only configured `ApprovedSource`; normalize `news.Item`;
  sanitize/deduplicate; enforce HTTPS/origin/DNS/private-network/redirect/
  timeout/size/item limits; emit `NewsCollected`.
- **Tests:** Approved-source and no-client-URL enforcement; private-IP/unsafe
  redirect/DNS-rebind rejection; timeout/backoff; duplicate items; 2 MB limit;
  sanitization; event idempotency; no strategy/Python imports.

### M4-04 — Persist sentiment, aggregate windows, and add news strategy

- **Assignee / points:** Member 4 / 13 SP
- **Depends on:** M1-03, M3-02, M4-02, M4-03
- **Purpose:** Make sentiment optional, causal, and provenance-aware.
- **Scope:** Sentiment persistence/service, `NewsSentimentWindow`, model/version
  constraints, lag aggregation, `news_sentiment` plugin, `AnalysisContext`.
- **Description:** Persist `(news_item, model, model_version)`; apply lag; use
  one version per window; pass window through context; HOLD on missing data;
  keep strategy free of SQL/HTTP/model dependencies.
- **Tests:** Version uniqueness; no fake rows; lag/no-lookahead; missing HOLD;
  deterministic aggregate; model version in evidence; technical-only operation
  without AI; bounded precomputed query count.

### M4-05 — Implement AI/news degradation behavior

- **Assignee / points:** Member 4 / 5 SP
- **Depends on:** M3-03, M3-06, M4-04
- **Purpose:** Prove optional AI/news failure preserves core system.
- **Scope:** API errors, news/sentiment workers, readiness, chart and technical
  backtest paths, retry/recovery integration tests.
- **Description:** AI failure prevents sentiment writes and marks unavailable
  data; market data, chart, technical backtest, and core readiness continue;
  recovery enables later retry.
- **Tests:** Mock AI `503`; readiness remains core healthy; chart/technical
  backtest succeed; no neutral placeholders; retry succeeds after recovery.

## Member 5 — Frontend and end-to-end verification

### M5-01 — Define web API, WebSocket, and state contracts

- **Assignee / points:** Member 5 / 5 SP
- **Depends on:** M3-04, M3-06
- **Purpose:** Define typed browser-facing contracts.
- **Scope:** `web/lib/api.ts`, DTOs for market/WS/experiments/search/
  leaderboard/news/auth/errors/loading/degraded states.
- **Description:** Consume only Go REST/WS contracts; define stable envelopes,
  ownership/auth states, and distinct provisional/closed payloads.
- **Tests:** Type-check against mocked Go responses; malformed/error handling;
  typed reconnect; static scan finds no DB/Python calls.

### M5-02 — Implement four-panel realtime market dashboard

- **Assignee / points:** Member 5 / 13 SP
- **Depends on:** M1-06, M3-06, M5-01
- **Purpose:** Render independent realtime timeframe panels.
- **Scope:** Chart, indicator/strategy overlays, market status, four timeframe
  subscriptions, reconnect state, accessibility.
- **Description:** Support stale/recovered status, sequence checks, provisional
  updates, closed overlays, and isolated panel state; calculations stay backend.
- **Tests:** Mock reconnect; timeframe isolation; stale-event rejection;
  provisional/closed rendering; loading/error/empty; keyboard/accessibility;
  one panel change does not rerender others.

### M5-03 — Implement experiment and backtest visualization

- **Assignee / points:** Member 5 / 13 SP
- **Depends on:** M2-02, M3-06, M5-01
- **Purpose:** Show async lifecycle and reproducible results.
- **Scope:** Experiment status, trades, equity, signals, overlays, polling,
  ownership errors, provenance components.
- **Description:** Render queued/running/completed/failed/cancelled states and
  exact dataset/strategy/snapshot/evaluator metadata; hide facts before
  completion.
- **Tests:** Every lifecycle response; API-to-chart order; no premature result;
  safe ownership errors; exact provenance; accessible empty/loading/error.

### M5-04 — Implement search, leaderboard, and news views

- **Assignee / points:** Member 5 / 13 SP
- **Depends on:** M2-06, M3-06, M4-04, M5-01
- **Purpose:** Expose search progress, ranking provenance, news, and coverage.
- **Scope:** Search actions/progress, leaderboard, provenance, news list/
  aggregate, sentiment version, pagination, auth errors.
- **Description:** Show score policy, dataset hash, strategy/model version,
  missing sentiment, ranking failures, pause/resume/cancel, and deterministic
  tie order; retain `sentiment: null` as unavailable.
- **Tests:** Deterministic ranking; missing policy; no-sentiment; model version;
  pagination; authorization; loading/empty/degraded/retry states.

### M5-05 — Enforce frontend purity and accessibility

- **Assignee / points:** Member 5 / 5 SP
- **Depends on:** M5-02, M5-03, M5-04
- **Purpose:** Harden browser boundaries and inclusive behavior.
- **Scope:** `web/app/`, `web/components/`, `web/lib/`, error boundaries,
  keyboard/focus/ARIA, purity checks, frontend tooling.
- **Description:** Remove direct infrastructure assumptions; standardize error
  boundaries/degraded states; document typecheck/lint/accessibility commands.
- **Tests:** Typecheck/lint; static DB/Python scan; keyboard/focus management;
  automated accessibility; no raw upstream error leakage.

### M5-06 — Run final Binance, fixture, and scale verification

- **Assignee / points:** Member 5 / 13 SP
- **Depends on:** M1-05, M1-06, M2-03, M3-03, M3-05, M3-06, M4-05, M5-05
- **Purpose:** Verify the complete component graph under live, failure, and
  bounded-concurrency conditions.
- **Scope:** E2E harness, Docker stack, fixture replay, opt-in Binance,
  provider disconnect/reconnect, auth/API/WS/UI, AI outage, leases, rate
  limits, ownership, and concurrent experiments.
- **Description:** Run SOL fixture; connect with `BINANCE_LIVE=1`; disconnect
  provider for 60 seconds; reconnect/backfill; exercise complete stack and
  bounded concurrent jobs; collect reproducibility evidence.
- **Tests:** Zero candle loss/duplication; reproducible fixture; containers
  interoperate; AI outage preserves technical functionality; rate limits,
  lease recovery, ownership, auth, four-timeframe WS, and scale bounds pass.

## Component interaction acceptance

```text
Binance REST/WSS
  -> MarketDataProvider/BBO capability
  -> MarketService
  -> closed Candle + BBO dataset + events
  -> StrategyRegistry
  -> causal AnalysisContext
  -> Signal / ResolvedSignal
  -> BacktestEngine(snapshot, Candle[], BBO[])
  -> Result
  -> Evaluator
  -> Ranking/API/Web UI
```

```text
ApprovedSource
  -> NewsProvider
  -> news.Item
  -> SentimentAnalyzer(text)
  -> sentiment.Result
  -> NewsSentimentWindow
  -> AnalysisContext
  -> news_sentiment strategy
```

```text
Experiment API
  -> immutable snapshot
  -> JobDispatcher lease/heartbeat
  -> Worker
  -> BacktestEngine
  -> PostgreSQL projections/outbox
  -> REST/WebSocket/frontend
```

## Totals

| Member | Stories | Story points |
|---|---:|---:|
| Member 1 | 6 | 60 |
| Member 2 | 6 | 84 |
| Member 3 | 6 | 94 |
| Member 4 | 5 | 44 |
| Member 5 | 6 | 62 |
| **Total** | **29** | **344** |
