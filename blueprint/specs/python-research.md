# Đặc tả: Python Research Platform

Trạng thái: canonical target + một phần implementation hiện có  
Service/package: `research`, source root `app/`  
Workloads: Research API và Research Worker dùng cùng package/image

## Mô tả

Python `research` là domain owner duy nhất của Strategy Runtime, Composite, Backtest,
Evaluation, Search, Ranking/Leaderboard, result visualization data, News/Sentiment
orchestration và Agent Platform. Research API phục vụ signed internal command/query từ Go;
Research Worker consume durable jobs. Hai workload dùng cùng domain/application code và cùng
Strategy Runtime, không có engine thứ hai.

Go chỉ sở hữu Public API/Edge và Market Data. AI/LLM Adapter là internal inference-only.

## Ownership contract

| Capability | Owner | Giao tiếp |
|---|---|---|
| Public REST/WSS, auth/RBAC/quota/CORS/error | Go | Browser -> Go |
| Binance/provider REST/WSS, Candle/BBO, backfill/checkpoint | Go | Go Market internal contract |
| Strategy catalog/runtime/version/composite/indicator | Python | Python domain/application |
| Experiment/job/run/trade/equity/evaluation | Python | Python API/worker + DB |
| Search/generator/ranking/leaderboard | Python | Python application services |
| News fetch/extract/tag/sentiment orchestration | Python | Python ports + AI adapter |
| Agent workflow/tool/artifact/sandbox/approval | Python | Python Agent Platform |
| Structured model inference | AI Adapter | Python `ModelGateway` only |
| Persisted event fan-out | Go | Python outbox -> Go `/internal/events` |

Invariants:

- Python không mở Binance connection.
- Go không tính indicator/signal/PnL/evaluation/rank.
- AI Adapter không ghi domain DB hoặc giữ workflow state.
- Browser không gọi Python/AI trực tiếp.
- Realtime và backtest resolve cùng immutable Python StrategyVersion.

## Bốn runtime rules

### R1 - Numeric precision

Canonical numeric type trong Python runtime là `float`/float64. Input được validate finite;
serialization/rounding/currency display có explicit rule. Không trộn Go decimal semantics vào
Python engine rồi gọi hai kết quả là tương đương.

### R2 - Causality

`CausalCandles` và `IndicatorView` không expose future index, negative index, slice hoặc raw
container length có thể leak tương lai. Strategy chỉ thấy data tại/before current event.

### R3 - Execution fidelity

Backtest merge normalized BBO trước CandleClosed theo `(event_time, source_sequence)`. LIMIT
BUY cross ask, LIMIT SELL cross bid; fallback candle fill phải explicit trong snapshot và
provenance. Risk/fee/spread/slippage đều deterministic.

### R4 - Data/network boundary

Python đọc market qua `MarketDataPort`, infrastructure adapter gọi authenticated Go internal
Market contract. Experiment chạy trên immutable dataset snapshot/hash. Agent tool gọi Python
application port, không gọi Go endpoint trực tiếp.

## Component map

```text
app/
  domain/
    market, indicator, strategy, composite
    backtest, evaluation, search, ranking
    news, sentiment, agent
  application/
    strategy_catalog, experiment, backtest, search, leaderboard
    source_ingestion, authoring, agent_orchestrator
    tool_registry, permission_policy, budget_manager
    news_pipeline, insight
  infrastructure/
    postgres repositories + outbox
    go_market_adapter
    model_gateway_adapter
    artifact_store
    sandbox_adapter
  transport/
    internal HTTP command/query
    worker job handlers
```

Target paths nêu intent; code hiện có có thể tiếp tục được tổ chức dần miễn dependency rules
và ownership không đổi.

## Existing reusable seams

- `app/domain/strategy/registry.py`
- `app/domain/strategy/contract.py`
- `app/domain/strategy/plugins/`
- `app/services/backtest_engine.py`
- `app/services/evaluator.py`
- `app/services/search.py`
- `app/services/ranking.py`
- `app/services/news.py`

Agent Platform phải wrap các service này bằng typed application tools. Agent không import
module trực tiếp, không nhận repository/DB session và không bypass permission/audit/budget.

## Internal API contract

### Go -> Python

Versioned internal endpoints hoặc equivalent RPC groups:

- Strategy catalog/version and authoring draft commands/queries.
- Agent run/status/evidence and approval commands.
- Experiment/search/leaderboard commands/queries.
- News/sentiment/insight queries.
- Health/readiness/compatibility.

Mỗi request có service signature, principal delegation, timestamp/nonce anti-replay,
correlation ID, deadline và idempotency key cho write. Python re-authorize resource ownership;
không tin một raw user ID header không ký.

### Python -> Go Market

- `GET /internal/market/candles`
- `GET /internal/market/bbo-snapshot`
- Authenticated normalized market event stream.

Contract chứa provider, symbol, timeframe, `open_time`, final/provisional flag,
event/source sequence, checkpoint và as-of semantics.

### Python -> Go event fan-out

- `POST /internal/events`

Python persist aggregate state + outbox trong cùng transaction. Go de-duplicate `event_id` và
fan-out authorized summary/reference. Go không dùng event để tái tạo domain state.

## Database ownership

Một PostgreSQL instance có thể dùng chung, nhưng role/grant và migration ownership tách rõ:

### Go-owned write

- Market pair/provider metadata.
- Closed candle cache, BBO/market events nếu persist.
- Stream checkpoints/reconnect state.
- Edge auth/session/refresh/quota data.

### Python-owned write

- Strategy definitions/versions/drafts/revisions.
- Agent runs/attempts/tool invocations/artifacts/sandbox/approvals.
- Experiments/jobs/runs/signals/trades/equity/evaluations.
- Search runs/candidates/ranking/leaderboard.
- News documents/items/extractions/tags/sentiment.
- Insight drafts và Python outbox.

MVP không cho Go trực tiếp join/read nhiều Python domain tables. Public query qua stable Python
internal API để tránh coupling schema. Cross-owner foreign key chỉ dùng khi migration ownership
và failure behavior được chứng minh; ưu tiên immutable ID/value snapshot.

## Worker model

- PostgreSQL durable job queue với claim `FOR UPDATE SKIP LOCKED`.
- Lease token + expiration + heartbeat; mọi result update guard current lease token.
- Retry/cancellation/status idempotent; old worker mất lease không được ghi.
- Scale bằng N Research Worker replicas, không đổi API/schema/domain contract.
- Agent job, backtest candidate, evaluation và ranking có handler riêng nhưng dùng chung job
  lifecycle/observability.
- CPU-heavy generated code chỉ chạy sandbox workload, không trong API process.

## Agent Platform integration

`AgentOrchestrator`, `ToolRegistry`, `ModelGateway`, permission/budget/state transition và
repositories nằm trong Python application/infrastructure. Sáu logical roles theo
`agent-architecture.md`; không deploy role riêng.

Required P0/P1:

- Designer, Implementation, Repair.
- News Extraction fallback.
- StrategySpec schema/semantic validator.
- Deterministic compiler, AST/import policy checker.
- Isolated Sandbox Runner và contract fixtures.
- Human ApprovalService và StrategyPublisher.

P2 default-off:

- Candidate Discovery generator adapter.
- Market Insight read-only flow.

## News và AI boundary

Python News Pipeline sở hữu:

```text
Safe Fetch
  -> Readability Extract
  -> Quality Gate
     -> pass: normalize
     -> fail: NewsExtractionAgent on sanitized HTML
  -> schema/quality validation
  -> content/model/prompt/schema hash cache
  -> tagging
  -> sentiment through AI adapter
```

AI Adapter trả structured inference, không insert/update news/sentiment table. Model down tạo
`unavailable`/null có provenance; không fake `NEUTRAL`.

## Failure behavior

| Failure | Behavior |
|---|---|
| Go Market unavailable | Current Python jobs retry/bound deadline; không tự nối Binance |
| Python API down | Go trả 503 cho domain command/query; market/WSS vẫn hoạt động |
| Python Worker down | Jobs remain durable; API vẫn nhận/query persisted state |
| PostgreSQL down | Python readiness fail; không báo completed khi chưa persist |
| AI Adapter down | Agent/news inference fail/unavailable; deterministic technical flow vẫn chạy |
| Sandbox down | Authoring dừng trước review; không publish |
| Go event endpoint down | Python state đúng; outbox retry; UI refetch theo aggregate version |
| Worker chết/mất lease | New worker takeover; old token cannot write |

## Security

- Python internal API không public bind hoặc được network policy chặn từ browser.
- Service-to-service signature rotation và anti-replay.
- Least-privilege DB role theo owner.
- Model/sandbox không nhận application/market credential.
- Agent tools deny-by-default; không shell/SQL/arbitrary HTTP/secret/publish.
- Safe Fetcher SSRF guard ở mọi redirect/DNS resolution.
- Generated Python no-network/no-DB/non-root/read-only/bounded.

## Observability

Trace propagation:

```text
Browser -> Go -> Python API -> job/worker
  -> domain/tool/model/sandbox
  -> PostgreSQL/outbox -> Go event -> Browser
```

Log chung có timestamp, level, service/workload, correlation/request/principal, aggregate/run/job,
event/tool/model/sandbox fields phù hợp. Không log raw prompt/source/secret.

Metrics gồm API/job/lease/domain event, backtest/search/evaluation/ranking, news/sentiment và
agent/tool/model/sandbox metrics. High-cardinality IDs nằm trong logs/traces, không làm label.

## Tiêu chí chấp nhận

- [ ] AC-01: Architecture test chặn Go import/implement strategy/backtest/search/news domain.
- [ ] AC-02: Python không mở Binance/network provider ngoài Go Market adapter.
- [ ] AC-03: Browser không truy cập Python/AI internal endpoints.
- [ ] AC-04: Research API/Worker dùng cùng package/image và Strategy Runtime.
- [ ] AC-05: Go không có write grant lên Python-owned tables và ngược lại.
- [ ] AC-06: Public Python-domain query qua Go proxy nhưng source of truth là Python API.
- [ ] AC-07: Same StrategyVersion tạo signal parity realtime/backtest.
- [ ] AC-08: Worker lease takeover không duplicate/fence-bypass result.
- [ ] AC-09: AI/model adapter không có domain write path.
- [ ] AC-10: Agent tool không bypass permission/budget/audit/repository boundary.
- [ ] AC-11: News fallback chỉ nhận sanitized document sau deterministic quality fail.
- [ ] AC-12: Python state commit trước Go progress event; event retry không mất state.

## Implementation status

Strategy Registry/plugins và service seams cho backtest/evaluation/search/ranking/news đã có
trong `app/`. Internal API ownership cleanup, complete Python-owned migrations, Agent Platform,
compiler/policy/sandbox/approval và adaptive news extraction còn cần implementation evidence.
