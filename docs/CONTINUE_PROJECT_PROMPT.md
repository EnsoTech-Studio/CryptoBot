# Prompt bàn giao hiện tại — CryptoBot

> Phần này là nguồn bàn giao mới nhất (01/09/2026) và **ghi đè các ghi chú
> legacy bên dưới**. Hãy đọc toàn bộ phần này trước khi thao tác.

Bạn tiếp quản repository **CryptoBot**. Tiếp tục đồ án từ trạng thái hiện có;
không làm lại từ đầu và không xoá/revert thay đổi chưa commit của người trước.

## Nguồn yêu cầu theo thứ tự ưu tiên

1. `Crypto Strategy Lab – Đồ án cuối kỳ.pdf`.
2. `docs/note-update-require.txt` — yêu cầu cập nhật từ giảng viên.
3. `blueprint/` (đặc biệt `design.md`, specs, ADR, diagrams, traceability).
4. `docs/note-duc.txt` chỉ là checklist lịch sử; phần tóm tắt của nó có thể
   lỗi thời.

Đích đến: code, blueprint, docs và bằng chứng kiểm thử khớp nhau. Không ghi
"hoàn thành" nếu chỉ có fixture/mock/sơ đồ.

## Quy tắc bắt buộc

- Bắt đầu bằng `git status --short`, `git diff --check`, đọc diff hiện có và
  đọc prompt này. Giữ toàn bộ thay đổi chưa commit của người trước.
- Dùng `apply_patch` khi sửa file. Không `git reset --hard`, không checkout/
  revert hàng loạt; không commit `.env`, API key, token hoặc database URL.
- Không tự chạy workload nặng hoặc crash test trên stack/database của người
  dùng. Benchmark/crash rehearsal chỉ dùng PostgreSQL hoặc container cô lập.
- TDD cho logic mới: thêm/sửa test, chạy để kiểm chứng hành vi, rồi chạy lại
  test pass.
- Phân biệt rõ trong tài liệu: `live`, `fixture/demo`, `mock/fallback`,
  `isolated benchmark`. Không suy diễn kết quả nhỏ thành benchmark 100k.
- Không tự cài package/framework mới hay push/commit nếu chủ repo chưa yêu cầu.

## Thay đổi chưa commit tại thời điểm bàn giao

Nếu người dùng đã push các file này, hãy xác minh bằng Git trước khi sửa.

```text
.env.example
README.md
app/config.py
app/event_worker.py
blueprint/traceability.md
docker-compose.stack.yml
docs/architecture/architectural-drivers.md
docs/note-update-require-status.md
scripts/backtest-throughput-benchmark.py
scripts/check_architecture.py
tests/integration/test_queue_integration.py
tests/test_integration_stack.py
```

## Đã hoàn thành trong worktree

1. **Regression kiến trúc/private network**
   - `scripts/check_architecture.py` chặn browser gọi trực tiếp AI, Research,
     PostgreSQL, Binance và fail nếu production Compose public port của
     `postgres`, `ai`, `research`.
   - `tests/test_integration_stack.py` có 4 test: migration mount, queue-proof
     replay range, production private ports, validation `EVENT_LEASE_SECONDS`.

2. **Crash recovery thật trên PostgreSQL cô lập**
   - `tests/integration/test_queue_integration.py` có 23 tests.
   - Backtest worker: process thật `python -m app.worker queue` lease job,
     bị `SIGKILL`, worker thay thế reclaim sau expiry; assert job/run attempt 2
     hoàn thành và không duplicate result event.
   - Event worker: process thật `python -m app.event_worker` bị kill sau outbox
     lease; worker thay thế reclaim và persist đúng một evaluation. Trigger
     test `crash_rehearsal_pause_evaluation` được xóa trong `finally`.
   - `EVENT_LEASE_SECONDS` là config dương mới, mặc định `60`; đã nối vào
     `EventWorker`, `docker-compose.stack.yml` và `.env.example`.

3. **Bằng chứng đã chạy**
   - Queue integration: `23 passed, 1 warning` với PostgreSQL 16 cô lập; hai
     crash-recovery test được chạy lặp lại và đều pass.
   - `tests/test_integration_stack.py`: `4 passed`.
   - `python scripts/check_architecture.py`: pass; `git diff --check`: pass.
   - Đã có từ trước: Go `go test ./...` pass; frontend 45 tests + lint +
     TypeScript pass; failure baseline 52 tests pass; k6 `/ready` 10 VU/60s:
     23,954 requests, p95 38.08ms, 0% error.

4. **Provider proof**
   - `RealtimeMarketProviderRegistry` và deterministic `okx_fixture` chứng
     minh frontend không phụ thuộc provider cụ thể.
   - Production chỉ register Binance. Không được gọi đây là live OKX
     integration.

## Throughput benchmark — đang tiếp tục

File mới `scripts/backtest-throughput-benchmark.py` đo đúng scope:
**PostgreSQL queue → worker processes → deterministic engine → persisted
result facts**. Nó không đo Go/API, frontend hoặc event-evaluation.

- Bắt buộc truyền `--database-url`, `--jobs`, và:

  ```text
  --confirm-isolated I_UNDERSTAND_THIS_WRITES_TO_AN_ISOLATED_DATABASE
  ```

  Harness tạo dữ liệu immutable và cố ý không cleanup, nên chỉ chạy trên DB
  disposable đã migration đầy đủ.
- Mẫu đã pass trên PostgreSQL 16 cô lập: **1,000 jobs, 4 workers, 60 candles**;
  7.318s; 136.642 job/s; p50 3670.410ms; p95 6988.348ms; 180,000 persisted
  equity points. Mẫu 12 jobs/2 workers cũng pass; harness yêu cầu ít nhất 50
  candles vì MA warm-up.
- **100,000 executed backtests vẫn Pending.** Không suy diễn từ mẫu 1k. Chỉ
  chạy 100k sau khi chủ repo đồng ý vì tốn tài nguyên; dùng DB mới cô lập và
  ghi machine, worker count, duration, p50/p95, errors, queue depth, disk.
- Có thể còn container tạm `cryptobot-throughput-sample-test`. Kiểm tra trước;
  chỉ xóa đúng container tạm sau khi xác minh an toàn.

## Trạng thái chính xác và thứ tự tiếp tục

- Failure injection: **Done (isolated rehearsal)**.
- 100k executed throughput: **Pending**.
- Provider thứ hai: **Partial — fixture only**, không phải live integration.
- Agent 2/3: **Deferred P2** vì scope SSRF/security chưa chốt; không tự làm
  crawler không giới hạn.
- Browser visual acceptance: **Partial**; trước đó không có browser connector,
  nên không claim đã visual review.

Làm tiếp theo thứ tự này:

1. Review diff và chạy các static/test nhanh nêu trên; xác nhận prompt vẫn
   khớp worktree.
2. Cập nhật `docs/note-update-require-status.md`, architectural drivers và
   traceability để phản ánh trung thực mẫu throughput 1k nếu các file đó chưa
   được cập nhật.
3. Chỉ khi được phép rõ ràng, chạy 100k bằng DB/container cô lập; cập nhật docs
   bằng số đo thực tế, không extrapolate.
4. Khi có browser thực, kiểm tra UI acceptance; sau đó mới sửa UI nếu có gap.
5. Không mở rộng Agent 2/3 hoặc live provider mới nếu chưa có yêu cầu/scope an
   toàn rõ ràng.

---

## Legacy handoff (historical only)

# Prompt tiếp tục CryptoBot (handoff)

Sao chép nguyên prompt bên dưới vào tài khoản/agent tiếp theo. Không đưa mật khẩu, API key, hoặc nội dung `.env` vào chat hay commit.

---

Bạn tiếp quản repo `CryptoBot` tại `D:\Đại học\Năm 3\KTPM\Final Project\CryptoBot`.

## Mục tiêu

Hoàn thiện đồ án Crypto Strategy Lab đúng theo:

1. `Crypto Strategy Lab – Đồ án cuối kỳ.pdf` (nguồn yêu cầu sản phẩm chính);
2. `docs/note-duc.txt` (checklist kiến trúc, slide, và các gap thầy/nhóm yêu cầu);
3. `blueprint/` (thiết kế kiến trúc, C4/UML, ADR, specs, traceability);
4. `docs/note-update-require.txt` (bản ghi yêu cầu cập nhật).

`docs/note-duc.txt` là **checklist tổng hợp rất rộng để build + thuyết trình**, nhưng phần “Tóm tắt tình hình” đầu file là lịch sử cũ và đã lỗi thời. Không lấy nó làm nguồn sự thật duy nhất; luôn đối chiếu PDF, blueprint và code chạy thật.

## Quy tắc làm việc

- Đọc kỹ source liên quan và trace flow trước khi sửa. Sửa đúng root cause, không vá UI/API từng chỗ.
- Bắt buộc TDD cho logic: viết test cho hành vi thiếu/lỗi, chạy để thấy fail, rồi mới implement và chạy pass.
- Dùng `apply_patch` để sửa file. Không `git reset --hard`, không xóa thay đổi của người khác.
- Không commit `.env`, secrets, database URL hay API key. Nếu secret đã lộ trong lịch sử chat, coi là cần rotate.
- Chỉ claim “Done” khi có bằng chứng chạy được; tách rõ `live`, `fixture/demo`, và `mock/fallback`.
- Không tự ý thêm package/framework. Ưu tiên code/pattern hiện có, Go/Python/JS standard library.
- Trước khi commit/push: xem `git diff`, chạy đúng test; dùng Git identity của máy hiện tại, không của agent.

## Trạng thái repo khi handoff

- Branch hiện tại: `feat/product-implementation`.
- Commit đã push trước đó: `8101c20 feat: complete strategy research workflows`.
- Repo **có thay đổi chưa commit** của phiên hiện tại. Không checkout/revert. Kiểm tra bằng `git status --short` trước khi làm.
- Các services local trước đó đã chạy: Next `3000`, Go API `8081`, AI FastAPI `8000`, research `8001`, worker/event/news/agent worker. API binary đang chạy có thể chưa bao gồm thay đổi Go chưa commit; chỉ restart sau khi hoàn tất/lúc cần smoke test.

## Những phần đã hoàn thành và đã có bằng chứng

- Product runtime: xác thực, market Binance REST/WebSocket + reconnect/backfill/persist, strategies, loop discovery/search, deterministic backtest queue, leaderboard/provenance, news ingestion/sentiment, LLM Groq, adaptive extraction/self-healing có boundary an toàn, strategy authoring draft/review/sandbox/retry.
- Architectural materials trong `blueprint/`: C4/UML, ADR, specs, traceability. Đã thêm `docs/architecture/architectural-drivers.md` và `docs/note-update-require-status.md` để mapping ASR/QA và trạng thái trung thực.
- Rehearsal toàn stack từng pass: `scripts/rehearsal-smoke.ps1 -ApiBaseUrl http://127.0.0.1:8081 -WebBaseUrl http://127.0.0.1:3000 -TimeoutSeconds 120`.
- Trước thay đổi hiện tại: Python `181 passed`; frontend 45 tests + lint + TypeScript pass; Go suite pass; AI 23 tests pass.
- Không phải toàn bộ dữ liệu mock: runtime mặc định dùng Binance, PostgreSQL và Groq khi có env. Fixture/demo chỉ dành cho offline/smoke/reference mode.

## Công việc đang dở (cần hoàn tất trước)

Mục tiêu là đóng các gap trong `note-duc.txt` bằng tài liệu/evidence thật, không bịa claim.

### 1. ASR/Quality Attributes

Đã thêm:

- `docs/architecture/architectural-drivers.md`
- `docs/note-update-require-status.md`

Cần rà lại, cập nhật liên kết README/traceability sau khi các evidence bên dưới hoàn tất. Những tài liệu này phải nói rõ: queue proof không phải benchmark throughput 100k backtest thật; fixture provider không phải tích hợp live provider thứ hai.

### 2. Proof provider có thể thay thế mà frontend không đổi

Đã TDD và implement các file chưa commit:

- `server/internal/ports/market.go`: thêm `RealtimeMarketProviderRegistry`.
- `server/internal/infrastructure/market/registry.go`: registry resolve provider theo ID.
- `server/internal/infrastructure/market/okx_fixture.go`: provider fixture `okx_fixture`, để chứng minh canonical contract mà không gọi OKX thật.
- `server/internal/infrastructure/market/registry_test.go`: test registry/fixture.
- `server/internal/application/market.go`: MarketService dùng registry và **scope StreamStatus theo đúng provider keys**; đây là root-cause fix tránh Binance stale làm OKX stale.
- `server/internal/application/market_test.go`: regression test `TestMarketServiceIsolatesStaleStatusToItsProviderKeys`.
- `server/cmd/api/main.go`: production hiện chỉ đăng ký Binance; fixture chỉ là proof test, không được claim OKX live.

Đã chạy pass:

```powershell
go test ./internal/application ./internal/infrastructure/market -count=1
go test ./...
```

Nếu muốn thêm provider live, phải có API contract/chứng cứ adapter thật và config rõ ràng; không tự đổi frontend.

### 3. 100k proof và failure evidence

Đã phát hiện script `scripts/queue-scale-proof.sql` cũ hỏng do migration 015 bắt buộc `experiments.replay_range_from/replay_range_to`. Đã viết static regression test trước trong `tests/test_integration_stack.py`, sau đó sửa SQL để insert hai trường này từ dataset.

Đã chạy pass:

```powershell
uv run pytest tests/test_integration_stack.py -q
docker compose -f docker-compose.test.yml exec -T postgres-test psql -U cryptobot -d cryptobot -f /proof/queue-scale-proof.sql
```

Kết quả local gần nhất: insert 100,000 experiments khoảng 6.141s, 100,000 jobs khoảng 4.031s, query-claim `EXPLAIN` khoảng 4.355ms và script `ROLLBACK`. Đây chỉ là **queue/query-plan proof**, không phải claim engine chạy 100k backtests.

Đã thêm nhưng cần kiểm tra tồn tại/nội dung rồi chạy:

- `scripts/k6-ready-smoke.js`: k6 readiness smoke (10 VU/60s mặc định; threshold p95 < 1s, error < 1%). `k6` chưa được cài trên máy, không tự cài nếu chưa được yêu cầu.
- `scripts/failure-contract-smoke.ps1`: chạy các test retry/idempotency/failure isolation của worker, agent, news; có `-IncludeIntegration` cho queue integration.

Chạy tiếp:

```powershell
.\scripts\failure-contract-smoke.ps1
Get-Command k6 -ErrorAction SilentlyContinue
# Chỉ khi k6 đã được cài:
k6 run -e API_BASE_URL=http://127.0.0.1:8081 .\scripts\k6-ready-smoke.js
```

Sau đó update `README.md`, `docs/architecture/architectural-drivers.md`, `docs/note-update-require-status.md`, và phần R14 trong `blueprint/traceability.md` bằng evidence thật. Không nói “100k backtests done” nếu chỉ có SQL proof.

## Gap còn lại sau handoff

Không được nói website/project “100% hoàn chỉnh” nếu chưa xử lý hoặc chủ động đưa vào P2:

1. Agent 2 Market Insight và Agent 3 web discovery toàn Internet: chưa có runtime hoàn chỉnh. Crawler hiện allowlist/SSRF-safe; unrestricted web fetch không nên tự thêm vì rủi ro bảo mật. Đưa P2 hoặc cần scope/approval rõ ràng.
2. Provider thứ hai hiện chỉ có fixture proof. Live provider thứ hai cần adapter thật, credentials/rate limit/reconnect test.
3. 100k engine throughput thật chưa benchmark end-to-end; chỉ có queue/query-plan 100k proof. Muốn claim full cần tạo workload cô lập, đo latency/throughput/DB, machine spec và report.
4. Failure-injection demo nên có evidence test/rehearsal; không chỉ slide. Script smoke ở trên là baseline.
5. UI phải được visual regression/Playwright review ở 100% zoom nếu task đánh giá screenshot/reference; không dùng zoom 90% để claim chuẩn.

## Cách xác minh cuối cùng

Chạy từ root repo, theo thứ tự. Khi full Python test chạm shared test DB, dừng worker/agent-worker và reseed lại trước khi restart:

```powershell
go test ./...
uv run pytest tests -q
cd web; npm test; npm run lint; npx tsc --noEmit; cd ..
.\scripts\failure-contract-smoke.ps1
.\scripts\rehearsal-smoke.ps1 -ApiBaseUrl http://127.0.0.1:8081 -WebBaseUrl http://127.0.0.1:3000 -TimeoutSeconds 120
git diff --check
git status --short
```

Nếu cần reseed test DB sau full test:

```powershell
.\scripts\stop-native-backend.ps1 -Services worker,agent-worker
docker compose -f docker-compose.test.yml exec -T postgres-test psql -U cryptobot -d cryptobot -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/05_reference_data.sql
docker compose -f docker-compose.test.yml exec -T postgres-test psql -U cryptobot -d cryptobot -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/07_demo_dataset.sql
.\scripts\stop-native-backend.ps1 -Services research
.\scripts\start-native-backend.ps1 -EnvFile .runtime\smoke\local-stack.env -Services research,worker -SkipMigrations -SkipBuild
```

## Deliverable cần bàn giao

1. Code + docs khớp PDF/blueprint/note, không có claim quá thực tế.
2. Bảng traceability cập nhật trạng thái `Done / Partial / P2` và evidence command.
3. Bộ slide có thể trả lời 10 câu hỏi cuối `note-duc.txt`: drivers, C4, boundaries, extensibility, provider replacement, scale, failure isolation, retry/event order, provenance.
4. Một commit nhỏ, reviewable, không chứa secrets; push/PR chỉ khi chủ repo yêu cầu.

---

Hãy bắt đầu bằng: đọc file handoff này, chạy `git status --short`, xem diff hiện có, xác minh các scripts mới tồn tại, rồi hoàn tất mục “Công việc đang dở” trước khi mở rộng scope.
