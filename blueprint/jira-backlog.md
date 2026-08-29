# Crypto Strategy Lab — Canonical Delivery Backlog

> Blueprint v1.5. Đây là backlog thiết kế; `Planned` không có nghĩa đã implement. Requirement ID tham chiếu `traceability.md`.

## Delivery boundaries

| Stream | Owner | In scope | Explicitly out of scope |
| --- | --- | --- | --- |
| GO | Go API/Market | Public REST/WSS, auth/RBAC/quota/CORS/error/correlation, provider REST/WSS, normalized Candle/BBO, history/provisional/closed persistence, checkpoint/reconnect/backfill, internal market contract, Python-event fan-out | Strategy, indicator, experiment, backtest, search, ranking, news, sentiment, agent, Python-domain tables |
| PY | Python `research` | Strategy Runtime/Registry, indicators/composite, experiment/jobs/worker, backtest/evaluation/search/ranking/Leaderboard, news/sentiment orchestration, Agent Platform | Binance/provider connection, public browser edge, model hosting |
| AI | Internal `ai` adapter | Versioned structured inference | Workflow state, tools, domain DB, crawl/fetch, approval/publish |
| WEB | Next.js | Render/API client, four independent panels, authoring/review/progress/results | Domain calculation, direct Python/AI access |
| QA/OPS | Cross-cutting | Contracts, migrations/grants, sandbox image/policy, observability, test/demo/benchmark evidence | Marking a requirement verified without an artifact |

## Priority map

- **P0 / final-project core:** boundary reconciliation, Go Market/API, Python runtime, exact backtest/result contract, Random Search/Leaderboard, four-panel 1.000-candle bootstrap, DSL-backed strategy authoring with Designer/Implementation/Repair, sandbox + human approval.
- **P1:** adaptive news extraction with `NewsExtractionAgent`.
- **P2 / optional-default-off:** `CandidateDiscoveryAgent`, `MarketInsightAgent`, custom Python publishing path, full SMC implementation.

## P0 epics and stories

### ARCH-01 — Enforce Go/Python/AI ownership

- **Status:** Planned
- **Requirements:** P01–P03
- **Depends on:** none
- **Scope:** architecture tests, DB roles/grants, signed Go→Python internal contract, Python→Go `/internal/events`, production network exposure.
- **Acceptance:**
  - Go build has no strategy/backtest/search/ranking/news/agent package or Python-domain repository.
  - Browser cannot reach `research` or `ai`; Go cannot write/read Python base tables.
  - Signed principal/scopes/correlation/deadline reach Python; Python rechecks ownership.
  - Python commits state + outbox before fan-out notification; duplicate event is idempotent.
- **Refs:** `design.md` §1.2, ADR-011/016; `specs/python-research.md`; diagrams 02–04, 14, 33.

### GO-01 — Public API, auth and Market Data Gateway

- **Status:** Partial
- **Requirements:** R01, R02, A08, P01
- **Depends on:** ARCH-01
- **Scope:** Binance REST/combined WSS, normalization, REST weight limiter, Candle/BBO boundaries, closed persistence/checkpoint, reconnect/backfill, public history, per-panel subscription, WebSocket fan-out.
- **Acceptance:**
  - Exactly 1.000 most-recent closed candles on panel bootstrap.
  - Provisional candle with equal `open_time` replaces; newer appends; final closes/persists once.
  - Forced disconnect recovers by checkpoint + overlap-safe REST backfill with no missing/duplicate closed candles.
  - Raw Binance payload never crosses adapter; BBO does not become candle data.
  - Changing panel 1 does not request, subscribe or render panel 2–4.
- **Refs:** `specs/market-data.md`, `go-review-checklist.md`; diagrams 05, 09, 20.

### PY-01 — Canonical Strategy Runtime and plugin catalog

- **Status:** Partial
- **Requirements:** R03, R04, A09, P02
- **Depends on:** ARCH-01
- **Scope:** Strategy Protocol/Definition/Registry, causal context, indicator library, MA/RSI/Bollinger/S-R, composites, metadata-driven catalog/form/search, runtime parity.
- **Acceptance:** no literal strategy branching; plugin purity/no-lookahead tests; same approved spec/version/fingerprint drives preview/realtime/backtest; MACD add proof does not change core.
- **Refs:** `specs/strategy-registry.md`, `specs/composite-strategy.md`; diagrams 03, 10, 22.

### PY-02 — Experiment, backtest, evaluation and exact result facts

- **Status:** Partial
- **Requirements:** R05, R06, R09, R11, A04–A06
- **Depends on:** PY-01, GO-01
- **Scope:** immutable ExperimentSnapshot, job lease/heartbeat/takeover, BBO execution, one-net LONG/SHORT, risk/cost policies, facts/evaluation/provenance and result query DTO.
- **Acceptance:**
  - Create snapshot + candidate/job atomically; worker restart never double-counts.
  - BUY uses ask, SELL uses bid; no future candle; deterministic rerun.
  - Trade DTO/UI has `symbol`, `quote_currency`, entry/exit time, side, quantity, entry/exit notional, prices, nullable SL/TP, fee/spread/slippage, gross/net PnL.
  - Wins/losses/total profit/Win Rate/Max Drawdown reconcile to immutable facts.
- **Refs:** `specs/experiment.md`, `specs/backtest.md`, `specs/evaluation.md`, `specs/visualization.md`; diagrams 16–19, 23, 24.

### PY-03 — Bounded Search and Leaderboard

- **Status:** Partial
- **Requirements:** R07, R08, R12, A01
- **Depends on:** PY-02
- **Scope:** Random + Domain-Guided CandidateGenerator, generator registry, dedup, quota/stop/pause/resume/cancel, bounded queue, evaluation-based ranking and Top-K provenance.
- **Acceptance:** seed determinism; candidate/time/no-improvement stop gates; no unbounded loop; generator cannot call backtest directly; scoring change does not rewrite facts; Leaderboard entry traces exact strategy/dataset/execution/evaluator/score versions.
- **Refs:** `specs/search-loop.md`, `specs/leaderboard.md`; diagrams 11, 12, 15, 24.

### AGT-01 — Shared Agent Platform

- **Status:** Planned
- **Requirements:** P04
- **Depends on:** ARCH-01
- **Scope:** deterministic `AgentOrchestrator`, `ModelGateway`, `ToolRegistry`, permission/budget/audit middleware, run/attempt repositories, event publisher and idempotent transitions.
- **Implement:**
  - `strategy_drafts`, `agent_runs`, `agent_attempts`, `strategy_artifacts`, `sandbox_runs` persistence.
  - Versioned invocation/result envelopes with principal, run, correlation, deadline, idempotency and evidence reference.
  - Stable errors: validation/policy/sandbox/model/tool/budget/conflict/permission/cancelled.
- **Acceptance:** role allowlist denies undeclared tool; generic shell/SQL/HTTP/filesystem/secret/publish/policy/budget tools do not exist; retry cannot duplicate attempt/transition; model output cannot grant authority.
- **Refs:** `specs/agent-architecture.md`; diagrams 25, 26, 33.

### AGT-02 — Strategy Designer Agent and safe source ingestion

- **Status:** Planned
- **Requirements:** A02, P04–P05
- **Depends on:** AGT-01, PY-01
- **Tools:** `source.get_document`, `strategy.get_catalog`, `strategy.get_dsl_schema`, `strategy.validate_spec`, `strategy.get_validation_errors`, `strategy.save_draft_spec`.
- **Acceptance:** text and allowlisted URL produce schema/semantic-valid draft; SSRF/DNS rebinding/redirect/size/content-type checks; prompt injection cannot add tools or publish; source/content/model/prompt hashes persist.
- **Refs:** `specs/strategy-authoring.md`, `specs/agent-architecture.md`; diagrams 21, 27, 33.

### AGT-03 — Strategy Implementation, policy and sandbox

- **Status:** Planned
- **Requirements:** A03, P05
- **Depends on:** AGT-02
- **Tools:** `artifact.compile_from_spec`, `artifact.create_custom_draft`, `artifact.run_policy_check`, `artifact.save_version`, `sandbox.run_contract_tests`, `sandbox.get_test_report`, `draft.mark_review_required`.
- **Implement:** deterministic StrategySpec compiler, AST/import policy checker, disposable non-root/no-network/no-secret sandbox, fixture/contract/determinism/parity tests, artifact/report repositories.
- **Acceptance:** DSL compile reproducible; violation fails before execution; sandbox limits CPU/RAM/time/output/fs/process; pass reaches only `REVIEW_REQUIRED`; custom Python cannot hot-load.
- **Refs:** diagrams 21, 28, 33.

### AGT-04 — Bounded Repair, review and immutable publishing

- **Status:** Planned
- **Requirements:** A03, P04–P05
- **Depends on:** AGT-03
- **Tools:** `agent.get_attempt_context`, `sandbox.get_test_report`, `strategy.apply_spec_patch`, `artifact.apply_code_patch`, validation/policy/sandbox tools, `draft.mark_failed`.
- **Acceptance:** orchestrator enforces default max 3 repair attempts; repair cannot alter fixtures/policy/budget or approve; restart resumes exactly once; rejection hides Registry version; approval publishes exactly reviewed spec/artifact hash and is idempotent/conflict-safe.
- **Refs:** diagrams 26, 29, 33.

### WEB-01 — Authoring, review, progress and exact results UI

- **Status:** Planned
- **Requirements:** R02, R08–R09, A01–A06, A08
- **Depends on:** GO-01, PY-02, PY-03, AGT-04
- **Scope:** four panels, draft/spec/evidence/repair/review screens, agent progress via Go WSS, search/Leaderboard, chart markers and exact trade columns.
- **Acceptance:** browser network targets Go only; pending/degraded/null states explicit; approval binds visible artifact hash; accessible keyboard/focus/error behavior; no indicator/PnL/ranking logic in TypeScript.

## P1 epic

### NEWS-01 — Adaptive news extraction and sentiment orchestration

- **Status:** Planned
- **Requirements:** R10, A07
- **Depends on:** AGT-01, ARCH-01
- **Flow:** Safe Fetch → Readability → Quality Gate → on failure `NewsExtractionAgent` with sanitized HTML → schema/quality validation → content-hash/model/prompt cache → tags → sentiment.
- **Tools:** `document.get_sanitized_html`, `document.get_extraction_errors`, `news.get_item_schema`, `news.validate_extraction`, `news.save_extraction`.
- **Acceptance:** agent has no fetch/arbitrary URL tool; deterministic pass never calls model; malformed extraction is not saved; DOM-change fixture recovers; AI-down leaves sentiment unavailable/null while collection persists.
- **Refs:** `specs/news.md`, `specs/sentiment.md`; diagrams 13, 30, 33.

## P2 optional epics

### DISC-01 — Candidate Discovery Agent

- **Status:** Optional / default-off
- **Requirements:** A01, P04
- **Depends on:** PY-03, AGT-01
- **Tools:** `search.get_search_space`, `search.get_tested_hashes`, `leaderboard.get_summary`, `candidate.validate`, `candidate.estimate_cost`, `candidate.submit_batch`.
- **Acceptance:** only validated DSL candidates; normal quota/dedup/queue/stop path; no direct backtest/Leaderboard write; generator/model/prompt/history/candidate provenance.
- **Refs:** diagram 31.

### INSIGHT-01 — Read-only Market Insight Agent

- **Status:** Optional / default-off
- **Requirements:** A10, P04
- **Depends on:** AGT-01, GO-01, NEWS-01
- **Tools:** `market.get_snapshot`, `indicator.get_snapshot`, `news.get_recent_summary`, `experiment.get_recent_results`, `insight.save_draft`.
- **Acceptance:** timestamped insight/provenance; cannot place order, publish strategy or submit candidate; strategy conversion restarts normal authoring/review flow.
- **Refs:** diagram 32.

### SMC-01 — Full SMC plugin/custom strategy

- **Status:** Optional until teacher confirms final-demo scope
- **Requirements:** A09
- **Depends on:** PY-01, AGT-04
- **Acceptance:** explicit SMC method/inputs/warm-up/causality; plugin + fixtures + no-lookahead + demo evidence. Architecture support alone must not be reported as implementation.

## Release evidence gate

Before changing any `Verified` field in `traceability.md` to `Yes`, attach the matching test report, demo capture, benchmark or immutable provenance record. Required release bundle includes architecture-boundary tests, Mermaid render check, API/tool schema tests, agent permission/sandbox/repair tests, reconnect/backfill test, deterministic backtest/search fixtures, exact UI result-contract test and dependency-down behavior.
