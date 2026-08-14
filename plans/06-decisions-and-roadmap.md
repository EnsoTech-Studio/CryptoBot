# 06 -- Architecture decisions and roadmap

> ⚠️ **ARCHIVED — superseded by [`blueprint/`](../blueprint/README.md).** Bản nháp đầu, chưa xác thực. Không sửa, không dùng làm nguồn. Xem [`plans/README.md`](README.md) để biết quyết định nào đã thay đổi.


## ADR-001 -- Use backend-mediated WebSocket for normalized realtime data

**Decision:** Binance is reached only by a market-data adapter. The backend publishes normalized candle events to the dashboard through WebSocket (or SSE if only server-to-client flow is required).

**Why:** The frontend must not depend on Binance payloads, and four chart panels need selective independent subscriptions. This also gives one place for reconnect, backfill, stale status, and future exchange adapters. [PDF pp. 5--7]

**Consequence:** The backend owns subscription authorization/limits and must keep message schemas versioned.

## ADR-002 -- Use a registry/plugin boundary for strategies

**Decision:** A strategy is a versioned implementation of a common `Strategy` contract plus declarative metadata in a registry.

**Why:** Adding MACD must not require a controller, UI, database, backtester, or combination-engine edit. The registry supplies UI configuration while pure strategies remain testable. [PDF pp. 12--13, 44--45]

**Consequence:** No hard-coded strategy `if/else` trees. Parameter schemas are validated at the application boundary.

## ADR-003 -- Represent combinations as immutable strategy snapshots

**Decision:** A composite strategy contains immutable child specifications and an explicit combination policy (majority, weighted, etc.).

**Why:** Both the combination method and child parameters affect a historical result. Persisting the exact definition makes leaderboard entries explainable and reproducible. [PDF pp. 14--16, 39]

## ADR-004 -- Separate candidate generation from experiment execution

**Decision:** Search algorithms produce `CandidateStrategy`; the experiment/backtest/evaluation pipeline receives only that stable value.

**Why:** Random Search is required for MVP but Domain-Guided/Genetic search may be added later without rewriting the rest of the pipeline. [PDF pp. 17--19, 45--46]

## ADR-005 -- Start backtesting bounded and synchronous; promote the same job contract to workers

**Decision:** Permit a small, bounded manual experiment to complete inline for the first demo. Persist a run record first and retain `queued/running/completed/failed/cancelled` state from day one. Move long-running search to an explicit worker when its runtime or concurrency exceeds the HTTP budget.

**Why:** The coursework asks the team to explain the queue/worker scaling path; it does not award complexity for its own sake. A stable run/job contract permits a safe later split. [PDF pp. 24--25, 42--43, 46--47]

## ADR-006 -- Treat news and sentiment as isolated optional inputs

**Decision:** News collection normalizes data, sentiment analysis versions classifications, and `NewsSentimentStrategy` is an ordinary strategy plugin.

**Why:** News sources and models may change independently. A failure must not stop market charts or technical-only backtests. [PDF pp. 27--31, 48]

## ADR-007 -- Persist reproducibility before optimizing ranking

**Decision:** Record versioned strategy/candidate, dataset, execution assumptions, evaluator policy, trade facts, and model metadata before adding sophisticated scoring/search.

**Why:** It is impossible to defend or compare a leaderboard result without knowing what produced it. [PDF pp. 38--39, 44]

## Delivery phases

| Phase | Outcome | Evidence |
|---|---|---|
| 0. Baseline | Run existing web/API/AI stack; introduce shared error/request-ID conventions | Docker health checks and API contract tests |
| 1. Market vertical slice | Binance adapter, candle persistence, one chart panel, realtime normalized update | reconnect/backfill test and stale feed UI |
| 2. Multi-chart + strategy plugins | Four independently mutable panels; MA/RSI/BB/SR registry implementations | add-a-MACD demonstration with no core edits |
| 3. Experiments | Immutable snapshots, chronological backtest, trades/equity, required metrics | fixture backtest with known result |
| 4. Combinations + leaderboard | Majority/weighted policy, Random Search, bounded search run, Top-K | displayed progress and reproducible Top-K entry |
| 5. News + sentiment | provider normalization, storage, versioned model result, optional strategy | provider/model failure isolation test |
| 6. Scale proof | Queue/worker adapter only if required by actual load | one-job vs multi-worker throughput comparison |
| 7. Final hardening | Documentation, demo rehearsal, security/reliability checks | fresh-start scripted demo and architecture review |

## Demo script

1. Start Docker Compose and show healthy web, API, AI, and database services.
2. Open `ETHUSDT` with `5m | 15m | 1h | 4h`; demonstrate an update/realtime indicator and independently change one panel.
3. Show the strategy catalogue: MA, RSI, Bollinger, Support/Resistance; add/select a composite.
4. Start a bounded Random Search; show current candidate, tested count, queue/run state, and stop condition.
5. Open the updated Top-K leaderboard and select its first entry.
6. Render its signals, entry/exit markers, trades, return, win rate, maximum drawdown, and number of trades.
7. Open the news view, show stored sentiment distribution, then include sentiment in a new candidate search space.
8. Open the experiment provenance record: strategy/candidate version, timeframe/dataset, fees/slippage, evaluator version, result.
9. Explain the three change scenarios: add MACD, replace Random Search, add OKX or scale workers.

This covers the final brief's proposed demo while proving architectural decisions rather than only UI output. [PDF pp. 49--54]

## Requirements traceability

| Course requirement | Blueprint location | Verification evidence |
|---|---|---|
| Binance behind an adapter | 02, 03, 04 | Frontend unaffected by provider contract test |
| Four independent timeframes | 01, 04 | Panel-specific subscription E2E test |
| Four strategies/plugins | 02, 03 | Registry test; MACD extension demonstration |
| Composite strategies | 03 | Deterministic majority/weighted policy unit tests |
| Historical backtest | 04 | Fixture-based expected trades/metrics test |
| Required evaluation metrics | 01, 05 | Known equity/trade metric test |
| Random Search + Top-K | 03, 04 | Bounded run test and leaderboard ordering test |
| Candlestick, volume, MA/BB/SR, signals, entry/exit, stop-loss/take-profit visualization | 01, 03, 04 | Server-overlay contract plus panel-specific realtime/visual E2E check |
| News -> sentiment pipeline | 04, 05 | Provider/model integration tests |
| Extensibility/scalability/reliability | 01, 02, 05 | Architecture scenario walkthrough |
| Architecture document / ADRs / demo | all files | Presentation/repository review |

## Risk register

| Risk | Mitigation |
|---|---|
| Binance rate limits or disconnects | Adapter retries/backfills; cached persisted candles; visible stale state |
| Look-ahead bias makes results misleading | Next-candle fill rule; chronological fixture tests; documented assumptions |
| Search cost explodes | Explicit candidate/time/no-improvement stop conditions; queue only when needed |
| Leaderboard cannot be explained | Append-only experiment and version snapshots |
| News/model availability lowers demo reliability | Use provider/model adapters and a documented local fixture fallback |
| Scope grows into an exchange bot | Treat simulation-only as a non-negotiable MVP boundary |
