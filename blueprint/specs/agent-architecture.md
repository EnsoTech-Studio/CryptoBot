# Đặc tả: Agent Architecture

Trạng thái kiến trúc: `Designed`  
Mức ưu tiên: P0 cho Strategy Authoring/Repair, P1 cho adaptive news, P2 cho discovery/insight  
Nguồn: `[SRC-ADD]` từ `note.txt`, cùng các quyết định an toàn `[PD]` của nhóm  
Sơ đồ: `25-agent-platform-components` đến `33-tool-invocation-security-boundary`

## Mô tả

Agent Platform biến yêu cầu tự nhiên thành artifact có thể kiểm tra, nhưng không trao
quyền hệ thống cho mô hình. Một `AgentOrchestrator` deterministic giữ workflow, state,
budget và idempotency. Năm agent role chỉ là logical role bên trong Python `research`; chúng
không phải năm service hoặc container.

Bốn role cần cho yêu cầu bổ sung:

1. `StrategyDesignerAgent`: source -> valid `StrategySpec`.
2. `StrategyImplementationAgent`: valid spec -> generated Python artifact.
3. `StrategyRepairAgent`: structured failure -> bounded patch.
4. `NewsExtractionAgent`: sanitized HTML -> structured news khi parser deterministic fail.

Một role extension, default-off:

5. `MarketInsightAgent`: tạo insight read-only, không tạo order.

Discovery dùng typed LLM generator của SearchRun, không phải AgentOrchestrator role.

Agent Platform thuộc Python `research`. Go chỉ xác thực public request, enforce edge
quota, ký principal context, proxy command/query và fan-out event đã được Python persist.
AI/LLM Adapter chỉ thực hiện structured inference; nó không giữ workflow state, không
ghi domain database và không approve/publish.

## Phạm vi và non-goal

### Trong phạm vi

- Durable orchestration, resume, retry, cancellation và bounded repair.
- Typed/versioned tool registry với role/state permission.
- Model adapter, structured output và provenance.
- Draft/spec/artifact/sandbox/approval persistence.
- Human review trước immutable publishing.
- Audit, metric, trace và failure evidence.
- Cô lập generated Python bằng policy check và disposable sandbox.

### Ngoài phạm vi

- Agent tự đặt lệnh hoặc giữ exchange credential.
- Agent tự gọi shell, SQL, arbitrary HTTP, filesystem hoặc Docker.
- Agent tự sửa fixture, policy, budget, approval hoặc Registry.
- Một microservice/container cho mỗi role.
- Hot-load arbitrary custom Python vào process production đang chạy.
- Claim rằng runtime đã implement trước khi có migration, code, test và demo evidence.

## Deployment và dependency rules

```text
Browser
  -> Go Public API / WSS
  -> signed internal command/query
Python Research API
  -> PostgreSQL job/outbox
Python Research Worker x N
  -> AgentOrchestrator
  -> logical agent handler
  -> ToolRegistry -> deterministic application service
  -> ModelGateway -> internal AI/LLM Adapter
  -> Python-owned state/evidence tables

Python outbox -> POST /internal/events -> Go WSS fan-out -> Browser
```

Dependency invariants:

- `domain` không phụ thuộc transport, database, Go hoặc vendor LLM SDK.
- `application` phụ thuộc domain port và repository interface.
- `infrastructure` implement database, Go market adapter, sandbox và model adapter.
- Agent handler chỉ gọi tool qua `ToolRegistry`; không import repository/module domain để
  bypass policy.
- Python agents không gọi public Go API. `market.get_snapshot` đi qua Python
  `MarketDataPort`; infrastructure adapter mới gọi authenticated Go internal market API.
- Critical state được commit cùng outbox event trước khi gửi progress tới Go.

## Thành phần deterministic

| Thành phần | Trách nhiệm | Invariant |
|---|---|---|
| `AgentOrchestrator` | State machine, hand-off, resume, retry, cancellation | Không suy luận thay agent; không tự approve |
| `ToolRegistry` | Resolve name/version/schema/handler | Không có generic tool hoặc dynamic import |
| `AgentPermissionPolicy` | Check principal, role, current state, tool | Deny-by-default |
| `AgentBudgetManager` | Tool-call, token, time, cost, repair budget | Agent không thể tăng budget |
| `ModelGateway` | Structured model call, timeout, usage, adapter version | Không ghi domain table |
| `StateTransitionService` | Compare-and-set legal transition | Mỗi write có idempotency key |
| `ArtifactRepository` | Immutable spec/source/artifact/evidence | Content-addressed, không ghi đè |
| `SandboxRunner` | Isolated policy/contract/fixture execution | No network/DB/secret/package install |
| `ApprovalService` | Human approve/reject exact fingerprint | Model không thể tạo approval |
| `StrategyPublisher` | Publish immutable `StrategyVersion` | Publish-once, reviewed hash phải khớp |

Các thành phần sau không phải agent: StrategySpec Validator, deterministic compiler,
AST/import policy checker, Backtest Engine, Evaluator, Random/Domain-Guided generators,
NewsTagger và SentimentAnalyzer.

## Contract chung của tool

### Invocation envelope

```json
{
  "tool_name": "strategy.validate_spec",
  "tool_version": "v1",
  "context": {
    "principal_id": "01J_USER",
    "agent_run_id": "01J_RUN",
    "agent_attempt_id": "01J_ATTEMPT",
    "correlation_id": "01J_REQUEST",
    "deadline": "2026-08-27T12:00:00Z",
    "idempotency_key": null,
    "remaining_budget": {
      "tool_calls": 8,
      "model_tokens": 12000,
      "repair_attempts": 2
    }
  },
  "input": {
    "draft_id": "01J_DRAFT",
    "revision": 3
  }
}
```

Write tool bắt buộc có `idempotency_key`; read/compute tool có thể để `null`.

### Result envelope

```json
{
  "ok": true,
  "data": {},
  "error": null,
  "evidence_ref": "evidence:sha256:...",
  "tool_version": "v1",
  "started_at": "2026-08-27T11:59:58Z",
  "finished_at": "2026-08-27T11:59:59Z"
}
```

### Error taxonomy

| Code | Retryable | Ý nghĩa |
|---|---:|---|
| `INVALID_INPUT` | no | Input không khớp JSON Schema |
| `PERMISSION_DENIED` | no | Role/state/principal không được gọi tool |
| `STALE_REVISION` | no | Expected revision không còn hiện hành |
| `BUDGET_EXHAUSTED` | no | Hết tool/token/time/repair budget |
| `DEADLINE_EXCEEDED` | conditional | Handler/model/sandbox vượt deadline |
| `POLICY_VIOLATION` | no | Generated artifact vi phạm AST/import/API policy |
| `SANDBOX_TEST_FAILED` | conditional | Contract/fixture test fail; có thể repair |
| `DEPENDENCY_UNAVAILABLE` | yes | Repository/model/sandbox adapter tạm thời unavailable |
| `CONFLICT` | no | Approval/publish/idempotency fingerprint xung đột |
| `INTERNAL_ERROR` | conditional | Lỗi không phân loại; không trả stack/secret cho model |

Mọi error có `code`, `message_safe`, `retryable`, `evidence_ref`; stack trace đầy đủ chỉ
nằm trong protected log.

## Role và allowed tools

### StrategyDesignerAgent - P0

Mục đích: chuyển natural language, DSL hoặc URL-derived document thành declarative
`StrategySpec` hợp lệ.

| Tool | Purpose | Loại |
|---|---|---|
| `source.get_document` | Đọc document đã safe-fetch/sanitize theo ID | read |
| `strategy.get_catalog` | Đọc strategy/indicator/operator/parameter được hỗ trợ | read |
| `strategy.get_dsl_schema` | Đọc JSON Schema đúng version | read |
| `strategy.validate_spec` | Schema + semantic + bounds + causal validation | compute |
| `strategy.get_validation_errors` | Đọc structured errors/unresolved questions | read |
| `strategy.save_draft_spec` | Lưu immutable-hash draft revision | write |

Không được gọi URL, shell, SQL, source tree, backtest, approval hoặc publish.

### StrategyImplementationAgent - P0

Mục đích: tạo Python artifact từ valid spec hoặc tạo advanced custom-code draft.

| Tool | Purpose | Loại |
|---|---|---|
| `artifact.compile_from_spec` | Compile DSL thành Python deterministic | compute/write |
| `artifact.create_custom_draft` | Lưu custom Python draft cho advanced path | write |
| `artifact.run_policy_check` | AST/import/API/forbidden behavior check | compute |
| `artifact.save_version` | Lưu artifact hash và provenance | write |
| `sandbox.run_contract_tests` | Tạo isolated sandbox run và chạy fixture | async write |
| `sandbox.get_test_report` | Đọc structured report/evidence | read |
| `draft.mark_review_required` | Chuyển state sau khi mọi gate pass | write |

`artifact.compile_from_spec` là đường mặc định. `artifact.create_custom_draft` chỉ dùng
khi DSL không biểu diễn được yêu cầu; artifact custom không hot-load.

### StrategyRepairAgent - P0

Mục đích: đọc structured failure và đề xuất patch nhỏ nhất trong bounded attempt.

| Tool | Purpose | Loại |
|---|---|---|
| `agent.get_attempt_context` | Đọc current revision và bounded attempt history | read |
| `sandbox.get_test_report` | Đọc validation/policy/test failure evidence | read |
| `strategy.apply_spec_patch` | Patch DSL spec với expected revision | write |
| `artifact.apply_code_patch` | Patch advanced custom-code draft | write |
| `strategy.validate_spec` | Revalidate spec sau patch | compute |
| `artifact.run_policy_check` | Recheck artifact policy | compute |
| `sandbox.run_contract_tests` | Retest bằng sandbox run mới | async write |
| `draft.mark_failed` | Persist terminal failure khi hết budget | write |

Budget mặc định tối đa 3 repair attempts. Chỉ orchestrator được giảm budget và quyết định
có attempt tiếp theo; agent không sửa fixture/policy/budget.

### NewsExtractionAgent - P1

Mục đích: phục hồi structured news khi deterministic Readability Extractor fail quality gate.

| Tool | Purpose | Loại |
|---|---|---|
| `document.get_sanitized_html` | Đọc sanitized HTML đã fetch | read |
| `document.get_extraction_errors` | Đọc deterministic quality diagnostics | read |
| `news.get_item_schema` | Đọc output schema/version | read |
| `news.validate_extraction` | Validate fields, quality và provenance | compute |
| `news.save_extraction` | Lưu/cache theo content/model/prompt/schema hash | write |

Agent không có URL/browser tool. Safe Fetcher deterministic sở hữu network và SSRF guard.

### Discovery LLM generator — typed, bounded

Discovery MVP không tạo autonomous agent hay tool loop. `DiscoveryController`
gọi một typed internal LLM generator duy nhất sau khi deterministic selector
chọn `llm`; controller giữ archive, admission, cost, state và stop policy.

Ba strict-JSON prompt mode:

| Mode | Input tối thiểu | Output |
|---|---|---|
| `new` | allowed catalog, data capability, archive summary, diversity gap | one new `CandidateSpec` + hypothesis/operation |
| `improve` | one parent, train/validation metrics, failure evidence | exactly one structural change + `CandidateSpec` |
| `combine` | top candidates, validation-return correlation | one complementary flat ensemble + `CandidateSpec` |

Provider dùng existing `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `MODEL_CHEAP`,
`LUNA_REASONING_EFFORT`; archive giữ provider model/version và prompt version.
Provider fail là terminal generator failure, không fallback random.

Output chỉ tham chiếu catalog version, parameter/risk configured và flat
composite. Nó không có shell, SQL, HTTP, filesystem, definition publishing,
BacktestEngine, result-table, leaderboard, queue, quota, pause/resume/cancel
hoặc stop-condition capability. Catalog/causality/risk/hash/duplicate/quota/cost
validation vẫn chạy trước queue admission. Chi tiết lifecycle ở
`specs/search-loop.md`.

### MarketInsightAgent - P2, default-off

Mục đích: tạo research insight read-only tại một as-of timestamp.

| Tool | Purpose | Loại |
|---|---|---|
| `market.get_snapshot` | Đọc normalized Candle/BBO qua `MarketDataPort` | read |
| `indicator.get_snapshot` | Đọc causal indicator snapshot | read |
| `news.get_recent_summary` | Đọc recent news/sentiment window | read |
| `experiment.get_recent_results` | Đọc authorized evaluation summary | read |
| `insight.save_draft` | Lưu insight và provenance | write |

Output bắt buộc có symbol, timeframe, data timestamp, regime, observations, risks,
confidence và model version. Không trả executable order. Muốn biến insight thành strategy
phải quay lại authoring -> test -> human approval.

## Forbidden capabilities

`ToolRegistry` không đăng ký và permission policy luôn deny:

- Generic shell/process execution.
- Generic SQL/direct database connection.
- Arbitrary HTTP/browser fetch.
- Unrestricted filesystem read/write.
- Docker/host socket control.
- Secret/credential/environment access.
- Direct Registry publish hoặc approval.
- Test fixture/expected output modification.
- Policy/budget modification.
- Direct exchange order.
- Direct Leaderboard write.
- Direct search stop-condition control.

## State machine

```text
DRAFT_CREATED
  -> SOURCE_READY
  -> SPEC_GENERATING
  -> SPEC_VALIDATING
  -> CODE_GENERATING
  -> POLICY_CHECKING
  -> SANDBOX_TESTING
       -> fail + còn budget: REPAIRING -> CODE_GENERATING
       -> fail + hết budget: FAILED
       -> pass: REVIEW_REQUIRED
            -> human approve: APPROVED -> PUBLISHED
            -> human reject: REJECTED
```

### Transition contract

| From | To | Actor | Guard |
|---|---|---|---|
| `DRAFT_CREATED` | `SOURCE_READY` | Source service | Source hash persisted |
| `SOURCE_READY` | `SPEC_GENERATING` | Orchestrator | Designer budget admitted |
| `SPEC_GENERATING` | `SPEC_VALIDATING` | Designer | Candidate spec revision saved |
| `SPEC_VALIDATING` | `CODE_GENERATING` | Validator/orchestrator | Schema, semantic, bounds, causality pass |
| `SPEC_VALIDATING` | `REPAIRING` | Orchestrator | Repairable error + budget remains |
| `CODE_GENERATING` | `POLICY_CHECKING` | Implementation | Artifact hash persisted |
| `POLICY_CHECKING` | `SANDBOX_TESTING` | Policy checker | Policy pass |
| `POLICY_CHECKING` | `REPAIRING` | Orchestrator | Repairable fail + budget remains |
| `SANDBOX_TESTING` | `REVIEW_REQUIRED` | Orchestrator | Full contract suite pass |
| `SANDBOX_TESTING` | `REPAIRING` | Orchestrator | Fail + budget remains |
| `REPAIRING` | `CODE_GENERATING` | Repair/orchestrator | New immutable revision saved |
| any repairable state | `FAILED` | Orchestrator | Budget exhausted/non-repairable |
| `REVIEW_REQUIRED` | `APPROVED` | Human reviewer | Reviewed hashes match current frozen package |
| `REVIEW_REQUIRED` | `REJECTED` | Human reviewer | Reason persisted |
| `APPROVED` | `PUBLISHED` | Publisher | Publish-once + compatible Registry target |

Transition write dùng compare-and-set `(run_id, expected_state, aggregate_version)` và
idempotency key. Illegal/stale transition trả `CONFLICT`; không tự đoán state mới.

## Persistence

Tất cả bảng dưới đây do Python `research` sở hữu write:

| Entity | Trường chính | Invariant |
|---|---|---|
| `strategy_drafts` | owner, source type/ref/hash, mode, current revision, status | unique `(owner_id,idempotency_key)` |
| `strategy_draft_revisions` | draft, revision, spec JSON/hash, actor, run | unique `(draft_id,revision)`, immutable |
| `agent_runs` | draft, role, state, versions, budget, timestamps | legal compare-and-set transition |
| `agent_attempts` | run, attempt number, input/output hash, error/evidence | unique `(run_id,attempt_no)`, immutable |
| `strategy_artifacts` | revision, language, object ref, hash, compiler version | unique artifact hash |
| `sandbox_runs` | artifact, image/policy/fixture versions, report, resources | idempotent run key |
| `strategy_approvals` | reviewer, decision, reviewed hashes, reason | decision binds exact hashes |
| `strategy_versions` | version, spec/artifact hashes, provenance | append-only, publish-once |
| `tool_invocations` | run/attempt/tool/version/request hash/result/evidence | auditable write idempotency |
| `news_extractions` | content/model/prompt/schema hashes, quality/result | deterministic cache key |
| `insight_drafts` | as-of data, observation/risk/confidence/evidence | no order relation |
| discovery candidate provenance | candidate/model/prompt/input hash/provider version | immutable; references Python-owned search archive |

Large source/report được lưu content-addressed trong artifact/evidence store; database giữ
hash, media type, size và object reference. Không nhét arbitrary HTML/source/report vào
agent event hoặc WebSocket frame.

## ModelGateway và provenance

Mỗi model call persist:

- Provider/adapter ID và version.
- Model ID/version hoặc deployment ID.
- Prompt template ID/version và system policy version.
- Tool manifest hash.
- Input evidence hashes và output hash.
- Structured-output schema version.
- Token/input/output usage, latency, status và safe error.
- Correlation/run/attempt IDs.

Model output không được xem là valid chỉ vì JSON parse được. Domain validator và policy
gate luôn chạy sau model.

## Sandbox policy

Generated Python chỉ chạy trong disposable sandbox:

- Non-root identity.
- Network disabled.
- Không database, secret, exchange credential hoặc host socket.
- Không package installation.
- Import allowlist.
- Read-only base filesystem, một bounded writable workspace.
- CPU, RAM, process, syscall, output-size và wall-clock limit.
- Deterministic fixture, random seed và time source khi cần.
- Structured report; persist image digest, policy version, fixture version, duration và
  resource usage.

Contract suite tối thiểu:

1. Import và Strategy protocol conformance.
2. Parameter schema/default/bounds.
3. Signal action/price/size validation.
4. Không network/DB/unrestricted filesystem.
5. Không future candle/indicator access.
6. Determinism với identical input.
7. Timeout/resource bound.
8. Exception isolation.
9. Realtime/backtest parity cho cùng spec/version.
10. Preview fixture đủ evidence cho reviewer.

Policy violation fail trước sandbox execution. Sandbox pass không bỏ qua human review.

## Human review, approval và publishing

Review package hiển thị:

- Sanitized source và source hash.
- StrategySpec diff/revision/hash.
- Generated artifact/source/hash và compiler/model provenance.
- Policy report.
- Sandbox contract/fixture report và preview.
- Repair attempt history.
- Exact target Registry mode: DSL runtime hoặc custom deployed plugin.

Approval request chứa exact `draft_revision`, `spec_hash`, `artifact_hash`,
`policy_version`, `sandbox_run_id` và `sandbox_report_hash`. Nếu bất kỳ giá trị nào thay đổi,
approval trả `STALE_REVISION`; user phải review lại.

DSL-backed approved strategy có thể vào safe Python runtime qua declarative compiler/interpreter
semantics. Custom Python approved chỉ tạo patch/PR/build/deploy artifact; Registry load trusted
plugin sau deploy/restart, không hot-load source tùy ý.

## Crash recovery, retry và cancellation

- Worker claim job bằng lease token; heartbeat định kỳ.
- Lease takeover chỉ tiếp tục từ persisted state và current immutable revision.
- Mỗi attempt có unique number; retry cùng idempotency key trả existing result.
- Dependency failure có exponential backoff trong deadline/budget; không lặp vô hạn.
- User cancellation là persisted terminal intent; running model/tool/sandbox nhận cancellation.
- Worker cũ mất lease không được ghi state/result.
- Manual retry sau `FAILED` tạo agent run mới liên kết run cũ; không reset lịch sử.

## Event và public progress

Python commit state + outbox cùng transaction, sau đó gửi `POST /internal/events` tới Go.
Go de-duplicate `event_id` và fan-out theo authorized topic.

Event tối thiểu:

- `strategy_draft.state_changed`
- `agent_run.progressed`
- `agent_attempt.completed`
- `sandbox_run.completed`
- `strategy_review.required`
- `strategy_version.published`
- `news.extraction.completed`

Event envelope có `event_id`, `event_type`, `aggregate_id`, `aggregate_version`,
`occurred_at`, `correlation_id`, `principal_id`, `payload_schema_version`. Event chỉ chứa
summary/reference; source, prompt và report lớn không phát qua WSS.

## Observability

Metric tối thiểu:

- `agent_runs_total{agent_type,terminal_status}`
- `agent_state_duration_seconds{agent_type,state}`
- `agent_tool_calls_total{agent_type,tool,status}`
- `agent_tool_latency_seconds{tool}`
- `agent_model_calls_total{agent_type,model,status}`
- `agent_model_tokens_total{agent_type,model,direction}`
- `agent_repair_attempts_total{result}`
- `sandbox_runs_total{policy_version,status}`
- `sandbox_resource_usage{resource}`
- `strategy_publish_conflicts_total{reason}`

Không dùng `principal_id`, `draft_id`, `run_id` làm Prometheus label. Các ID nằm trong log/trace.

Alert tối thiểu: run stuck quá state deadline, repeated policy violation, sandbox isolation
signal, model failure rate, tool permission denial spike và outbox delivery backlog.

## Kịch bản lỗi

| Tình huống | Phản ứng |
|---|---|
| Prompt yêu cầu tự cấp shell/HTTP | Tool permission deny; audit `PERMISSION_DENIED` |
| URL redirect vào private IP | Safe Fetcher chặn trước khi agent thấy content |
| Model trả JSON sai schema | `INVALID_INPUT`; bounded retry nếu policy cho phép |
| Draft đổi trong lúc model chạy | Write trả `STALE_REVISION`; discard proposal cũ |
| Generated import bị cấm | Policy fail; không khởi tạo sandbox |
| Sandbox timeout/OOM | Structured failure; repair nếu còn budget |
| Worker chết giữa repair | Lease takeover resume từ persisted attempt/state |
| Hết repair budget | `FAILED`; không tự tăng budget |
| Reviewer approve artifact cũ | `STALE_REVISION`; không publish |
| Publish request lặp | Trả existing version hoặc deterministic conflict |
| AI adapter down | Persist unavailable/failure; không fake success |
| Go event endpoint down | Python state vẫn đúng; outbox retry, UI refetch theo version |

## Ràng buộc

- Default repair attempts = 3, configurable bởi operator policy và persist per run.
- Mỗi model/tool/sandbox call có deadline; workflow không có `while(true)`.
- Tool output chỉ chứa dữ liệu principal được phép đọc.
- Sandbox và tool policy version là một phần reproducibility fingerprint.
- Discovery LLM candidate/insight luôn có model/prompt/input-history provenance.
- P2 feature không được làm thay đổi deterministic engine/evaluator/ranking contracts.

## Tiêu chí chấp nhận

- [ ] AC-01: Text input tạo valid draft StrategySpec và immutable revision hash.
- [ ] AC-02: Approved URL được safe-fetch/sanitize; prompt injection không cấp thêm tool.
- [ ] AC-03: Generated Python có artifact hash, compiler/model/prompt provenance.
- [ ] AC-04: Forbidden import fail ở policy gate trước sandbox.
- [ ] AC-05: Sandbox không có network, DB, secret, host socket hoặc package install.
- [ ] AC-06: Failing fixture tạo structured report và repair attempt mới tối đa 3 lần.
- [ ] AC-07: Worker restart không mất state, duplicate attempt hoặc publish hai lần.
- [ ] AC-08: Test pass chỉ chuyển `REVIEW_REQUIRED`, không tự publish.
- [ ] AC-09: Rejection không tạo Registry-visible version.
- [ ] AC-10: Approval publish đúng exact reviewed spec/artifact/report fingerprint.
- [ ] AC-11: Re-approval/publish cùng idempotency key trả cùng result hoặc conflict rõ ràng.
- [ ] AC-12: Realtime và backtest resolve cùng approved StrategyVersion/runtime.
- [ ] AC-13: News agent chỉ chạy sau deterministic quality gate fail và không có URL tool.
- [ ] AC-14: Discovery LLM không bypass queue, quota, de-dup hoặc stop condition; provider failure được persist, không random fallback.
- [ ] AC-15: Market insight không tạo order/publish/search candidate trực tiếp.
- [ ] AC-16: Audit truy được principal -> run -> attempt -> model/tool -> artifact -> approval.

## Open decisions và default

| Quyết định | Default target |
|---|---|
| Full SMC | Architecture-supported, không phải MVP implementation |
| Custom arbitrary Python | Advanced PR/build/deploy path |
| DSL strategy availability | Safe runtime admission sau approval |
| Repair attempts | 3 |
| Authoring URL | Explicit allowlist + Safe Fetcher |
| Discovery LLM generator | Discovery MVP; typed `new`/`improve`/`combine`, controller-owned |
| Market Insight | P2, read-only, default-off |

Thay đổi bất kỳ default nào phải cập nhật proposal, design, authoring spec, traceability,
backlog và các diagram 21, 25-33 trong cùng pull request.
