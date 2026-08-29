# Đặc tả: AI Strategy Authoring

Trạng thái kiến trúc: `Designed`, runtime còn là target gap  
Nguồn: `[SRC-ADD]` - thêm strategy bằng natural language/URL, tạo draft trước code,
generate Python và có repair loop  
Owner: Python `research`; Go chỉ là public API/edge proxy

## Mô tả

Authoring nhận text, URL được phép hoặc declarative DSL, tạo một draft để người dùng xem
trước, sau đó mới tạo Python artifact. Artifact không được chạy hoặc publish chỉ vì model
đã sinh code: nó phải qua schema/semantic validation, AST/import policy, isolated sandbox,
bounded repair và human approval.

Luồng mặc định là DSL-backed:

```text
Text / approved URL / DSL
  -> Safe Source Ingestor
  -> StrategyDesignerAgent
  -> validated StrategySpec revision
  -> StrategyImplementationAgent
  -> deterministic Python compiler
  -> policy check
  -> isolated contract/fixture tests
  -> REVIEW_REQUIRED
  -> human approval
  -> immutable StrategyVersion
  -> Python Strategy Registry
```

Custom Python là advanced path khi DSL không biểu diễn được yêu cầu. Nó vẫn qua policy và
sandbox nhưng không hot-load. Approval chỉ tạo patch/PR/build/deploy; Registry load trusted
plugin sau deploy/restart.

## Boundary

- Browser chỉ gọi Go public API.
- Go thực hiện auth, RBAC, quota, request/schema/size validation và ký principal context.
- Go proxy command/query tới Python `research`; Go không tạo spec/code và không ghi bảng draft.
- Python sở hữu draft, agent run, artifact, sandbox, approval và publish workflow.
- AI/LLM Adapter chỉ inference; không có domain DB credential và không approve/publish.
- Agent gọi narrow typed tools được định nghĩa trong `agent-architecture.md`.

## Contract

### Source input

```json
{
  "mode": "dsl",
  "source": {
    "type": "text",
    "text": "MA 20 cắt lên MA 50 thì LONG, cắt xuống thì SHORT"
  },
  "name_hint": "ma-cross-20-50",
  "idempotency_key": "authoring-create-01"
}
```

`source.type` là `text`, `approved_url` hoặc `dsl`. URL phải dùng HTTPS, match origin
allowlist, qua DNS/IP recheck sau từng redirect, size/type/time limit và sanitize trước khi
model nhìn thấy. Model chỉ nhận `document_id`/sanitized content, không nhận HTTP tool.

### Authoring mode

| Mode | Model tạo | Execution | Publishing |
|---|---|---|---|
| `dsl` | Declarative `StrategySpec` | Deterministic compiler/interpreter | Có thể admit vào safe runtime sau approval |
| `custom_python` | Python source proposal | Policy + disposable sandbox | PR/build/deploy, không hot-load |

Default/MVP là `dsl`. `custom_python` cần role/policy riêng và phải hiển thị cảnh báo advanced.

### StrategySpec tối thiểu

```json
{
  "schema_version": "strategy-spec/v1",
  "strategy_id": "generated.ma_cross_20_50",
  "display_name": "MA Cross 20/50",
  "family": "trend",
  "parameters": {
    "fast_period": {"type": "integer", "default": 20, "minimum": 2, "maximum": 200},
    "slow_period": {"type": "integer", "default": 50, "minimum": 3, "maximum": 400}
  },
  "indicators": [
    {"id": "fast", "kind": "sma", "period": "$fast_period"},
    {"id": "slow", "kind": "sma", "period": "$slow_period"}
  ],
  "rules": {
    "long_entry": {"op": "crosses_above", "left": "fast", "right": "slow"},
    "short_entry": {"op": "crosses_below", "left": "fast", "right": "slow"},
    "exit": {"op": "opposite_signal"}
  },
  "warmup_bars": 50
}
```

Schema validator kiểm shape/type. Semantic validator kiểm:

- Strategy/indicator/operator có trong allowlist catalog.
- Bounds/default/relationship hợp lệ, ví dụ `fast_period < slow_period`.
- Chỉ dùng current/past causal values.
- Warmup đủ cho indicator dependency.
- Output action thuộc `LONG | SHORT | EXIT | HOLD` theo runtime contract.
- Không chứa code, URL, import, query hoặc tool instruction trong DSL field.

### Draft view

```json
{
  "draft_id": "01J_DRAFT",
  "mode": "dsl",
  "status": "REVIEW_REQUIRED",
  "current_revision": 3,
  "source_hash": "sha256:...",
  "spec_hash": "sha256:...",
  "artifact_hash": "sha256:...",
  "policy_report_ref": "evidence:sha256:...",
  "sandbox_report_ref": "evidence:sha256:...",
  "preview_ref": "evidence:sha256:...",
  "repair_attempts_used": 1,
  "repair_attempts_max": 3
}
```

### Approval command

```json
{
  "draft_id": "01J_DRAFT",
  "revision": 3,
  "spec_hash": "sha256:...",
  "artifact_hash": "sha256:...",
  "sandbox_report_hash": "sha256:...",
  "decision": "approve",
  "reason": "Reviewed rules, artifact and fixture preview",
  "idempotency_key": "approval-01"
}
```

Approval không tham chiếu "latest". Mọi hash/revision phải đúng frozen review package.

## Persistence

Python-owned entities:

- `strategy_drafts`: owner, source type/ref/hash, mode, current revision, status.
- `strategy_draft_revisions`: immutable spec/code revision và hash.
- `agent_runs`, `agent_attempts`: role/model/prompt/budget/state/evidence.
- `strategy_artifacts`: source/object ref, artifact hash, compiler version.
- `sandbox_runs`: image/policy/fixture versions, report, resource usage.
- `strategy_approvals`: human decision bound exact hashes.
- `strategy_versions`: immutable published fingerprint.

Unique/invariant:

- `(owner_id, create_idempotency_key)` tạo đúng một draft.
- `(draft_id, revision)` immutable và tăng đơn điệu.
- `(agent_run_id, attempt_no)` immutable.
- Artifact content-addressed theo SHA-256.
- Approval khác current frozen fingerprint trả `STALE_REVISION`.
- Publish-once theo approved fingerprint; retry idempotent.

## Luồng chính

### A. Tạo source và draft

1. Browser gửi text/approved URL/DSL tới Go.
2. Go xác thực owner, role, request size, source policy và quota.
3. Go ký service/principal/correlation context, proxy tới Python.
4. Python tạo `strategy_drafts` + outbox trong transaction và trả `202`.
5. Với URL, Safe Source Ingestor fetch/sanitize/persist document + content hash.
6. Python chuyển `DRAFT_CREATED -> SOURCE_READY` idempotently.

### B. Thiết kế StrategySpec

1. Orchestrator tạo Designer run với budget/prompt/tool manifest version.
2. Designer chỉ dùng source/catalog/schema/validation tools.
3. Candidate spec được validate schema + semantic + bounds + causality.
4. Valid spec được lưu thành immutable draft revision.
5. Nếu intent thiếu và không thể suy ra an toàn, workflow dừng để user bổ sung; model không
   tự bịa rule/risk.

### C. Tạo Python artifact

1. Orchestrator chuyển valid revision sang Implementation Agent.
2. DSL mode gọi deterministic compiler; cùng spec/compiler version luôn tạo cùng bytes/hash.
3. Custom mode lưu source proposal riêng, không ghi source tree production.
4. AST/import policy checker chạy trước sandbox.
5. Artifact/report/provenance được persist trước state transition.

### D. Sandbox và repair

1. Sandbox chạy contract/fixture suite trong môi trường no-network/no-DB/non-root.
2. Report có pass/fail, structured error, resource usage và evidence hash.
3. Fail + còn budget: orchestrator chuyển `REPAIRING`; Repair Agent đọc bounded context/report.
4. DSL mode patch spec rồi compile lại; custom mode patch isolated source draft.
5. Mọi patch tạo revision/artifact/sandbox run mới; không ghi đè evidence cũ.
6. Sau tối đa 3 attempt hoặc non-repairable failure, chuyển `FAILED`.

### E. Review, approve và publish

1. Chỉ policy + full sandbox pass mới chuyển `REVIEW_REQUIRED`.
2. UI hiển thị source, spec diff, artifact, policy report, sandbox report, preview và repair history.
3. Human approve/reject exact frozen hashes.
4. Reject -> `REJECTED`, không Registry visibility.
5. Approve -> `APPROVED`; publisher verify fingerprint và tạo immutable `StrategyVersion`.
6. DSL path admit vào safe Python runtime; custom path xuất patch/PR/build/deploy.
7. Publish commit + outbox cùng transaction; Go nhận persisted event và fan-out.

## Generated-code policy

Policy checker deny ít nhất:

- Import ngoài allowlist.
- Network, subprocess, reflection/dynamic import, eval/exec.
- Database/ORM/client, filesystem tùy ý, environment/secret access.
- Infinite/unbounded loop và thread/process creation.
- Global mutable state không được contract cho phép.
- Current wall clock/randomness không injected.
- Future candle/indicator access.
- Monkey patch test/runtime hoặc catch/ignore cancellation.

DSL compiler chỉ phát source từ allowlisted templates/AST nodes; raw user/model text không
được nối trực tiếp thành Python statement.

## Sandbox contract suite

1. Import và Python Strategy protocol conformance.
2. Parameter schema/default/bounds.
3. Indicator dependency và warmup.
4. Signal action/price/size validity.
5. No network/DB/secret/unrestricted filesystem.
6. No look-ahead.
7. Determinism với identical input/seed.
8. Timeout/memory/output/process limits.
9. Exception isolation.
10. Realtime/backtest parity cùng StrategyVersion.
11. Preview fixture có signal/overlay/trade evidence để review.

## Kịch bản lỗi

| Tình huống | Phản ứng |
|---|---|
| URL không allowlist hoặc resolve private IP | `SOURCE_REJECTED`, không gọi model |
| HTML chứa prompt injection | Chỉ là data; tool policy không đổi |
| Model trả spec sai schema | Structured validation error; bounded regenerate |
| Intent thiếu điều kiện exit | Dừng yêu cầu user bổ sung, không bịa |
| Draft bị sửa khi agent đang chạy | Expected revision fail `STALE_REVISION` |
| Compiler output không deterministic | Build fail; không tạo review package |
| Forbidden import/API | Policy fail trước sandbox |
| Sandbox timeout/OOM | Structured report; repair nếu còn budget |
| Repair lặp cùng output hash | Terminate attempt sớm; không đốt hết budget vô ích |
| Worker chết | Lease takeover resume từ persisted state |
| Reviewer approve revision cũ | `409 STALE_REVISION` |
| Publish retry | Trả existing StrategyVersion hoặc conflict rõ ràng |

## Ràng buộc

- Go không ghi `strategy_drafts`, artifact, sandbox, approval hoặc strategy version table.
- AI adapter không có DB credential và không nhận generic tool.
- Default repair budget = 3; operator policy có thể hạ nhưng agent không thể tăng.
- Mọi model/tool/sandbox call có deadline/cancellation và audit.
- Large document/source/report đi qua immutable reference, không nhồi vào event/WSS.
- Custom Python không hot-load.
- Realtime và backtest dùng cùng approved immutable runtime/version.

## Tiêu chí chấp nhận

- [ ] AC-01: Text input tạo draft preview trước code generation.
- [ ] AC-02: Approved URL qua SSRF guard/sanitize và persist `source_hash`.
- [ ] AC-03: Prompt injection không thay tool manifest/permission/budget.
- [ ] AC-04: Valid spec có schema/semantic/causal evidence.
- [ ] AC-05: DSL compiler tạo byte-identical artifact cho cùng spec/compiler version.
- [ ] AC-06: Artifact persist hash + compiler/model/prompt/tool-policy provenance.
- [ ] AC-07: Policy violation không khởi động sandbox.
- [ ] AC-08: Sandbox chứng minh no-network/no-DB/no-secret/read-only isolation.
- [ ] AC-09: Failing fixture tạo structured report và bounded repair tối đa 3.
- [ ] AC-10: Restart không mất draft hoặc duplicate attempt.
- [ ] AC-11: Pass chỉ đến `REVIEW_REQUIRED`; không auto-publish.
- [ ] AC-12: Approval/rejection bind exact frozen fingerprint.
- [ ] AC-13: Publish idempotent và chỉ exact reviewed version vào Registry.
- [ ] AC-14: Custom Python approval không hot-load; chỉ PR/build/deploy.
- [ ] AC-15: Realtime/backtest parity pass cho published DSL StrategyVersion.

## Implementation status

Tại thời điểm blueprint v1.5, repository đã có Python Strategy Registry/Runtime và các
service backtest/evaluation/search/ranking, nhưng chưa có complete authoring orchestrator,
agent tables, compiler, policy checker, sandbox, approval/publisher hoặc UI review flow.
Các AC trên là implementation gates, không phải bằng chứng đã đạt.
