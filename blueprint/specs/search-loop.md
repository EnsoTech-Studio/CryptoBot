# Đặc tả: Python Search Loop

Trạng thái: Python canonical  
Owner: Python `research`  
Runtime seam hiện có: `app/services/search.py`

## Mô tả

Search Loop tạo bounded `CandidateStrategy`, submit candidate qua durable Python job queue,
chờ Backtest -> Evaluation -> Ranking và dừng theo explicit stop conditions. Random Search là
MVP bắt buộc. Domain-Guided chứng minh generator replaceability. Candidate Discovery Agent là
P2 optional adapter; nó không thay deterministic engine/evaluator/ranking.

Không có Go CandidateGenerator/SearchRun. Go chỉ auth/quota/proxy public command/query và
fan-out persisted progress.

## Contract

### SearchRun create

```json
{
  "strategy_space": {
    "allowed_strategy_ids": ["ma_cross", "rsi", "bollinger", "support_resistance"],
    "composite": {
      "min_children": 1,
      "max_children": 4,
      "allowed_policies": ["majority_vote", "weighted_vote"]
    },
    "parameter_bounds": {
      "ma_cross.fast": {"type": "integer", "min": 5, "max": 50},
      "ma_cross.slow": {"type": "integer", "min": 20, "max": 200}
    }
  },
  "generator": {
    "id": "random",
    "version": "v1",
    "seed": 42
  },
  "experiment_template": {
    "symbol": "BTCUSDT",
    "dataset_id": "01J_DATASET",
    "initial_capital": 1000.0,
    "position_policy": {"kind": "fixed_notional", "entry_notional": 100.0},
    "execution": {"fee_bps": 10.0, "slippage_bps": 2.0}
  },
  "stop_conditions": {
    "max_candidates": 50,
    "max_duration_seconds": 1800,
    "max_non_improving": 20
  },
  "max_in_flight": 4,
  "idempotency_key": "search-create-01"
}
```

Ít nhất một finite stop condition bắt buộc; target yêu cầu `max_candidates` luôn có giá trị.
API, DB constraint và runtime cùng enforce.

### CandidateStrategy

```json
{
  "definition": {
    "strategy_id": "composite",
    "version": "v1",
    "children": [
      {"strategy_id": "ma_cross", "version": "v1", "parameters": {"fast": 20, "slow": 50}, "weight": 1.0},
      {"strategy_id": "rsi", "version": "v1", "parameters": {"period": 14}, "weight": 1.0}
    ],
    "combination": {"policy": "majority_vote", "threshold": 0.0, "encoding": "signed-v1"}
  },
  "candidate_hash": "sha256:...",
  "generated_by": "random@v1",
  "generation_meta": {
    "seed": 42,
    "ordinal": 17,
    "search_space_hash": "sha256:..."
  }
}
```

Hash dùng canonical JSON sau materialize defaults/order. Unique `(search_run_id,candidate_hash)`
de-duplicate proposal/retry.

### Search progress

```json
{
  "search_run_id": "01J_SEARCH",
  "status": "running",
  "generated": 25,
  "queued": 4,
  "running": 3,
  "tested": 18,
  "failed": 1,
  "duplicate_skipped": 2,
  "best_score": 0.8123,
  "current_candidate_ref": "candidate:sha256:...",
  "elapsed_seconds": 420,
  "aggregate_version": 37
}
```

Progress là persisted summary; WSS frame có sequence/version, client reconnect refetch snapshot.

## CandidateGenerator port

```python
class CandidateGenerator(Protocol):
    def definition(self) -> GeneratorDefinition: ...
    def propose(self, context: GenerationContext) -> list[CandidateStrategy]: ...
```

Generator chỉ tạo candidate DSL. Nó không nhận Backtest Engine, DB session, RankingService
hoặc stop-control handle.

### Random Generator - MVP

- Seed persist trong run snapshot.
- Sampling deterministic theo seed/ordinal/search-space hash.
- Tôn trọng type/bounds/family/composite policy.
- Không đảm bảo unique; standard de-dup layer xử lý.

### Domain-Guided Generator

- Dùng deterministic rules theo family/parameter compatibility.
- Cùng `GenerationContext` port như Random.
- Thay generator bằng config; Backtest/Evaluator/Ranking không đổi.

### CandidateDiscoveryAgent - P2

Agent chỉ có tools:

- `search.get_search_space`
- `search.get_tested_hashes`
- `leaderboard.get_summary`
- `candidate.validate`
- `candidate.estimate_cost`
- `candidate.submit_batch`

Required provenance: generator/agent version, model, prompt, tool manifest, input-history hash,
search-space hash và candidate hash. Agent cannot:

- Direct-call Backtest Engine.
- Write candidate/result/Leaderboard tables trực tiếp.
- Bypass quota/de-dup/queue/admission.
- Pause/resume/cancel hoặc sửa stop condition.
- Tự tăng cost/tool/token budget.

## Luồng chính

### A. Tạo run

1. Browser gửi public command tới Go.
2. Go auth/RBAC/quota/schema/body-size và signed principal context.
3. Python validate catalog/search space/dataset/execution/stop conditions.
4. Python materialize immutable run snapshot + create row/outbox atomically.
5. Trả `202 + search_run_id`; client subscribe/refetch progress qua Go.

### B. Vòng lặp bounded

1. Search coordinator claim run lease.
2. Evaluate stop/cancel/pause trước generate.
3. Tính capacity `max_in_flight - queued - running`.
4. Gọi configured generator để propose bounded batch.
5. Candidate validator kiểm schema, parameter bounds, causality và catalog/version.
6. Canonicalize/hash/de-duplicate theo run/history.
7. Admission kiểm remaining candidate quota và estimated worker cost.
8. Insert candidate + experiment/job + outbox trong transaction.
9. Python Workers backtest; Evaluator persist metrics; Ranking update Top-K idempotently.
10. Coordinator update counters/best/non-improving và lặp từ bước 2.

Không polling busy vô hạn: coordinator dùng job/event wakeup và bounded reconcile interval.

### C. Stop conditions

Run dừng khi bất kỳ điều kiện bật nào đạt:

- `tested + terminal_failed >= max_candidates`.
- Wall-clock active duration >= `max_duration_seconds`.
- `non_improving_count >= max_non_improving`.
- Human `cancel_requested`.

`paused` ngừng tạo candidate mới nhưng không giết job đã chạy; counters vẫn reconcile. Resume
idempotent. Cancel không rank partial/incomplete result và không enqueue thêm.

### D. Completion

Run chỉ `completed` khi stop reason persisted và mọi in-flight candidate đã terminal theo
chosen drain/cancel policy. Completion + outbox atomic. Top-K query đọc Python ranking source
qua Go proxy.

## Cost và quota

Admission estimate tối thiểu:

```text
estimated_candle_steps = candidate_count * dataset_candle_count * strategy_cost_factor
```

Quota có:

- Max concurrent search runs per principal.
- Max candidates per run.
- Max in-flight candidates.
- Max candle steps/worker seconds.
- Optional model/tool token/cost cho Candidate Discovery.

Go edge enforce public admission coarse quota; Python enforce authoritative domain quota trong
cùng transaction tạo work để tránh race.

## Persistence

Python-owned:

- `search_runs`: snapshot/status/stop/counters/lease/version.
- `search_candidates`: immutable definition/hash/generator/provenance/status.
- `experiments`, `backtest_jobs`, `backtest_runs`.
- `evaluations`, `leaderboard_entries`.
- `domain_events`/outbox.

Candidate status progression idempotent. Duplicate event/result consumer dùng event ID và
unique result keys.

## Kịch bản lỗi

| Tình huống | Phản ứng |
|---|---|
| Thiếu finite stop condition | Reject create + DB constraint |
| Unknown strategy/version/parameter | Reject candidate before enqueue |
| Generator trả duplicate | Increment `duplicate_skipped`, không tạo job |
| Generator exception | Persist failure; retry bounded theo run policy |
| Agent đề xuất ngoài search space | `candidate.validate` reject |
| Cost vượt quota | Reject/defer batch; không bypass |
| Worker/candidate fail | Mark failed, run tiếp tục nếu stop chưa đạt |
| Coordinator chết | Lease takeover + reconcile persisted counters |
| Pause request lặp | Trả current paused state idempotently |
| Cancel khi có in-flight | Persist cancel intent, apply drain/cancel policy |
| Duplicate evaluation event | Ranking consumer idempotent |
| Ranking unavailable | Evaluation facts remain; outbox/reconcile retry |

## Ràng buộc

- Random Search là MVP.
- Stop conditions luôn finite và authoritative ở SearchRun.
- Generator chỉ output CandidateStrategy DSL.
- Backtest/Evaluation/Ranking không phụ thuộc generator type.
- Candidate hash/provenance immutable.
- Python sở hữu search state/tables; Go không có generator/domain write.
- Candidate Discovery/Market Insight default-off không chặn MVP.

## Tiêu chí chấp nhận

- [ ] AC-01: Run thiếu `max_candidates`/finite stop bị API và DB từ chối.
- [ ] AC-02: Random generator deterministic với cùng seed/context.
- [ ] AC-03: Duplicate candidate hash không tạo duplicate job.
- [ ] AC-04: Random -> Domain-Guided đổi qua config; Backtest/Evaluator/Ranking core diff = 0.
- [ ] AC-05: Pause ngừng enqueue mới; resume/cancel idempotent.
- [ ] AC-06: Run dừng đúng max candidate/duration/non-improving/cancel.
- [ ] AC-07: Coordinator crash/takeover không mất counter hoặc duplicate candidate.
- [ ] AC-08: Candidate failure isolated và reflected trong progress.
- [ ] AC-09: Top-K chỉ nhận terminal valid evaluation.
- [ ] AC-10: Agent candidate ngoài space/quota bị reject trước queue.
- [ ] AC-11: Candidate Discovery không có direct Backtest/Leaderboard/stop tool.
- [ ] AC-12: Architecture test chứng minh Go không implement SearchRun/CandidateGenerator.
