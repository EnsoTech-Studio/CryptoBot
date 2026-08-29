# Crypto Strategy Lab - Working Context

Last updated: 2026-08-26 (Asia/Saigon)

## Resume protocol

This file is the durable context for the current architecture review.

After context compaction, a model switch, a new session, or loss of conversational
history, read this file completely before making decisions or editing architecture
documents. Treat the decisions under "Locked decisions" as current user intent
unless the user explicitly changes them.

Do not restart the requirements audit from assumptions. The relevant source files,
findings, ownership decision, agent design, tool design, and pending work are recorded
below.

## 1. Current user goal

The user has:

- The assignment in `Crypto Strategy Lab - Do an cuoi ky.pdf` (actual filename uses
  Vietnamese punctuation: `Crypto Strategy Lab – Đồ án cuối kỳ.pdf`).
- Consolidated requirements in `requirements.html`.
- A teacher-provided supplemental note in `note.txt`.
- An existing architecture blueprint under `blueprint/`.
- A partial implementation containing Next.js, Go, Python research, Python AI,
  PostgreSQL migrations, tests, and Docker Compose configuration.

The user first requested an audit of whether the blueprint correctly satisfies the
assignment and `note.txt`, especially because the blueprint appeared to lack agent
architecture. The user then clarified the canonical language boundary:

> Go should only own Market Data and API responsibilities.

The current objective is to preserve the complete reasoning so subsequent work can
update the blueprint consistently and design the agent/tool architecture without
losing context.

## 2. Source-of-truth files

Read these before architecture edits:

1. `note.txt`
2. `requirements.html`
3. `Crypto Strategy Lab – Đồ án cuối kỳ.pdf`
4. `blueprint/README.md`
5. `blueprint/proposal.md`
6. `blueprint/design.md`
7. `blueprint/traceability.md`
8. `blueprint/specs/strategy-authoring.md`
9. `blueprint/specs/strategy-registry.md`
10. `blueprint/specs/python-research.md`
11. `blueprint/specs/market-data.md`
12. `blueprint/specs/backtest.md`
13. `blueprint/specs/search-loop.md`
14. `blueprint/specs/news.md`
15. `blueprint/specs/sentiment.md`
16. `blueprint/specs/visualization.md`
17. `blueprint/jira-backlog.md`
18. `blueprint/assets/diagrams/*.mmd`

Repository execution instructions:

- `C:\Users\Admin\.codex\RTK.md` requires every shell command to be prefixed by
  `rtk`.
- Preserve unrelated user changes and untracked files.
- At the time of this context capture, the pre-existing untracked paths were
  `UI-reference/`, `note.txt`, and `ui-refactor-plans/`.

## 3. Assignment requirements already audited

### 3.1 Original assignment MVP

The assignment requires at least:

- Binance historical and realtime market data.
- Candlestick charts with realtime updates.
- Up to four independently configurable timeframe panels.
- At least four single strategies: MA, RSI, Bollinger Bands, and
  Support/Resistance.
- Extensible Strategy Plugin/Registry architecture.
- Manual composite strategies with an explained combination policy.
- Backtesting on historical data.
- Evaluation with Return, Win Rate, Max Drawdown, and Number of Trades.
- At least Random Search.
- Top-K Leaderboard.
- Buy/Sell and Entry/Exit visualization.
- News pipeline: Collect -> Store -> Analyze sentiment.
- Strategy versioning and reproducible experiments.
- Stop conditions for continuous search.
- Architecture views: System Context, container/module decomposition,
  component responsibilities, Data Flow, Realtime Flow, Strategy Flow, and
  Search/Backtest Flow.
- Explanations for modifiability, scalability, realtime, reliability,
  performance, maintainability, observability, and reproducibility.

Advanced items in the original assignment include Genetic Search, Bayesian
Optimization, Agent-based Search, LLM-generated strategy, full SMC/Wyckoff,
market prediction, and more complex infrastructure. These are not automatically
MVP unless `note.txt` promotes them.

### 3.2 Supplemental teacher requirements in `note.txt`

The note adds or emphasizes:

- Select a single or combined strategy.
- Manual strategy composition.
- Automatic Loop Discovery that combines strategies, evaluates candidates, and
  displays the best variants on the Leaderboard.
- Add a strategy using natural language or a URL.
- Generate a draft for the user to review before code generation.
- Generate a Python strategy file.
- Consider a repair loop because generated code may fail on the first attempt.
- Backtest inputs: pair/coin, date range, investment, and single/combined strategy.
- Trade output: pair, entry time, LONG/SHORT, USD weight/notional, entry price,
  Stop Loss, Take Profit, exit price, transaction cost, spread/slippage, and
  profit.
- Statistics: Win Rate, wins, losses, total profit, and Max Drawdown.
- Visualization on the graph.
- News crawling that remains resilient when a website changes its HTML tree,
  using LLM assistance if needed.
- Realtime chart bootstrap with 1,000 historical candles for each timeframe and
  correct handling of the current provisional candle when it matches or follows
  the last historical candle.
- MA, Bollinger Bands, SMC, and additional strategies.
- Advanced LLM-based market analysis.

These supplemental requirements should be tagged `[SRC-ADD]` in proposal and
traceability documents. They must not be mislabeled as team-invented `[PD]`
requirements.

## 4. Blueprint audit result

### 4.1 What is already strong

The blueprint broadly covers and often exceeds the original assignment:

- Market adapter abstraction and normalized Candle/BBO contracts.
- Historical loading, realtime provisional candles, closed-candle persistence,
  reconnect/backfill, checkpointing, de-duplication, and provider rate limiting.
- Four independent chart panels and per-panel subscriptions.
- Plugin Registry and metadata-driven UI/search integration.
- Manual composites with majority and weighted policies.
- Async experiment creation, PostgreSQL-backed jobs, worker leases, takeover,
  idempotency, and transactional outbox.
- Backtest, evaluation, ranking, Top-K, provenance, immutable datasets, and
  reproducibility.
- News and sentiment separation.
- Failure isolation, observability, quota, and security controls.
- Existing AI authoring sequence: text/URL -> declarative StrategySpec ->
  validation -> preview -> human approval.

The current AI authoring design is safe because LLM output is data, not directly
executed code. It is a valid MVP foundation.

### 4.2 Critical inconsistency: Go/Python ownership

The top-level target architecture says the Python `research` platform owns:

- Strategy Registry and Strategy Runtime.
- Indicators and composite strategies.
- Backtest and worker execution.
- Evaluation, search, ranking, and Leaderboard.
- Experiment/result persistence.
- News extraction/tagging and sentiment orchestration.
- AI strategy authoring.

However, several detailed sections still describe the old Go implementation:

- `blueprint/design.md` section 8.1 contains a Go Strategy Registry and Go MACD
  plugin paths.
- `blueprint/design.md` section 11.1 says "Python plugin" but shows
  `server/internal/domain/strategy/plugins/*.go`.
- `blueprint/specs/strategy-registry.md` is primarily a Go interface and Go
  implementation.
- `blueprint/specs/backtest.md` uses Go contracts, Go workers, Decimal, and Go
  plugins.
- `blueprint/specs/search-loop.md` describes Go CandidateGenerator implementations.
- `blueprint/specs/news.md` contains old Go worker/parser ownership, then appends a
  Python target-additions section.
- `blueprint/proposal.md` still contains old image/workload language such as a Go
  Strategy Service.
- `blueprint/README.md` contains legacy statements about Go domain writes and a
  trusted Go plugin boundary.

This contradiction is the highest-priority documentation problem. If left in place,
the team can build two strategy runtimes and lose parity and reproducibility.

### 4.3 Agent gap

`blueprint/specs/strategy-authoring.md` and diagram 21 implement a safe authoring
pipeline, but they do not satisfy the full supplemental requirement when Python code
generation and repair are mandatory.

Missing elements include:

- Generated Python artifact lifecycle.
- Code/spec compile and validation evidence.
- An isolated execution sandbox.
- Bounded repair attempts.
- State machine and crash recovery.
- Model/prompt/compiler/sandbox provenance.
- Artifact hash and test report persistence.
- Promotion rules from draft to approved strategy version.
- A distinction between safe DSL-backed strategy and arbitrary custom Python.

### 4.4 News extraction gap

The current news target supports safe HTML fetch, readability extraction, LLM
tagging, and content-hash caching. It does not explicitly implement the supplemental
requirement for LLM-assisted extraction when deterministic parsing fails because the
HTML tree changed.

The required fallback is:

```text
Safe HTML Fetch
  -> Deterministic Readability Extractor
  -> Content Quality Gate
       -> pass: normalize
       -> fail: Structured LLM Extraction
  -> Schema and quality validation
  -> Content-hash cache
  -> Tagging
  -> Sentiment
```

The LLM extractor must only receive previously fetched and sanitized content. It must
not receive an unrestricted URL-fetching or browser tool.

### 4.5 Result contract gaps

The visualization spec is close but not perfectly aligned with `note.txt`:

- The trade response contains `quantity`, fee, and slippage, but no explicit USD
  notional for each trade.
- The JSON example contains `sl_price` and `tp_price`, but the TypeScript `Trade`
  interface shown later omits them.
- `fixed_notional` exists in the experiment snapshot, but the table requirement asks
  for the USD amount per trade.
- Pair/coin can be obtained from experiment context, but should be explicitly present
  in the view model or clearly joined by the UI.
- `risk_policy = NULL` means SL/TP may be absent; the UI and API need an explicit null
  contract.

Recommended fields include `symbol`, `quote_currency`, `entry_notional`,
`exit_notional`, `sl_price`, `tp_price`, `fee_paid`, `spread_cost`,
`slippage_cost`, `gross_pnl`, and `net_pnl`.

### 4.6 Smaller requirement clarifications

- Market Data currently defines a maximum of 1,000 candles per public response.
  The supplemental note expects the initial chart bootstrap to request the most recent
  1,000 closed candles, then merge the current provisional candle by open time.
- SMC is currently an admitted future plugin rather than an implemented MVP plugin.
  If the teacher intends `note.txt` to require an SMC demonstration, scope and
  acceptance criteria must change.
- Advanced LLM market analysis is not currently a separate bounded component. It
  should remain optional and read-only unless explicitly promoted into an approved
  versioned strategy.

## 5. Locked architecture decisions

These decisions reflect the user's latest explicit direction.

### 5.1 Go boundary

Go owns only API/edge and Market Data responsibilities:

- Public REST and WebSocket boundary.
- Authentication, authorization, quota, rate limiting, CORS, error mapping, and
  correlation IDs.
- Binance/market-provider adapters.
- Historical candle loading.
- Realtime Candle/BBO normalization.
- Provisional candle fan-out.
- Closed-candle persistence, stream checkpoints, reconnect, backfill, and market
  provider rate limiting.
- Proxying signed internal commands to Python.
- Receiving persisted Python progress/result notifications and broadcasting them to
  web clients.

Go does not own strategy, backtest, search, ranking, news, sentiment orchestration,
agent workflow, or their domain tables.

### 5.2 Python `research` boundary

Python `research` owns:

- Strategy catalog, Registry, Runtime, and versioning.
- Indicator library and overlays derived from strategy data.
- Composite policies.
- Strategy authoring and agent orchestration.
- Experiment snapshots and job creation.
- Python worker execution.
- Backtest, trade facts, equity, and evaluation.
- Search generators, search state, and Candidate Discovery extension.
- Ranking and Leaderboard.
- News collection/extraction/tagging orchestration.
- Sentiment orchestration through the internal AI adapter.
- Agent, artifact, sandbox, and approval persistence.

The Python worker is a second workload of the same `research` image/package, not a
separate source tree or independently implemented engine.

### 5.3 AI/LLM adapter boundary

The AI/LLM adapter:

- Is internal-only.
- Does not expose browser-facing endpoints.
- Does not own workflow state.
- Does not write domain tables.
- Does not approve or publish strategies.
- Performs structured model inference requested by `research`.
- May support sentiment, StrategySpec generation, repair proposals, news extraction,
  news tagging, candidate proposals, and market insights through versioned adapters.

### 5.4 Database ownership

A single PostgreSQL instance is acceptable, but write ownership must be explicit:

- Go-owned: market pairs, market cache candles, BBO/market events, stream
  checkpoints, auth/session/edge data.
- Python-owned: strategy definitions/versions/drafts, agent runs, artifacts,
  experiments, jobs, runs, trades, signals, equity, evaluations, ranking,
  Leaderboard, news, tags, sentiment, and agent evidence.

For the MVP, prefer a stable internal Python API instead of allowing Go to depend on
many Python domain tables through direct read projections. Browser traffic still uses
one public Go API.

## 6. Canonical target topology

```text
Browser
  -> HTTPS/WSS
Go API and Market Gateway
  -> Binance/market providers
  -> Go-owned market/auth tables
  -> signed internal API and normalized market stream
Python Research Platform
  -> Python-owned domain tables
  -> Python Worker x N
  -> internal AI/LLM Adapter

Python persisted event/outbox
  -> Go POST /internal/events
  -> Go WebSocket fan-out
  -> Browser
```

Important flow rules:

- The browser only knows the public Go API contract.
- Python does not open Binance connections.
- Go does not calculate strategy signals, PnL, evaluation, or rank.
- Realtime and backtest resolve the same immutable StrategySpec/version and use the
  same Python Strategy Runtime.
- Python event notifications sent to Go are for fan-out; critical state is persisted
  before notification.

## 7. Agent architecture decision

### 7.1 Deployment model

Use one deterministic `AgentOrchestrator` and up to six logical agent roles.

The six roles are prompt/model profiles and handlers inside Python `research`; they
are not six containers or microservices. They share a `ModelGateway`, `ToolRegistry`,
state store, permission policy, and observability.

Required for the supplemental requirement:

1. `StrategyDesignerAgent`
2. `StrategyImplementationAgent`
3. `StrategyRepairAgent`
4. `NewsExtractionAgent`

Optional extensions:

5. `CandidateDiscoveryAgent`
6. `MarketInsightAgent`

The following are deterministic services or simple model adapters, not agents:

- Agent Orchestrator.
- StrategySpec Validator.
- Python compiler.
- AST/policy checker.
- Sandbox runner.
- Backtest Engine and Evaluator.
- Random and Domain-Guided Search generators.
- Human review and Approval Service.
- News tagger.
- Sentiment analyzer.

### 7.2 Strategy authoring flow

```text
Text / URL / DSL
  -> Safe Source Ingestor
  -> StrategyDesignerAgent
  -> StrategySpec schema and semantic validation
  -> StrategyImplementationAgent
  -> deterministic Python compiler or custom-code draft
  -> AST/policy checker
  -> isolated sandbox contract and fixture tests
  -> on failure: StrategyRepairAgent, bounded attempts
  -> on pass: REVIEW_REQUIRED
  -> human approval
  -> immutable StrategyVersion
  -> Strategy Registry
```

### 7.3 Two authoring modes

#### Mode A: DSL-backed strategy - default/MVP

- LLM creates declarative `StrategySpec`.
- The system compiler deterministically creates Python from allowlisted constructs.
- Repair updates the spec, then regenerates the artifact.
- Approved specs can become dynamically available through the Strategy Runtime
  without loading arbitrary code.
- Realtime and backtest use identical semantics.

#### Mode B: Custom Python - advanced

- Used only when the DSL cannot express a strategy such as a complex SMC method.
- LLM may propose or repair Python source in an isolated workspace.
- The artifact must pass policy and sandbox tests.
- It cannot be hot-loaded into the running production Registry.
- Human approval produces a patch/PR/build/deploy flow.
- Registry loads the trusted, reviewed plugin on startup after deployment.

### 7.4 Agent state machine

```text
DRAFT_CREATED
  -> SOURCE_READY
  -> SPEC_GENERATING
  -> SPEC_VALIDATING
  -> CODE_GENERATING
  -> POLICY_CHECKING
  -> SANDBOX_TESTING
       -> fail and repair budget remains: REPAIRING -> CODE_GENERATING
       -> fail and repair budget exhausted: FAILED
       -> pass: REVIEW_REQUIRED
            -> human approves: APPROVED -> PUBLISHED
            -> human rejects: REJECTED
```

All transitions must be persisted and idempotent. A worker restart must not lose the
draft, duplicate a repair attempt, or publish an artifact twice.

### 7.5 Required agent persistence

At minimum, design these entities:

- `strategy_drafts`: owner, source type, source hash, current spec, status.
- `agent_runs`: agent type, model, prompt, budget, status, timestamps.
- `agent_attempts`: attempt number, input hash, output hash, structured error.
- `strategy_artifacts`: source, language, artifact hash, compiler version.
- `sandbox_runs`: image digest, policy version, test report, duration, resource use.
- `strategy_versions`: approved spec/artifact fingerprint and immutable provenance.
- Optional `authoring_sessions` and `authoring_messages` when the UI exposes a
  multi-turn authoring chat.

## 8. Agent roles and allowed tools

### 8.1 StrategyDesignerAgent

Purpose: convert natural language, URL-derived text, or DSL input into a valid
declarative StrategySpec.

Allowed tools:

- `source.get_document`
- `strategy.get_catalog`
- `strategy.get_dsl_schema`
- `strategy.validate_spec`
- `strategy.get_validation_errors`
- `strategy.save_draft_spec`

Forbidden capabilities:

- Arbitrary HTTP.
- Shell.
- SQL.
- Source-tree access.
- Direct backtest execution.
- Approval or publishing.

### 8.2 StrategyImplementationAgent

Purpose: produce a Python artifact from a validated StrategySpec or create an
advanced custom-code draft.

Allowed tools:

- `artifact.compile_from_spec`
- `artifact.create_custom_draft`
- `artifact.run_policy_check`
- `artifact.save_version`
- `sandbox.run_contract_tests`
- `sandbox.get_test_report`
- `draft.mark_review_required`

The preferred path is `compile_from_spec`. Custom Python is a separate advanced
path with stricter publishing rules.

### 8.3 StrategyRepairAgent

Purpose: consume structured validation/compile/test failures and propose a bounded
spec or code patch.

Allowed tools:

- `agent.get_attempt_context`
- `sandbox.get_test_report`
- `strategy.apply_spec_patch`
- `artifact.apply_code_patch`
- `strategy.validate_spec`
- `artifact.run_policy_check`
- `sandbox.run_contract_tests`
- `draft.mark_failed`

The orchestrator, not the agent, enforces the repair-attempt budget. The Repair Agent
cannot modify fixtures, disable tests, relax policy, raise its own budget, approve, or
publish.

### 8.4 NewsExtractionAgent

Purpose: recover structured news content when deterministic extraction fails the
quality gate after a safe fetch.

Allowed tools:

- `document.get_sanitized_html`
- `document.get_extraction_errors`
- `news.get_item_schema`
- `news.validate_extraction`
- `news.save_extraction`

The agent is not allowed to fetch arbitrary URLs. The deterministic Safe Fetcher owns
all network access and SSRF controls.

### 8.5 CandidateDiscoveryAgent - optional

Purpose: propose new CandidateStrategy DSL values based on search history and
Leaderboard summaries.

Allowed tools:

- `search.get_search_space`
- `search.get_tested_hashes`
- `leaderboard.get_summary`
- `candidate.validate`
- `candidate.estimate_cost`
- `candidate.submit_batch`

It cannot call the Backtest Engine directly, write the Leaderboard, bypass quota, or
control the search stop condition. `candidate.submit_batch` enters the normal bounded
queue pipeline.

Required provenance includes generator ID/version, model version, prompt version,
input-history hash, and candidate hash.

### 8.6 MarketInsightAgent - optional

Purpose: create a read-only research insight, not a trade command.

Allowed tools:

- `market.get_snapshot`
- `indicator.get_snapshot`
- `news.get_recent_summary`
- `experiment.get_recent_results`
- `insight.save_draft`

Its output contains symbol, timeframe, data timestamp, regime, observations, risks,
confidence, and model version. It must not directly return an executable order, publish
a strategy, or enter the search space. Converting an insight into a strategy must go
through normal authoring, testing, and approval.

## 9. Tool architecture

### 9.1 Tool invocation contract

Every tool must have:

- A stable name and version.
- JSON input and output schemas.
- Principal and agent-run context.
- Deadline and cancellation.
- Idempotency key for writes.
- Permission declaration.
- Structured error codes.
- Audit log and metrics.
- An evidence/reference ID for large reports.

Suggested shared invocation context:

```json
{
  "principal_id": "user-id",
  "agent_run_id": "run-id",
  "correlation_id": "request-id",
  "deadline": "timestamp",
  "idempotency_key": "key",
  "remaining_budget": {
    "tool_calls": 10,
    "repair_attempts": 2
  }
}
```

Suggested result envelope:

```json
{
  "ok": true,
  "data": {},
  "error": null,
  "evidence_ref": "evidence-id",
  "tool_version": "v1"
}
```

### 9.2 Tools that must never be exposed to an agent

- Generic shell execution.
- Generic SQL queries.
- Arbitrary HTTP fetch.
- Unrestricted filesystem writes.
- Arbitrary Docker/container execution.
- Secret access.
- Direct Registry publishing.
- Test-fixture modification.
- Policy or budget modification.

Agents receive narrow domain tools; deterministic services enforce all security and
correctness boundaries.

## 10. Tool implementation inventory

### 10.1 P0: shared agent platform - implement new

- `AgentOrchestrator`
- `ToolRegistry`
- `ModelGateway`
- `AgentPermissionPolicy`
- `AgentBudgetManager`
- `AgentRunRepository`
- `AgentAttemptRepository`
- Agent progress/event publisher
- Idempotent agent state-transition service
- Tool audit and metrics middleware

### 10.2 P0: strategy authoring and repair - implement new

- Safe Source/Document Fetcher for authoring URLs
- StrategySpec schema service
- StrategySpec semantic validator
- StrategySpec deterministic Python compiler
- Python AST/import policy checker
- Isolated Sandbox Runner
- Contract-test suite for generated strategies
- Artifact Repository
- Sandbox Report Repository
- Approval Service
- Strategy Publisher
- Authoring endpoints
- Agent run/status endpoints
- UI draft/preview/repair/review states

### 10.3 Existing Python capabilities to wrap as tools

The repository already contains reusable Python seams under `app/`:

- `app/domain/strategy/registry.py`
- `app/domain/strategy/contract.py`
- `app/domain/strategy/plugins/`
- `app/services/backtest_engine.py`
- `app/services/evaluator.py`
- `app/services/search.py`
- `app/services/ranking.py`
- Python domain/port abstractions for strategy, backtest, search, evaluation,
  ranking, news, and sentiment

Wrap these application services through typed tools. Do not give agents direct module,
database, or source-code access.

### 10.4 P1: adaptive news extraction - implement

- Deterministic Readability Extractor
- Content Quality Gate
- NewsExtractionAgent handler
- News extraction schema validator
- Content-hash/model/prompt cache
- Structured news-tagging model adapter
- Extraction failure evidence and metrics

### 10.5 P2: optional extensions

- CandidateDiscoveryAgent
- Candidate cost estimator
- Agent-generated candidate provenance
- MarketInsightAgent
- Market/indicator/news snapshot tools
- Insight persistence and UI

## 11. Go/Python internal contracts

Python agents and domain services must not call the public Go API through a loopback
path. Go should expose a small authenticated internal market contract, for example:

- `GET /internal/market/candles`
- `GET /internal/market/bbo-snapshot`
- A normalized internal market event stream
- `POST /internal/events` for Python progress/result notifications to Go
- Signed principal context on Go-proxied domain commands

Agents do not call these endpoints directly. Python implements `MarketDataPort`, and
the infrastructure adapter calls Go. Agent-facing tools call the Python application
port.

Public request example:

```text
Browser
  -> POST /api/v1/strategy-drafts on Go
  -> Go auth/quota/body validation
  -> signed internal POST to Python research
  -> Python creates draft and AgentRun
  -> Python worker advances the workflow
  -> Python persists progress
  -> Python POST /internal/events to Go
  -> Go broadcasts progress by WebSocket
```

## 12. Sandbox policy

Generated Python may only run in an isolated disposable environment with:

- Non-root identity.
- No network.
- No database.
- No exchange or application credentials.
- No package installation.
- Import allowlist.
- Read-only base filesystem.
- One bounded writable workspace.
- CPU, memory, output-size, and wall-clock limits.
- Process and syscall restrictions appropriate to the runtime.
- Deterministic fixture inputs.
- Structured test output.
- A persisted sandbox image digest and policy version.

Required test categories:

- Import and contract conformance.
- Parameter-schema validation.
- Signal action/price/size validation.
- No database/network/file-system dependency.
- No future candle or indicator access.
- Determinism on repeated identical input.
- Bounded execution and timeout behavior.
- Error isolation.
- Realtime/backtest parity for the same StrategySpec/version.
- Preview fixture output suitable for human review.

Suggested repair budget is two or three attempts. The exact number is a team NFR and
must be configurable and recorded, but never controlled by the agent.

## 13. Search and discovery policy

Random Search remains mandatory MVP functionality. Domain-Guided Search remains a
deterministic replaceability demonstration.

Agent-based discovery is an optional `CandidateGenerator` adapter. It may only output
validated CandidateStrategy DSL values. It must:

- Respect the search space.
- Use tested hashes for de-duplication.
- Respect candidate/run and worker-cost quotas.
- Persist model/prompt/history provenance.
- Submit candidates through the standard queue.
- Leave stop conditions under SearchRun control.
- Leave backtesting, evaluation, and ranking unchanged.

## 14. Realtime 1,000-candle behavior to specify

The market/chart design should explicitly say:

1. Opening or changing a chart requests the most recent 1,000 closed candles for its
   provider, symbol, and timeframe.
2. The chart subscribes to the matching realtime stream.
3. If the provisional candle has the same `open_time` as the last displayed candle,
   replace/update that candle in memory.
4. If it has a newer `open_time`, append it as the current provisional candle.
5. When `Final=true`, convert it to the closed representation, persist it, and start a
   new provisional candle on the next open time.
6. De-duplicate by `(provider, symbol, timeframe, open_time)`.
7. Changing one panel cancels/replaces only that panel's subscription and history
   request.

## 15. Documentation changes required

### 15.1 `blueprint/design.md`

Update:

- Service Boundary and Ownership.
- C4 L2/L3 explanations.
- High-Level Architecture.
- Database ownership and internal API boundaries.
- Plugin Registry section to Python.
- Backtest/search/worker examples to Python.
- ADR-011 and topology language.
- The answer for adding MACD to show `app/domain/strategy/plugins/macd.py`.
- Repository tree.
- Target gap/invariant list.
- Agent workflow, state machine, sandbox, repair, approval, and publishing.

Remove or explicitly archive:

- Go Strategy Service.
- Go Backtest Worker.
- Go Strategy plugins.
- `server/internal/domain/strategy` as the canonical runtime.
- Go CandidateGenerator ownership.
- Go news-domain ownership.

### 15.2 Specs to rewrite as Python canonical

- `blueprint/specs/strategy-registry.md`
- `blueprint/specs/backtest.md`
- `blueprint/specs/search-loop.md`
- `blueprint/specs/experiment.md`
- `blueprint/specs/evaluation.md`
- `blueprint/specs/leaderboard.md`
- `blueprint/specs/visualization.md`
- `blueprint/specs/news.md`
- `blueprint/specs/sentiment.md`

Keep Go canonical for:

- `blueprint/specs/market-data.md`
- Public/internal API transport.
- Auth, quota, CORS, request validation, and WebSocket fan-out.
- Chart subscription transport; indicator calculation remains Python-owned.

### 15.3 Agent documents

- Add `blueprint/specs/agent-architecture.md` for orchestration, roles, tools,
  state machine, persistence, sandbox, permissions, budgets, and observability.
- Expand `blueprint/specs/strategy-authoring.md` for Python artifact generation,
  policy checks, sandbox tests, repair, evidence, approval, and publishing.

### 15.4 Diagrams

Update at least:

- `02-c4-l2-container`
- `03-c4-l3-python-strategy-platform`
- `04-high-level-architecture`
- `11-search-backtest-pipeline`
- `13-news-html-llm-pipeline`
- `17-python-worker-execution`
- `21-ai-strategy-authoring`

Add a dedicated Agent component/state diagram if the existing sequence becomes too
dense. The diagram should show Agent Orchestrator, Model Gateway, Tool Registry,
Spec Validator, Compiler, Policy Checker, Sandbox Runner, Repair Agent, human approval,
Artifact Store, and Strategy Registry.

### 15.5 Proposal and traceability

- Replace old Go Strategy Service language.
- Describe the four target images/workloads consistently: web, Go API/Market,
  Python research API/worker, and internal AI inference.
- Add `[SRC-ADD]` entries for every supplemental teacher requirement.
- Map each supplemental requirement to spec, diagram, acceptance criteria, and demo.
- Distinguish DSL-backed MVP authoring from custom-Python advanced authoring.
- Clarify whether SMC implementation is required or only architectural admission.

### 15.6 Result and UI contract

- Add per-trade USD notional fields.
- Add missing `sl_price` and `tp_price` to the TypeScript `Trade` contract.
- Make fee, spread, and slippage breakdown explicit.
- Define gross and net PnL.
- Define the symbol/currency join in the result view model.
- Define null behavior when SL/TP is disabled.
- Add API/schema/UI acceptance tests matching the exact `note.txt` columns.

## 16. Recommended implementation order

1. Reconcile all Go/Python ownership documentation.
2. Make Python `research` the only canonical strategy/backtest/search/news runtime.
3. Update C4 and high-level diagrams.
4. Add Agent Orchestrator, state model, tool contract, and persistence design.
5. Implement safe DSL-backed authoring first.
6. Implement deterministic compiler, policy checker, sandbox, and bounded repair.
7. Add human review and immutable publishing.
8. Add adaptive news extraction fallback.
9. Close realtime 1,000-candle and trade-output contract gaps.
10. Add Candidate Discovery and Market Insight only after MVP gates pass.

## 17. Acceptance gates for the agent feature

The blueprint should not claim the agent flow complete until all of these are
demonstrable:

- Text input creates a valid draft StrategySpec.
- Approved URL input is fetched safely and produces a content hash.
- Prompt-injection text cannot grant tools or bypass validation.
- Generated Python artifact has an immutable hash and compiler/model provenance.
- Policy violations fail before runtime.
- Sandbox has no network, DB, secrets, or unrestricted filesystem.
- A failing fixture produces a structured failure report.
- Repair is bounded and persisted across worker restarts.
- Test pass leads to `REVIEW_REQUIRED`, not automatic publishing.
- Rejection prevents Registry visibility.
- Approval publishes exactly the reviewed spec/artifact hash.
- Re-approval is idempotent or returns a clear conflict.
- Realtime and backtest use the same approved StrategySpec/version.
- Agent/tool/model/sandbox activity is observable and auditable.
- News LLM fallback runs only after deterministic extraction fails its quality gate.
- Candidate Discovery cannot bypass quota, queue, or stop conditions.

## 18. Current implementation observations

At audit time:

- Python strategy code exists under `app/domain/strategy/`.
- Python plugins include MA/EMA cross, RSI, Bollinger, Support/Resistance,
  News Sentiment, MACD, and a composite root through the catalog.
- Python search services include Grid, Random, and Domain-Guided generation.
- The repository search found no implemented `StrategyAuthoringService`,
  `strategy_drafts` runtime flow, repair workflow, or sandbox implementation in
  `app/`, `ai/`, `server/`, migrations, tests, or web code.
- The blueprint therefore describes authoring as a target gap, not a completed
  runtime feature.

Do not confuse a detailed blueprint acceptance checklist with implemented evidence.
Implementation claims require real tests, fixtures, and demo results.

## 19. Decisions that remain open

The following need explicit user/team confirmation before implementation scope is
locked, although the architecture already supports either choice:

- Whether full SMC is required for the final demo or only plugin extensibility proof.
- Whether custom arbitrary Python generation is mandatory, or deterministic Python
  generated from StrategySpec is sufficient.
- Whether approved DSL strategies must become available without redeploy.
- The exact repair-attempt, model-token, time, CPU, and memory budgets.
- Which URL origins are allowed for user-submitted strategy articles.
- Whether Agent-based Candidate Discovery is part of final delivery or only target
  architecture.
- Whether MarketInsightAgent is part of the UI or stays outside MVP.

Until clarified, use these defaults:

- DSL-backed strategy generation is MVP.
- Custom Python is advanced and requires review/build/deploy.
- Repair attempts are bounded at three.
- SMC is architecture-supported but not fully implemented.
- Candidate Discovery Agent and Market Insight Agent are extensions.
- All authoring URLs pass through an explicit allowlist and Safe Fetcher.

## 20. Handoff status

Completed in the conversation before this file:

- Read and visually inspected the assignment PDF.
- Read `requirements.html` and `note.txt`.
- Audited the main blueprint, traceability, diagrams, and relevant specs.
- Identified the Go/Python ownership contradiction.
- Identified the missing generated-Python/repair agent architecture.
- Proposed the canonical Go API/Market vs Python Research split.
- Defined six logical agent roles and their allowed tools.
- Defined required tool implementation groups and sandbox constraints.

Completed in the subsequent blueprint-update pass (documentation only):

- Reconciled canonical ownership: Go is limited to Public API/Edge and Market
  Data; Python `research` owns Strategy, Backtest, Evaluation, Search, Ranking,
  News/Sentiment orchestration and the Agent Platform.
- Updated the blueprint overview, proposal, design, Go checklist, traceability,
  Jira backlog and the affected domain specifications. Legacy alternatives are
  marked as archived rather than presented as target architecture.
- Added the canonical Agent Platform specification, including the deterministic
  orchestrator, six logical agent roles, typed tool contracts, permissions,
  budgets, persistence, sandbox, approval and publishing gates.
- Updated agent authoring and adaptive-news specifications for deterministic
  DSL compilation, advanced custom-code review, bounded repair, and the
  quality-gated sanitized-HTML fallback.
- Added Mermaid diagrams 25--33 for the overall platform, state machine, each
  agent role and the tool-security boundary; updated core diagrams 02, 03, 04,
  06, 13, 14 and 21; rendered every one of the 33 diagrams as SVG and PNG.
- Verified documentation links, diagram-source/catalog counts and Mermaid
  rendering. These are documentation-artifact checks, not runtime evidence.

Not yet performed:

- No agent runtime, tool implementation, database migration, API, UI, sandbox, or
  tests have been implemented.
- No runtime acceptance evidence has been produced for the new agent
  requirements; statuses that describe implementation remain Designed/Planned.

The next implementation task should use this file as the canonical resume source,
start with the P0 persistence/tool/state-machine contracts, and implement the
DSL-backed authoring path before custom Python, optional discovery or insight work.
