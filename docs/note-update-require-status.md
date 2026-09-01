# Status of `note-update-require.txt`

This is the as-built status of the requirement note. The opening summary in
the original note predates the current implementation and must not be used as
the final project status.

## Product capabilities

| Requirement from note | Status | Evidence / boundary |
| --- | --- | --- |
| Register, login, logout and owned data | Done | Go auth with refresh rotation/CSRF; rehearsal and ownership tests |
| Realtime candles, 1,000-candle bootstrap, provisional replacement | Done | Go Binance market gateway + WebSocket; web market tests |
| Single MA/Bollinger/SMC and manual composite strategy | Done | Plugin registry, composite engine and SMC causal tests |
| Loop Discovery, stop/pause/resume/cancel and leaderboard | Done | Bounded search queue, event worker, rehearsal |
| Backtest form, immutable input, trades/equity/KPI/chart markers | Done | Python engine/store, public API, web contracts and rehearsal |
| Normal crawling from approved sources | Done | RSS/Atom and HTML provider adapters, persisted collection jobs |
| Adaptive crawler when HTML quality gate fails | Done | Sanitized document → LLM extraction fallback → evidence validation/cache |
| LLM sentiment | Done | Groq structured-output contract; unavailable is not fake neutral |
| Natural-language/approved-URL strategy draft | Done | Durable authoring job, safe fetch, immutable draft/review package |
| Generated artifact policy, sandbox and bounded repair | Done | AST policy, isolated Docker sandbox, max-three repair attempts |
| Agent 2: market insight from data | Deferred P2 | Designed read-only role; no public runtime/UI is claimed |
| Agent 3: unrestricted web-search/crawl idea generation | Deferred P2 | Deliberately not implemented: arbitrary web fetch violates SSRF boundary; sources must be operator approved |

## Architecture and evidence deliverables

| Requirement from note | Status | Evidence / boundary |
| --- | --- | --- |
| ASR, Architectural Drivers, Quality Attributes | Done | [`architecture/architectural-drivers.md`](architecture/architectural-drivers.md) |
| C4, UML, use case, high-level component boundaries | Done | `blueprint/assets/diagrams/01` through `39`; mapping in `blueprint/README.md` |
| Strategy/Search/Crawler interfaces | Done | UML diagrams 36–38 and typed ports/plugin contracts |
| Docker Compose, health/readiness and scale path | Done for MVP | `docker-compose.stack.yml`, health checks and worker replicas; Kubernetes remains optional |
| Second market provider proof | Pending | Port and provider-bearing frontend contracts exist, but a registered OKX fixture adapter is still required before claiming it |
| 100k runtime throughput | Pending | Queue-plan proof exists; not a throughput benchmark |
| Failure-injection demo bundle | Partial | Lease/outbox/retry tests exist; repeatable operator scenario script still required |

## Rules for the final presentation

1. Say **“simulation-only”**: there is no exchange order route or exchange
   credential in the product.
2. Do not say the screen data is always live. It is live by default; clearly
   labeled deterministic mock mode exists for UI-reference/demo fallback.
3. Do not claim arbitrary URL crawling or automatic production deployment of
   generated Python. Those are security boundaries, not missing validation.
4. Do not claim 100,000 executed backtests until a measured benchmark artifact
   exists. The current SQL script proves the queue claim query plan only.

For the full evidence table, see
[`../blueprint/traceability.md`](../blueprint/traceability.md).
