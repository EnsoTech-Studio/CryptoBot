# Kế hoạch cập nhật Blueprint - Agent Architecture và ranh giới Go/Python

Trạng thái: `DOCUMENTATION_UPDATED — RUNTIME_IMPLEMENTATION_PENDING`  
Ngày lập: 2026-08-26  
Phạm vi: tài liệu kiến trúc, specification, diagram, traceability và backlog  
Nguồn context bền vững: [`../PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md)  
Sơ đồ tham chiếu: [`agent-architecture-diagrams.html`](agent-architecture-diagrams.html)

> Cập nhật 2026-08-29: các thay đổi blueprint trong kế hoạch này đã được áp dụng và kiểm tra ở mức artifact (link, Mermaid source, SVG/PNG và catalog). Đây chưa phải bằng chứng rằng runtime agent đã được implement; các gate cần code, migration, sandbox và test vẫn giữ trạng thái pending.

## 1. Tóm tắt quyết định

Blueprint cần được sửa theo một đường kiến trúc duy nhất:

- Go chỉ sở hữu Public API/Edge và Market Data.
- Python `research` sở hữu Strategy, Backtest, Evaluation, Search, Ranking, News, Sentiment orchestration và toàn bộ Agent Platform.
- AI/LLM Adapter chỉ làm structured inference; không sở hữu workflow, không ghi domain DB, không approve/publish.
- Browser chỉ gọi Go. Go chuyển các domain command đã xác thực sang Python và fan-out các event đã được Python persist.
- Agent là sáu logical roles bên trong Python `research`, không phải sáu microservice/container.
- `AgentOrchestrator` là state machine deterministic, không phải agent.
- Authoring mặc định dùng DSL-backed `StrategySpec` rồi compile Python deterministic. Custom Python là advanced path, phải qua review/build/deploy và không hot-load.
- Mọi tool của agent phải hẹp, typed, versioned, permission-checked, audited và có budget. Không cấp shell, SQL, arbitrary HTTP, secret hay quyền publish trực tiếp.

Mục tiêu quan trọng nhất của đợt sửa là loại bỏ triệt để kiến trúc legacy trong đó Go đồng thời chạy Strategy/Backtest/Search/News. Nếu còn hai cách mô tả ownership, blueprint chưa đạt gate nhất quán.

## 2. Phạm vi và thứ tự ưu tiên

### P0 - Bắt buộc cho blueprint hợp lệ

1. Đồng bộ ownership Go/Python ở toàn bộ tài liệu.
2. Viết specification riêng cho Agent Platform.
3. Mở rộng Strategy Authoring với artifact, policy check, sandbox, repair, approval và immutable publishing.
4. Chốt persistence, state machine, tool contract, permission, budget, observability và crash recovery.
5. Sửa API/data/event contracts để Browser -> Go -> Python nhất quán.
6. Sửa result contract đúng các cột thầy yêu cầu.
7. Sửa chart bootstrap đúng 1,000 closed candles và provisional merge.
8. Cập nhật các diagram chính, traceability, backlog và Definition of Done.

### P1 - Bắt buộc cho adaptive news requirement

1. Safe Fetcher lấy và sanitize HTML.
2. Deterministic Readability Extractor chạy trước.
3. Content Quality Gate quyết định fallback.
4. `NewsExtractionAgent` chỉ chạy khi quality gate fail.
5. Output được validate, cache theo hash, rồi mới tagging và sentiment.

### P2 - Extension sau khi P0/P1 đạt gate

1. `CandidateDiscoveryAgent` đề xuất candidate qua queue/search policy chuẩn.
2. `MarketInsightAgent` tạo research insight read-only.
3. Full SMC chỉ được đưa vào MVP khi thầy/team xác nhận; mặc định chỉ chứng minh plugin admission.

### Ngoài phạm vi của kế hoạch tài liệu này

- Implement application code, migration, sandbox image hoặc UI runtime.
- Chạy production migration hay deploy.
- Chứng minh benchmark/performance khi chưa có implementation.
- Biến mỗi agent thành một service độc lập.
- Cho LLM tự approve, publish, gọi exchange hoặc tạo lệnh giao dịch.

## 3. Target architecture phải xuất hiện thống nhất

```text
Browser
  -> HTTPS/WSS
Go API + Market Gateway
  -> Binance/Market Provider
  -> Go-owned auth/market/checkpoint tables
  -> signed internal domain commands + normalized market stream
Python Research API + Worker
  -> Python-owned strategy/experiment/news/agent tables
  -> shared Python Strategy Runtime
  -> AgentOrchestrator + ToolRegistry
  -> internal AI/LLM Adapter

Python transaction/outbox
  -> Go POST /internal/events
  -> Go WebSocket fan-out
  -> Browser
```

Các invariant phải được ghi rõ trong `README.md`, `proposal.md`, `design.md` và các spec liên quan:

- Python không mở kết nối Binance.
- Go không tính indicator, signal, PnL, evaluation hoặc rank.
- Agent không gọi Go endpoint trực tiếp; agent gọi typed Python application tool/port.
- Realtime và backtest dùng cùng immutable `StrategySpec`/`StrategyVersion` và cùng Python Strategy Runtime.
- Event quan trọng được Python persist trước khi gửi Go để fan-out.
- Một PostgreSQL instance có thể dùng chung, nhưng write ownership theo table là bắt buộc.

## 4. Mô hình Agent Platform cần bổ sung

### 4.1 Thành phần deterministic dùng chung

| Thành phần | Trách nhiệm cần mô tả | Không được làm |
|---|---|---|
| `AgentOrchestrator` | Điều phối state machine, resume, retry, idempotency và hand-off giữa các agent | Tự suy luận như LLM agent; tự approve/publish |
| `ToolRegistry` | Đăng ký tool theo name/version/schema/permission | Expose shell, SQL, arbitrary HTTP |
| `ModelGateway` | Adapter model, structured output, timeout, token accounting | Ghi domain table; giữ workflow state |
| `AgentPermissionPolicy` | Allowlist tool theo role/state/principal | Cho agent tự sửa policy |
| `AgentBudgetManager` | Tool-call, token, repair, time và cost budget | Cho agent tự tăng budget |
| `AgentRunRepository` | Persist run, state, model/prompt/config provenance | Chứa secret hoặc raw credential |
| `AgentAttemptRepository` | Persist input/output hash, attempt number và structured error | Ghi đè lịch sử attempt |
| `ArtifactRepository` | Lưu immutable generated source/spec/artifact hash | Publish trực tiếp vào Registry |
| `SandboxRunner` | Chạy contract/fixture test trong môi trường cô lập | Có network, DB, secret hay package install |
| `ApprovalService` | Human approve/reject đúng reviewed hash | Cho model giả lập approval |
| `StrategyPublisher` | Publish idempotent immutable version sau approval | Publish artifact chưa test hoặc hash khác |

### 4.2 Sáu logical agent roles

| Agent | Mức | Kết quả đầu ra | Gate kế tiếp |
|---|---|---|---|
| `StrategyDesignerAgent` | P0 | Valid draft `StrategySpec` | Schema + semantic validation |
| `StrategyImplementationAgent` | P0 | Python artifact hoặc custom draft | Policy + sandbox tests |
| `StrategyRepairAgent` | P0 | Bounded spec/code patch | Revalidate + retest |
| `NewsExtractionAgent` | P1 | Structured news item từ sanitized HTML | Schema + quality validation |
| `CandidateDiscoveryAgent` | P2 | Validated candidate batch | Standard search queue |
| `MarketInsightAgent` | P2 | Read-only insight draft | Human/research consumption |

### 4.3 State machine canonical

```text
DRAFT_CREATED
  -> SOURCE_READY
  -> SPEC_GENERATING
  -> SPEC_VALIDATING
  -> CODE_GENERATING
  -> POLICY_CHECKING
  -> SANDBOX_TESTING
       -> fail, còn budget: REPAIRING -> CODE_GENERATING
       -> fail, hết budget: FAILED
       -> pass: REVIEW_REQUIRED
            -> human approve: APPROVED -> PUBLISHED
            -> human reject: REJECTED
```

Mỗi transition phải có expected-current-state, idempotency key, actor, reason, timestamp và correlation ID. Worker restart phải resume từ persisted state; không được lặp attempt hay publish hai lần.

## 5. Tool catalog phải được thiết kế và implement

### 5.1 Contract chung cho mọi tool

Mỗi tool specification phải có:

- Stable `name` và `version`.
- JSON Schema cho input/output.
- Allowed agent roles và allowed workflow states.
- `principal_id`, `agent_run_id`, `correlation_id`.
- Deadline, cancellation và resource budget.
- `idempotency_key` cho write tool.
- Structured error code với `retryable` rõ ràng.
- Audit event, latency/error metrics và evidence reference.
- Giới hạn kích thước input/output; dữ liệu lớn trả bằng immutable `evidence_ref`.

Envelope tối thiểu:

```json
{
  "context": {
    "principal_id": "user-id",
    "agent_run_id": "run-id",
    "correlation_id": "request-id",
    "deadline": "2026-08-26T12:00:00Z",
    "idempotency_key": "write-key",
    "remaining_budget": {
      "tool_calls": 10,
      "repair_attempts": 2
    }
  },
  "input": {}
}
```

```json
{
  "ok": true,
  "data": {},
  "error": null,
  "evidence_ref": "evidence-id",
  "tool_version": "v1"
}
```

### 5.2 Tools của `StrategyDesignerAgent`

| Tool | Loại | Dùng để làm gì | Backing service cần có |
|---|---|---|---|
| `source.get_document` | Read | Đọc document đã fetch/sanitize theo ID; không fetch URL | Source Document Repository |
| `strategy.get_catalog` | Read | Lấy strategy/indicator/operator/parameter được hỗ trợ | Python Strategy Registry/Catalog |
| `strategy.get_dsl_schema` | Read | Lấy JSON Schema của `StrategySpec` đúng version | StrategySpec Schema Service |
| `strategy.validate_spec` | Compute | Kiểm tra schema, semantic, bounds và causality | StrategySpec Validator |
| `strategy.get_validation_errors` | Read | Đọc lỗi có cấu trúc và câu hỏi cần bổ sung | Validation Evidence Repository |
| `strategy.save_draft_spec` | Write | Lưu revision spec với immutable content hash | Draft Repository + idempotent revision service |

### 5.3 Tools của `StrategyImplementationAgent`

| Tool | Loại | Dùng để làm gì | Backing service cần có |
|---|---|---|---|
| `artifact.compile_from_spec` | Compute/Write | Compile DSL hợp lệ thành Python deterministic | Versioned Strategy Compiler |
| `artifact.create_custom_draft` | Write | Lưu custom Python draft cho advanced path | Artifact Repository |
| `artifact.run_policy_check` | Compute | Kiểm AST, import, API và forbidden behavior | AST/Import Policy Checker |
| `artifact.save_version` | Write | Lưu artifact hash, compiler/model provenance | Artifact Repository |
| `sandbox.run_contract_tests` | Async Write | Tạo sandbox run idempotent và chạy contract fixtures | Isolated Sandbox Runner |
| `sandbox.get_test_report` | Read | Đọc report có cấu trúc/evidence | Sandbox Report Repository |
| `draft.mark_review_required` | Write | Chuyển state sau khi mọi gate pass | State Transition Service |

### 5.4 Tools của `StrategyRepairAgent`

| Tool | Loại | Dùng để làm gì | Backing service cần có |
|---|---|---|---|
| `agent.get_attempt_context` | Read | Đọc spec/code hiện tại và bounded attempt history | Agent Attempt Repository |
| `sandbox.get_test_report` | Read | Đọc lỗi test có cấu trúc | Sandbox Report Repository |
| `strategy.apply_spec_patch` | Write | Patch DSL-backed spec theo expected revision | Draft Revision Service |
| `artifact.apply_code_patch` | Write | Patch custom-code draft trong advanced path | Artifact Patch Service |
| `strategy.validate_spec` | Compute | Revalidate spec sau patch | StrategySpec Validator |
| `artifact.run_policy_check` | Compute | Recheck source sau patch | AST/Import Policy Checker |
| `sandbox.run_contract_tests` | Async Write | Retest trong sandbox mới | Isolated Sandbox Runner |
| `draft.mark_failed` | Write | Kết thúc khi hết budget hoặc lỗi không repair được | State Transition Service |

### 5.5 Tools của `NewsExtractionAgent`

| Tool | Loại | Dùng để làm gì | Backing service cần có |
|---|---|---|---|
| `document.get_sanitized_html` | Read | Đọc HTML đã safe-fetch và sanitize | News Document Repository |
| `document.get_extraction_errors` | Read | Đọc lý do deterministic extraction fail quality gate | Extraction Evidence Repository |
| `news.get_item_schema` | Read | Lấy output schema/version | News Schema Service |
| `news.validate_extraction` | Compute | Validate field, content quality và provenance | News Extraction Validator |
| `news.save_extraction` | Write | Lưu kết quả theo content/model/prompt hash | News Repository + cache |

### 5.6 Tools của `CandidateDiscoveryAgent` - P2

| Tool | Loại | Dùng để làm gì | Backing service cần có |
|---|---|---|---|
| `search.get_search_space` | Read | Lấy strategy/parameter/policy được phép | Search Configuration Service |
| `search.get_tested_hashes` | Read | De-duplicate candidate đã test | Search History Repository |
| `leaderboard.get_summary` | Read | Lấy metric/history summary, không đọc raw DB | Ranking Query Service |
| `candidate.validate` | Compute | Kiểm schema, semantic, causality và search bounds | Candidate Validator |
| `candidate.estimate_cost` | Compute | Ước lượng số run, quota và worker cost | Candidate Cost Estimator |
| `candidate.submit_batch` | Async Write | Đưa batch hợp lệ vào standard bounded queue | Search Application Service |

### 5.7 Tools của `MarketInsightAgent` - P2

| Tool | Loại | Dùng để làm gì | Backing service cần có |
|---|---|---|---|
| `market.get_snapshot` | Read | Lấy normalized Candle/BBO as-of snapshot qua Python `MarketDataPort` | Go Market internal adapter + Python port |
| `indicator.get_snapshot` | Read | Lấy causal indicator snapshot đúng timestamp | Python Indicator Service |
| `news.get_recent_summary` | Read | Lấy recent news/sentiment window | Python News Query Service |
| `experiment.get_recent_results` | Read | Lấy authorized evaluation summary | Python Experiment Query Service |
| `insight.save_draft` | Write | Lưu research insight và provenance; không tạo order | Insight Repository |

### 5.8 Capabilities tuyệt đối không expose

- Generic shell/process execution.
- Generic SQL hoặc direct DB connection.
- Arbitrary HTTP/browser fetch.
- Unrestricted filesystem read/write.
- Arbitrary Docker/container control.
- Secret, credential hoặc environment dump.
- Direct Registry publish/approve.
- Sửa test fixture, expected output, policy hay budget.
- Direct exchange/order execution.
- Direct Backtest Engine invocation bởi Candidate Discovery.

## 6. Persistence và invariant cần đưa vào ERD/spec

| Entity | Trường bắt buộc | Unique/idempotency invariant |
|---|---|---|
| `strategy_drafts` | `id`, `owner_id`, `source_type`, `source_ref`, `source_hash`, `mode`, `current_revision`, `status`, timestamps | `(owner_id, idempotency_key)`; optimistic revision |
| `strategy_draft_revisions` | `draft_id`, `revision`, `spec_json`, `spec_hash`, `created_by`, `agent_run_id` | `(draft_id, revision)` và immutable `spec_hash` |
| `agent_runs` | `id`, `draft_id`, `agent_type`, `state`, model/prompt/tool-policy versions, budgets, timestamps | create idempotency; legal-state transition only |
| `agent_attempts` | `run_id`, `attempt_no`, input/output hashes, error code, evidence ref, timestamps | `(run_id, attempt_no)` immutable |
| `strategy_artifacts` | `id`, `draft_id`, `revision`, `language`, source/object ref, artifact hash, compiler version | unique immutable `artifact_hash` |
| `sandbox_runs` | `id`, `artifact_id`, image digest, policy version, fixture version, status, resource use, report ref | `(artifact_id, policy_version, fixture_version, idempotency_key)` |
| `strategy_approvals` | reviewer, reviewed spec/artifact hashes, decision, reason, timestamp | decision bound to exact reviewed hashes |
| `strategy_versions` | strategy/version, spec hash, artifact hash, full provenance, publication timestamp | immutable version; publish-once constraint |
| `tool_invocations` | run/attempt/tool/version, request hash, result/evidence ref, latency, status | write call idempotency and audit retention |
| `news_extractions` | document/content/model/prompt/schema hashes, fields, quality result | deterministic cache key |
| `insight_drafts` | symbol/timeframe/as-of, observations, risk, confidence, evidence/model version | read-only artifact; no order relation |

Database ownership phải có matrix rõ ràng:

- Go write: market pair/cache candle/BBO/checkpoint, edge auth/session/quota data.
- Python write: strategy/agent/artifact/approval/experiment/job/trade/equity/evaluation/rank/news/sentiment/insight.
- Go không join trực tiếp nhiều Python table trong MVP; public query được proxy sang stable Python internal API.

## 7. API và event contracts cần cập nhật

### 7.1 Public Go API

Blueprint cần mô tả Go là điểm vào duy nhất cho browser:

- Create/read/update authoring draft.
- Submit source text/approved URL.
- Start agent run và xem status/evidence.
- Human approve/reject exact reviewed revision.
- Create/query experiment, search và leaderboard bằng proxy command/query.
- Query news, insight và results bằng proxy.
- Market history + public realtime WebSocket trực tiếp từ Go market boundary.

Go phải thực thi auth, RBAC, quota, request size/schema, CORS, correlation ID và error mapping trước khi ký principal context gửi Python.

### 7.2 Internal Go -> Python

Các domain command/query cần versioned path, signed service identity và signed principal context. Blueprint không bắt buộc tên endpoint cuối cùng, nhưng phải nêu đủ nhóm:

- Strategy draft/source/agent-run/approval commands.
- Strategy catalog/version queries.
- Experiment/search/leaderboard commands và queries.
- News/sentiment/insight queries.
- Health/readiness và compatibility version.

### 7.3 Internal Python -> Go Market

- `GET /internal/market/candles`
- `GET /internal/market/bbo-snapshot`
- Normalized authenticated market event stream.
- Contract phải có provider, symbol, timeframe, `open_time`, final/provisional, sequence/checkpoint và as-of semantics.

Agents không gọi endpoint trên. `MarketDataPort` và infrastructure adapter chịu trách nhiệm network/auth/retry.

### 7.4 Internal Python -> Go event fan-out

- `POST /internal/events`
- Event envelope: `event_id`, `event_type`, `aggregate_id`, `aggregate_version`, `occurred_at`, `correlation_id`, `principal_id`, payload schema version.
- Python persist state và outbox trong cùng transaction trước khi notify.
- Go de-duplicate theo `event_id`, sau đó fan-out theo authorized topic.

Các event tối thiểu:

- `strategy_draft.state_changed`
- `agent_run.progressed`
- `agent_attempt.completed`
- `sandbox_run.completed`
- `strategy_review.required`
- `strategy_version.published`
- `experiment.progressed`
- `search.progressed`
- `news.extraction.completed`

## 8. Kế hoạch sửa theo từng file

### 8.1 `blueprint/README.md`

- Thêm `specs/agent-architecture.md` vào cấu trúc và reading order.
- Thêm link đến kế hoạch này và HTML diagram reference trong mục tài liệu làm việc; ghi rõ không phải runtime evidence.
- Thay mọi mô tả Go Strategy/Backtest/News bằng Go API/Market và Python Research ownership.
- Cập nhật mapping requirement cho natural-language/URL authoring, generated Python, repair loop, adaptive extraction, 1,000-candle bootstrap và trade columns.
- Bổ sung diagram 25-33 vào catalog sau khi các `.mmd/.svg/.png` canonical được tạo.
- Đồng bộ version/changelog của blueprint.

### 8.2 `blueprint/proposal.md`

- Sửa topology/workload: web, Go API/Market, Python research API/worker, internal AI inference.
- Xóa cụm `Go Strategy Service` và mọi ownership legacy.
- Đưa các yêu cầu từ `note.txt` vào scope/traceability với tag `[SRC-ADD]`.
- Tách rõ DSL-backed authoring là MVP; custom Python, Candidate Discovery Agent, Market Insight Agent và full SMC là advanced/default-off.
- Thêm success criteria cho bounded repair, human approval, sandbox isolation, provenance và exact-result columns.
- Cập nhật risk: prompt injection, generated-code escape, model nondeterminism, HTML tree drift, double publish và stale workflow resume.

### 8.3 `blueprint/design.md`

- Mục 1.2: viết lại responsibility, DB write ownership và internal API boundary.
- Mục 1.2.5: thay Go direct read projection vào Python domain tables bằng stable Python internal query API cho MVP.
- Mục 1.3-1.5: mô tả Python API/worker cùng package/image; AI adapter inference-only; failure isolation.
- Mục 2-3: cập nhật C4 L2/L3 và HLA theo target topology.
- Mục 4: thêm agent/artifact/sandbox/approval entities, keys và table ownership.
- Mục 5: thêm tool invocation envelope, agent states, domain events và invariant.
- Mục 6: thêm authoring sequence, repair loop, news fallback, 1,000-candle merge và result display flow.
- Mục 7-8: thêm RBAC/tool permission, signed principal, budget, sandbox, SSRF/prompt-injection defense và audit.
- Mục 8.1: thay Go Registry/MACD sample bằng Python Registry và `app/domain/strategy/plugins/macd.py`.
- Mục 9: thêm antipattern “LLM tự gọi shell/SQL/HTTP”, “agent tự publish”, “hai strategy runtime”.
- Mục 10 ADR: bổ sung ADR cho ownership, DSL-first authoring, bounded repair, sandbox và human approval.
- Mục 11.1: sửa toàn bộ `.go` path còn sót thành Python canonical path.
- Mục 12: cập nhật roadmap P0/P1/P2, demo gates và status “target gap” đúng implementation evidence.
- Mục 13: cập nhật repository tree dự kiến cho agent/tool/sandbox modules.

### 8.4 `blueprint/specs/agent-architecture.md` - tạo mới

Specification mới phải có đủ các mục:

1. Purpose, scope, source traceability và non-goals.
2. Logical deployment model và dependency rules.
3. AgentOrchestrator responsibilities.
4. Sáu role, input/output và allowed tool matrix.
5. Tool protocol, registry, permission, budget và error taxonomy.
6. Canonical state machine và transition table.
7. Persistence schema, immutable hashes và idempotency.
8. ModelGateway adapter/version/provenance.
9. Sandbox threat model, limits và contract fixtures.
10. Human review/approval/publishing rules.
11. Retry, repair budget, crash recovery và cancellation.
12. Events, WebSocket progress và outbox behavior.
13. Metrics, logs, traces, audit retention và alerts.
14. Security abuse cases và forbidden capabilities.
15. Test strategy, acceptance scenarios và failure injection.
16. MVP/advanced split và open decisions.

### 8.5 `blueprint/specs/strategy-authoring.md`

- Giữ safe input flow text/URL -> sanitized document -> draft spec.
- Thêm hai authoring modes và rule không hot-load custom Python.
- Thêm Designer -> Implementation -> Repair hand-off.
- Thêm draft revision, content hashes, artifact lifecycle và exact reviewed fingerprint.
- Thêm compiler version, policy version, sandbox image/fixture version, model/prompt version.
- Thêm bounded repair default 3, terminal failure và manual retry semantics.
- Thêm review UI evidence: source, spec diff, generated artifact, policy report, test report và preview.
- Thêm approval/rejection/publish idempotency và registry visibility rules.
- Thêm acceptance tests cho prompt injection, stale revision, crash resume và parity.

### 8.6 `blueprint/specs/strategy-registry.md`

- Rewrite Python canonical contract dựa trên `app/domain/strategy/registry.py` và `contract.py`.
- Mô tả built-in trusted plugin, DSL compiled/interpreted strategy và advanced deployed plugin.
- Registry chỉ nhận immutable `StrategyVersion` đã approved/published.
- Không giữ Go interface/plugin path làm canonical; nếu cần lịch sử thì gắn rõ `Legacy/Archived` và không nằm trong target path.
- Thêm compatibility/versioning, parameter metadata và realtime/backtest parity invariant.

### 8.7 `blueprint/specs/backtest.md`

- Rewrite engine/worker/contracts sang Python.
- Giữ chronological, causal, deterministic semantics và immutable dataset/version.
- Thêm input `symbol`, range, investment/notional, single/composite strategy và execution assumptions.
- Thêm per-trade fields: symbol, quote currency, LONG/SHORT, entry/exit time, USD notional, SL/TP, fee, spread, slippage, gross/net PnL.
- Thêm null semantics khi risk policy không tạo SL/TP.
- Xóa Go worker/Decimal/plugin ownership khỏi target design.

### 8.8 `blueprint/specs/search-loop.md`

- Rewrite CandidateGenerator và SearchRun ownership sang Python.
- Random Search vẫn là MVP; Domain-Guided là deterministic replaceability proof.
- Agent discovery chỉ là optional generator adapter.
- `CandidateDiscoveryAgent` chỉ submit qua standard queue, không gọi backtest trực tiếp, không sửa ranking hay stop condition.
- Thêm de-dup hash, cost estimate, quota và provenance.

### 8.9 `blueprint/specs/experiment.md`

- Chốt Python ownership cho snapshot/job/run persistence.
- Thêm strategy/spec/artifact/compiler/sandbox/dataset/execution model fingerprints.
- Thêm signed principal context từ Go và idempotent experiment creation.
- Không để Go transaction ghi Python experiment tables.

### 8.10 `blueprint/specs/evaluation.md`

- Chốt Python evaluator là canonical.
- Đồng bộ Return, Win Rate, wins, losses, total/gross/net profit và Max Drawdown.
- Ghi rõ fee/spread/slippage ảnh hưởng gross/net metrics.
- Thêm deterministic rounding/currency semantics.

### 8.11 `blueprint/specs/leaderboard.md`

- Chốt Python ranking/leaderboard ownership và authorized query qua Go proxy.
- Thêm immutable result/provenance link.
- Đảm bảo Candidate Discovery chỉ đọc summary và không ghi rank.
- Thêm deterministic tie-break và stale-result/version policy.

### 8.12 `blueprint/specs/news.md`

- Rewrite Python canonical orchestration; Go không sở hữu parser/news worker/domain tables.
- Mô tả pipeline Safe Fetch -> Readability -> Quality Gate -> conditional LLM Extraction -> Validate -> Cache -> Tag -> Sentiment.
- Safe Fetcher enforce URL allowlist, DNS/IP recheck, redirect/size/type/time limits và sanitize.
- `NewsExtractionAgent` chỉ nhận document ID/sanitized HTML; không có arbitrary HTTP.
- Cache key gồm content/model/prompt/schema hashes; persist failure evidence.

### 8.13 `blueprint/specs/sentiment.md`

- Chốt Python orchestration, AI adapter inference-only.
- Sentiment input chỉ từ validated news item/version.
- Persist model/prompt/schema versions, confidence và failure state.
- Không cho model ghi DB trực tiếp.

### 8.14 `blueprint/specs/visualization.md`

- Sửa TypeScript `Trade` để có `symbol`, `quote_currency`, `entry_notional`, `exit_notional`, `sl_price`, `tp_price`, `fee_paid`, `spread_cost`, `slippage_cost`, `gross_pnl`, `net_pnl`.
- Ghi rõ nullable SL/TP và cách UI hiển thị `N/A`.
- Đồng bộ table, chart markers và API view model theo đúng `note.txt`.
- Thêm schema/API/UI test cho từng cột.

### 8.15 `blueprint/specs/market-data.md`

- Giữ Go canonical ownership.
- Ghi rõ initial request lấy đúng most recent 1,000 closed candles cho từng panel.
- Merge provisional candle theo `open_time`: replace nếu bằng last candle, append nếu mới hơn.
- `Final=true` chuyển thành closed/persisted; de-duplicate theo provider/symbol/timeframe/open_time.
- Đổi một panel chỉ cancel/reload subscription của panel đó.
- Thêm internal Python market contract và authenticated event stream.

### 8.16 `blueprint/specs/chart-overlay.md`

- Giữ browser subscription transport qua Go; indicator/overlay semantics ở Python.
- Xóa path legacy `server/internal/domain/strategy/config_hash.go`.
- Dùng strategy version/config hash do Python phát hành.
- Đồng bộ overlay và signal với same-runtime parity.

### 8.17 `blueprint/specs/composite-strategy.md`

- Chốt composite evaluator và indicator dependency ở Python.
- Giữ manual majority/weighted policies và causal evaluation.
- Composite spec phải dùng same schema/version/hash pipeline như single strategy.
- Không đặt combiner trong Go.

### 8.18 `blueprint/specs/python-research.md`

- Mở rộng component map cho Agent Platform, Source Ingestor, Compiler, Policy Checker, Sandbox Adapter, Artifact/Approval repositories.
- Nêu API workload và worker workload dùng cùng package/image.
- Nêu existing services được wrap thành typed application tools; agent không import/call DB trực tiếp.
- Thêm dependency rule: domain/application không phụ thuộc Go transport hay vendor LLM SDK.

### 8.19 `blueprint/specs/auth.md`

- Giữ Go auth/RBAC/quota ownership.
- Thay mọi `Go Worker` legacy bằng Python worker/internal service identity đúng topology.
- Thêm signed principal/delegation context và anti-replay cho Go -> Python.
- Thêm authorization rule cho owner/reviewer/admin, source URL và agent-run evidence.

### 8.20 `blueprint/specs/observability.md`

- Thêm metric cho agent run/state latency, tool call/error, model latency/token/cost, sandbox result/resource, repair count và publish conflict.
- Thêm trace propagation Browser -> Go -> Python -> Tool/Model/Sandbox -> event fan-out.
- Thêm audit query theo principal/run/draft/artifact hash.
- Thêm alert cho stuck state, repeated policy violation, sandbox escape signal và event delivery backlog.

### 8.21 `blueprint/traceability.md`

- Mỗi `[SRC-ADD]` phải map tới spec, diagram, acceptance test và demo evidence.
- Thêm riêng natural-language/URL draft, generated Python, bounded repair, trade columns, adaptive news extraction, 1,000 candles, SMC và market insight.
- Phân biệt status `Designed`, `Implemented`, `Verified`; không đánh dấu implemented chỉ vì có checklist.
- Link P2 requirement tới default-off/open decision.

### 8.22 `blueprint/jira-backlog.md`

- Phân lại ownership: Member/stream Go chỉ API/Market; Python nhận strategy/backtest/search/news/agent.
- Xóa task path `server/internal` cho strategy/composite/backtest/search.
- Tạo epic Agent Platform và stories cho orchestrator, tools, persistence, compiler, policy, sandbox, repair, approval, UI và tests.
- Tạo epic adaptive news extraction.
- Tạo story đóng result contract và realtime bootstrap gaps.
- Mỗi story có dependency, acceptance criteria, evidence và owner; P2 không chặn MVP.

### 8.23 `blueprint/go-review-checklist.md`

- Thu hẹp checklist vào Public API/Edge, auth/quota, signed proxy, Market Data, reconnect/checkpoint và WebSocket fan-out.
- Xóa câu khẳng định Go domain contracts là active implementation cho Strategy/Backtest/Search/News.
- Thêm negative gates: Go không import/calculate Python research domain; Go không ghi Python-owned tables.
- Link sang Python/Agent review gates phù hợp thay vì kiểm tra sai layer.

### 8.24 Diagram sources và catalog

Các diagram hiện có phải được sửa:

| ID | File | Nội dung cập nhật |
|---|---|---|
| 02 | `02-c4-l2-container` | Go API/Market, Python Research API/Worker, AI inference-only |
| 03 | `03-c4-l3-python-strategy-platform` | Agent Platform và Python domain ownership |
| 04 | `04-high-level-architecture` | Browser -> Go -> Python và event return path |
| 06 | `06-erd` | Agent/artifact/sandbox/approval tables và ownership |
| 11 | `11-search-backtest-pipeline` | Python-only engine; optional agent generator adapter |
| 13 | `13-news-html-llm-pipeline` | Deterministic extraction quality gate trước LLM fallback |
| 14 | `14-defense-in-depth` | Tool permissions, prompt injection và sandbox boundary |
| 17 | `17-python-worker-execution` | Agent jobs/state resume/tool calls |
| 21 | `21-ai-strategy-authoring` | Designer/Implementation/Repair, review và publish |
| 22 | `22-strategy-runtime-parity` | Same immutable Python runtime/version |
| 24 | `24-trade-result-provenance` | Artifact/compiler/sandbox/approval fingerprints |

Append diagram mới, không renumber diagram cũ:

| ID dự kiến | Tên | Mục đích |
|---|---|---|
| 25 | `agent-platform-components` | Toàn bộ orchestrator, agents, tools và services |
| 26 | `agent-run-state-machine` | State, repair branch, review, approval và terminal states |
| 27 | `strategy-designer-agent` | Inputs, 6 tools, validator và output |
| 28 | `strategy-implementation-agent` | Compiler/custom path, 7 tools và sandbox gate |
| 29 | `strategy-repair-agent` | Failure evidence, 8 tools và bounded loop |
| 30 | `news-extraction-agent` | Conditional fallback, 5 tools và validation/cache |
| 31 | `candidate-discovery-agent` | 6 tools, queue/quota boundary và provenance |
| 32 | `market-insight-agent` | 5 read/draft tools và no-trade boundary |
| 33 | `tool-invocation-security-boundary` | Registry, policy, budget, audit và forbidden capabilities |

Khi thực thi blueprint update:

- Tạo `.mmd` source trong `blueprint/assets/diagrams/`.
- Render cả `.svg` và `.png`.
- Cập nhật `blueprint/assets/diagrams/index.json` và `blueprint/assets/README.md`.
- Kiểm tra mọi Mermaid diagram theo hướng dọc `flowchart TB` nếu phù hợp.
- HTML đi kèm kế hoạch này là reference tổng hợp; không thay thế canonical diagram sources.

## 9. Sandbox và generated-code gates

Specification phải định nghĩa sandbox disposable với:

- Non-root user.
- Network disabled.
- Không DB, exchange credential, application secret hay host socket.
- Không package installation.
- Import allowlist.
- Read-only base filesystem và một bounded temp workspace.
- CPU, RAM, wall time, output size, process và syscall limit.
- Deterministic clock/random seed/fixture nếu test cần.
- Persist image digest, policy version, fixture version và resource usage.

Contract suite tối thiểu:

1. Import và Strategy contract conformance.
2. Parameter schema/default/bounds.
3. Signal action/price/size validity.
4. Không network/DB/unrestricted filesystem.
5. Không future candle/indicator access.
6. Determinism với cùng input.
7. Timeout và resource bound.
8. Exception isolation và structured failure.
9. Realtime/backtest parity cho cùng version.
10. Preview fixture dùng được cho human review.

## 10. Realtime và trade contract gaps phải đóng

### Realtime 1,000 candles

1. Mỗi chart panel request most recent 1,000 closed candles.
2. Sau snapshot mới subscribe matching realtime stream.
3. Provisional có cùng `open_time` với last candle thì replace in-memory.
4. Provisional mới hơn thì append.
5. `Final=true` biến thành closed, persist và mở bucket tiếp theo.
6. De-duplicate theo `(provider, symbol, timeframe, open_time)`.
7. Panel thay đổi không reload ba panel còn lại.

### Trade/result contract

Mỗi row/API object tối thiểu có:

- `symbol`, `quote_currency`.
- `entry_time`, `exit_time`, `side`.
- `entry_price`, `exit_price`.
- `quantity`, `entry_notional`, `exit_notional`.
- Nullable `sl_price`, `tp_price`.
- `fee_paid`, `spread_cost`, `slippage_cost`.
- `gross_pnl`, `net_pnl`.
- Strategy/experiment/run provenance reference.

Metric summary tối thiểu: Return, Win Rate, wins, losses, total/gross/net profit, Max Drawdown và Number of Trades.

## 11. Trình tự thực thi và dependency

### Phase 0 - Freeze và inventory

- [x] Chốt `PROJECT_CONTEXT.md` là resume source trong đợt sửa.
- [x] Lập danh sách mọi occurrence legacy Go Strategy/Backtest/Search/News.
- [x] Chụp baseline links, diagram IDs và implementation status.
- [x] Exit gate: không còn file canonical chưa được phân owner/status.

### Phase 1 - Ownership reconciliation

- [x] Sửa README, proposal, design boundary, Go checklist và Python research spec.
- [x] Sửa canonical ownership ở registry/backtest/search/news specs.
- [x] Exit gate: target architecture không còn mô tả Go là Strategy/Backtest/Search/News owner; legacy alternative được đánh dấu archived.

### Phase 2 - Contracts và persistence

- [x] Chốt internal APIs, event envelope, signed principal và DB ownership ở mức specification.
- [x] Chốt agent tables, unique keys, hash/provenance và state transition rule ở mức specification.
- [x] Exit gate tài liệu: write owner/idempotency và Browser -> Go boundary được quy định rõ. Runtime gate vẫn pending.

### Phase 3 - Agent Platform specification

- [x] Tạo `specs/agent-architecture.md`.
- [x] Chốt role/tool matrix, state machine, permission, budget, observability.
- [x] Exit gate tài liệu: mỗi role chỉ có typed tool cần thiết; forbidden capabilities được cấm rõ. Runtime enforcement vẫn pending.

### Phase 4 - Strategy authoring, compiler, repair và sandbox

- [x] Mở rộng authoring spec và Registry integration.
- [x] Chốt DSL/custom modes, artifact lifecycle, tests, approval/publish.
- [x] Exit gate tài liệu: failing artifact bị chặn và pass chỉ đến `REVIEW_REQUIRED`. Runtime gate vẫn pending.

### Phase 5 - Adaptive news extraction

- [x] Rewrite news/sentiment pipeline và conditional LLM fallback.
- [x] Exit gate tài liệu: agent không thể fetch URL; deterministic path luôn chạy trước fallback. Runtime gate vẫn pending.

### Phase 6 - Optional discovery và insight

- [x] Thiết kế Candidate Discovery và Market Insight dưới feature flag/default-off.
- [x] Exit gate tài liệu: discovery không bypass queue/quota/stop; insight không tạo order. Runtime gate vẫn pending.

### Phase 7 - Requirement contract closure

- [x] Sửa 1,000-candle behavior và exact trade/result fields.
- [x] Exit gate tài liệu: API/schema/UI acceptance rows map đủ `note.txt`. Runtime demo vẫn pending.

### Phase 8 - Diagrams, traceability và backlog

- [x] Update diagram 02/03/04/06/11/13/14/17/21/22/24.
- [x] Add diagram 25-33, render SVG/PNG, update index.
- [x] Update traceability và Jira theo dependency/P0-P2.
- [x] Exit gate artifact: mọi `[SRC-ADD]` có spec + diagram + acceptance mapping; demo runtime vẫn pending.

### Phase 9 - Consistency verification

- [x] Chạy link check, Mermaid render, search legacy terms và review ownership matrix.
- [x] So sánh README/proposal/design/spec/diagram/backlog trên cùng một scenario.
- [x] Exit gate documentation/artifact ở mục 12.1 và 12.4 đạt; các checklist runtime ở 12.2/12.3 giữ pending cho implementation evidence.

## 12. Verification checklist

### 12.1 Documentation consistency

- [x] Không còn target `Go Strategy Service`, `Go Backtest Worker`, Go strategy plugin hay Go CandidateGenerator.
- [x] Go chỉ có API/Edge/Market responsibilities ở mọi file.
- [x] Python là single Strategy Runtime cho realtime và backtest.
- [x] AI Adapter được ghi inference-only ở mọi view.
- [x] Agent roles luôn là logical roles, không bị vẽ thành independent services.
- [x] SMC/custom Python/Candidate Discovery/Market Insight có MVP/advanced status nhất quán.

### 12.2 Agent safety/correctness

- [ ] Prompt/URL input không thể tự cấp tool.
- [ ] Không agent nào có shell, SQL, arbitrary HTTP, secret hoặc direct publish.
- [ ] Tool permission kiểm role + state + principal.
- [ ] Write tool có idempotency key và audit record.
- [ ] Repair budget do orchestrator giữ, default 3 và persist.
- [ ] Sandbox no-network/no-DB/non-root/read-only/bounded.
- [ ] Pass test chỉ chuyển `REVIEW_REQUIRED`.
- [ ] Approval bind đúng spec/artifact hashes được review.
- [ ] Restart không duplicate attempt/publish.

### 12.3 Requirement acceptance

- [ ] Text input tạo valid draft StrategySpec.
- [ ] Approved URL được safe-fetch, sanitize và content-hash.
- [ ] Generated artifact có immutable hash và compiler/model provenance.
- [ ] Structured failure tạo bounded repair flow.
- [ ] News fallback chỉ chạy sau deterministic quality failure.
- [ ] Chart bootstrap/merge đúng 1,000 closed + provisional behavior.
- [ ] Trade API/table/chart có đủ fields và null semantics.
- [ ] Random Search và Top-K vẫn là MVP deterministic flow.
- [ ] Manual single/composite selection vẫn hoạt động theo Python runtime.

### 12.4 Artifact quality

- [x] Tất cả Mermaid source render không lỗi.
- [x] Mỗi diagram có `.mmd`, `.svg`, `.png` và index entry.
- [x] Internal links trong Markdown hợp lệ.
- [x] Traceability phân biệt `Designed`, `Implemented`, `Verified`.
- [x] Không claim implementation khi chưa có code/test evidence.

## 13. Definition of Done cho đợt cập nhật blueprint

Đợt sửa chỉ hoàn tất khi:

1. Ownership target không mâu thuẫn trong bất kỳ tài liệu canonical nào.
2. `agent-architecture.md` mô tả đầy đủ six-role model, tools, state, data, security và operations.
3. `strategy-authoring.md` mô tả được generated Python, bounded repair, sandbox, human approval và publishing.
4. News fallback, realtime 1,000 candles và exact trade output đã map đủ về acceptance test.
5. Diagram 02/03/04/06/11/13/14/17/21/22/24 được sửa và diagram 25-33 được thêm/render/index.
6. Traceability và Jira phản ánh đúng P0/P1/P2, owner, dependency và evidence.
7. Search legacy terms, link check và Mermaid render đều pass.
8. Các open decision chưa được xác nhận được ghi rõ default, không bị trình bày như requirement đã khóa.

## 14. Open decisions và default hiện tại

| Quyết định | Default dùng trong blueprint cho tới khi được đổi |
|---|---|
| Full SMC có bắt buộc demo không | Không; chỉ chứng minh extensibility/admission |
| Custom arbitrary Python có là MVP không | Không; DSL-backed deterministic compile là MVP |
| DSL strategy approved có hot availability không | Có thể qua safe interpreter/compiler semantics; custom Python không hot-load |
| Repair attempts | Tối đa 3, configurable và persisted |
| URL source allowlist | Bắt buộc allowlist + Safe Fetcher |
| Candidate Discovery Agent | P2, feature flag/default-off |
| Market Insight Agent | P2, read-only, feature flag/default-off |

Nếu một quyết định trên thay đổi, phải cập nhật đồng thời proposal, design, agent/authoring spec, traceability, backlog và diagram liên quan trước khi xem blueprint là nhất quán.
