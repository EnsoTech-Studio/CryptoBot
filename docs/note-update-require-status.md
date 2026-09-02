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
| Second market provider proof | Partial | `ProviderRegistry` resolves the deterministic `okx_fixture` adapter through the same `RealtimeMarketProvider` contract; regression tests cover contract preservation and provider-scoped stale state. Production registers Binance only, so this is not a live second-exchange integration. |
| 100k runtime throughput | Done with boundary | [`benchmark-100k-2026-09-03.json`](benchmark-100k-2026-09-03.json) records 100,000 executed jobs on an isolated PostgreSQL 16 database with 4 workers and 50 candles: 100% completed, 1519.209s elapsed, 65.824 jobs/s, p50 746604.202 ms, p95 1438429.875 ms. Scope is queue → worker → deterministic engine → persisted results; it excludes Go/API and event evaluation. Worker counts 8/16 remain unmeasured. |
| Failure-injection demo bundle | Done (isolated rehearsal) | The repeatable failure baseline and real PostgreSQL queue integration suite pass. The suite runs real backtest and event-worker processes, kills each after lease acquisition, waits for expiry, then verifies the replacement worker reclaims and completes exactly once. |

## Latest local verification (2026-09-01)

The host did not have Go, `uv`, PowerShell, or the Docker Compose plugin in
its `PATH`, so the checks below were run with the project's already-built
Docker images. They are real source-tree checks, not claims based only on a
previous handoff.

| Check | Result | Scope / limitation |
| --- | --- | --- |
| Go suite | Pass | `go test ./...` in the local `golang:1.23-alpine` image. This includes the provider registry and provider-scoped stale-state regression tests. |
| Failure-contract baseline | Pass | 52 tests passed for worker lease/retry, agent orchestration, news sentiment, and adaptive extraction. The queue process-crash check is separately listed below. |
| Queue integration | Pass with boundary | 23 PostgreSQL-backed tests passed for claim/lease/heartbeat/reclaim, completion fencing, outbox, quota, and async-idempotent research creation. The suite runs real backtest and event-worker processes, kills each after lease acquisition, waits for expiry, then verifies the replacement worker completes attempt 2 exactly once. This remains isolated local PostgreSQL evidence, not a production load benchmark. |
| Running-stack health | Pass | `GET /` on web returned 200; API `/health` and `/ready` returned 200, with database, market, and research all ready. |
| Architecture/private-network guard | Pass | `tests/test_integration_stack.py` (4 tests) and `scripts/check_architecture.py` pass. They require production to keep PostgreSQL, AI and Research host ports private, validate the event-outbox lease config, and reject browser source that bypasses the Go edge. This is static/configuration evidence, not dynamic browser-network capture. |
| Frontend source suite | Pass | Current source ran in a local Node 22 Docker dependency image: 45 tests passed, followed by ESLint and `tsc --noEmit` with exit code 0. |
| 100k queue proof | Pass with boundary | Separate PostgreSQL 16 container ran `queue-scale-proof.sql`; 100k experiments inserted in ~2.899s, 100k jobs in ~1.202s, and the claim-query execution time was ~2.236ms. The transaction rolled back. |
| k6 readiness smoke | Pass with boundary | 10 VU for 60s against `/ready`: 23,954 requests (~401 req/s), p95 38.08ms and 0% errors. This measures only API readiness under this local setup. |

## Rules for the final presentation

1. Say **“simulation-only”**: there is no exchange order route or exchange
   credential in the product.
2. Do not say the screen data is always live. It is live by default; clearly
   labeled deterministic mock mode exists for UI-reference/demo fallback.
3. Do not claim arbitrary URL crawling or automatic production deployment of
   generated Python. Those are security boundaries, not missing validation.
4. Claim 100,000 executed backtests only with the measured artifact and its
   boundary. The SQL script still proves the queue claim query plan only;
   [`benchmark-100k-2026-09-03.json`](benchmark-100k-2026-09-03.json) is the
   separate end-to-end worker/engine evidence for the 4-worker run.

For the full evidence table, see
[`../blueprint/traceability.md`](../blueprint/traceability.md).
