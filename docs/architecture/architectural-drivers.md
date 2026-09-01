# Architectural Drivers & Quality Attributes

Tài liệu này chuyển các ghi chú trong `docs/note-update-require.txt` thành
Architecturally Significant Requirements (ASR) có thể kiểm chứng. Canonical
technical design và ADR vẫn nằm trong `blueprint/design.md`.

## Drivers

| ID | Quality attribute / ASR | Thiết kế đang dùng | Evidence bắt buộc |
| --- | --- | --- | --- |
| ASR-01 | Realtime data không làm strategy đọc nến chưa đóng; mất kết nối không âm thầm tạo gap | Go Binance adapter chuẩn hoá `KlineUpdate`/`Candle`/BBO, checkpoint + REST backfill + WebSocket hub | Go adapter/application tests; demo `/markets/status` và candle continuity sau reconnect |
| ASR-02 | Thêm strategy, generator hoặc market provider không sửa runtime core/frontend | Python Strategy Plugin Registry, `CandidateGenerator` port, Go `MarketDataProvider` port; DTO market có `provider` | Plugin/generator contract tests; provider fixture proof |
| ASR-03 | Mỗi backtest/leaderboard có thể tái lập và truy nguồn | Immutable dataset + strategy snapshot, BBO replay, result hash, persisted trade/equity/evaluation provenance | Deterministic fixture + rehearsal smoke + provenance query |
| ASR-04 | Backtest/search vẫn đúng khi worker/event consumer retry hoặc chết | PostgreSQL queue, lease token, heartbeat, `FOR UPDATE SKIP LOCKED`, transactional outbox, idempotent consumer | Integration queue tests; controlled worker/event-worker recovery scenario |
| ASR-05 | AI và generated code không có quyền hệ thống hoặc publish tự động | AI inference-only; allowlisted/sanitized fetch; typed tools; AST policy + no-network Docker sandbox; human review | Authoring, sandbox, tool-policy and adaptive-news tests |
| ASR-06 | Core market/backtest vẫn hoạt động khi AI/news unavailable | AI gọi qua timeout và unavailable là trạng thái thật; chart/backtest technical không phụ thuộc sentiment | Dependency-unavailable unit/integration scenario |
| ASR-07 | Tăng worker replica không đổi public API hay immutable job contract | `202` async experiment, same Python worker image, bounded inputs, PostgreSQL queue; Compose scale path | Queue-plan proof, API latency smoke, and measured load run before claiming throughput |
| ASR-08 | Browser chỉ truy cập Go edge và mỗi user chỉ thấy dữ liệu của mình | Go auth/RBAC/CSRF/quota; signed internal context; Research checks owner again | Auth/ownership integration tests and rehearsal register/refresh/logout |

## Trade-offs that must be stated in the presentation

| Decision | Benefit | Cost accepted | Revisit trigger |
| --- | --- | --- | --- |
| PostgreSQL queue instead of broker | Atomic job/result/outbox and fewer services | Queue throughput is bounded by PostgreSQL | Measured queue depth/oldest-job age makes PostgreSQL a bottleneck |
| Go edge + market, Python research runtime | Go owns public security/realtime; Python owns strategy ecosystem | Internal HTTP and two runtime processes | Team needs a simpler single-language stack or latency evidence says otherwise |
| Declarative DSL first, custom Python deployment path | Safe reviewable authoring and no hot-loading code | Some ideas cannot run immediately in Registry | Trusted build/deploy workflow is available and sandbox evidence supports it |
| Approved news sources with safe fetch | Prevents SSRF and prompt-injection network access | Users cannot make arbitrary browser-supplied fetches | Add an operator-approved source onboarding workflow, not arbitrary fetch |
| Docker Compose for delivery | Reproducible MVP and health checks | No cluster scheduler/autoscaling | Measured workload requires replicas across hosts |

## Honest performance boundary

`scripts/queue-scale-proof.sql` proves the claim query remains explainable at
100,000 queued rows inside a rolled-back transaction. It is **not** a claim
that the deployment executes 100,000 backtests. Throughput may only be claimed
after recording worker count, fixture size, duration, throughput, queue depth
and p95 API latency from a repeatable load run.

## Presentation evidence

```powershell
# Functional end-to-end
.\scripts\rehearsal-smoke.ps1 -ApiBaseUrl http://127.0.0.1:8080 -WebBaseUrl http://127.0.0.1:3000

# Queue-plan and readiness latency evidence
docker compose -f docker-compose.test.yml exec postgres-test psql -U cryptobot -d cryptobot -f /proof/queue-scale-proof.sql
py -3 scripts/api-latency-smoke.py --url http://127.0.0.1:8080/ready --requests 100

# Contract suites
py -3 -m pytest tests -q
cd server; go test -race ./...
cd ..\ai; py -3 -m pytest -q
cd ..\web; npm test; npm run lint; npx tsc --noEmit
```

The exact implementation coverage and remaining gaps are maintained in
[`../note-update-require-status.md`](../note-update-require-status.md) and
[`../../blueprint/traceability.md`](../../blueprint/traceability.md).
