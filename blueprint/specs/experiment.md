# Đặc tả: Experiment Snapshot và vòng đời Backtest Job/Run

## Mô tả

`ExperimentSnapshot` là đơn vị bất biến trung tâm của hệ thống. Nó ghi lại **mọi thứ** cần để chạy lại một backtest và nhận đúng con số cũ: strategy nào ở version nào, tham số con và policy kết hợp nào, tập nến nào với `content_hash` nào, giả định thực thi nào (fee, slippage, fill policy, position policy, xử lý vị thế còn mở khi hết dataset), và evaluator version nào. Đây là hiện thực của yêu cầu Reproducibility (đề bài §36) và là gốc của toàn bộ chuỗi provenance mà `specs/leaderboard.md` khai thác. Nếu một field ảnh hưởng tới kết quả mà không nằm trong snapshot, thì kết quả đó không tái lập được — và đó là tiêu chí duy nhất để quyết định field nào phải có trong bảng này.

Module sở hữu ba bảng với ba vòng đời khác nhau: `experiments` là **snapshot ghi một lần, không bao giờ UPDATE**; `backtest_jobs` là **queue có trạng thái thay đổi liên tục**; `backtest_runs` là **vết của một lần thực thi**. Việc tách ba bảng không phải là chuẩn hoá cho đẹp: snapshot phải bất biến để provenance đáng tin, queue phải mutable để lease/retry hoạt động, và run phải riêng để ghi được `worker_id`, `duration_ms`, `error_code` — những thứ thuộc về *lần chạy* chứ không thuộc về *định nghĩa thí nghiệm*. Trách nhiệm code: `ExperimentService` (Python, `ai/`) tạo snapshot và enqueue; `worker` (cùng image Python, entrypoint `python -m app.worker`) claim job và gọi `BacktestEngine.run()` (chi tiết ở `specs/backtest.md`); Go API chỉ là public boundary — auth, RBAC, ownership, quota, validate (`specs/auth.md`).

Toàn bộ vòng đời là **bất đồng bộ, không có ngoại lệ** (ADR-006): `POST /api/v1/experiments` luôn ghi job và trả `202 { run_id }`, kể cả khi dataset chỉ có 200 nến và backtest mất 300 ms. Lý do không có fast path inline: hai code path nghĩa là hai chỗ có thể lệch nhau về xử lý lỗi, về việc ghi `backtest_runs`, về việc publish event — và bug ở path ít dùng sẽ không được phát hiện vì không ai chạy nó. Một path duy nhất đắt hơn khoảng **500 ms** cho backtest nhỏ nhưng đúng ở mọi trường hợp. Hệ quả tích cực: chuyển sang multi-worker không cần đổi API, vì API đã async từ đầu; nếu MVP làm inline rồi Phase 6 mới đổi async thì đó là **breaking change ở public contract**. Đánh đổi phải trả: UI buộc phải xử lý trạng thái pending (polling hoặc WebSocket) ngay từ MVP, không được hiển thị kết quả ngay sau khi bấm nút.

Queue là một **bảng PostgreSQL**, không phải broker (ADR-005). Điểm quyết định không phải là "đỡ một service" mà là: job và kết quả nằm cùng database nên `INSERT experiments` + `INSERT backtest_jobs` là **một transaction**. Với broker riêng, đó là dual-write giữa DB và broker, và phải thêm Outbox pattern để không mất job. `JobDispatcher` vẫn là port (`design.md` §5.1) để lúc đổi sang broker là đổi một adapter.

Đặc biệt phải đảm bảo:

- Một experiment được thực thi **đúng một lần** — kể cả khi queue giao trùng job cho hai worker.
- **Không có job nào treo mãi** ở `leased`: worker chết → lease hết hạn ≤ 120 s → job về `queued`.
- `experiments` row **không bao giờ bị UPDATE** sau khi tạo. Muốn đổi tham số là tạo experiment mới.
- Không có `backtest_jobs` row trỏ tới experiment không tồn tại, và không có experiment mồ côi không bao giờ được chạy.
- Mỗi `backtest_runs` kết thúc ở đúng một trong ba state terminal `completed | failed | cancelled` — không có state "đang chạy mãi".
- Không request nào tạo được work vượt `max_candles_per_experiment` (default **20.000** nến).

## Contract

`ExperimentSnapshot` — dạng đầy đủ, là thứ `BacktestEngine.run()` nhận vào và là thứ provenance API đọc ra:

```json
{
  "experiment_id": "8f14e45f-ea1e-4f3c-9c2b-7d1a2b3c4d5e",
  "strategy": { "strategy_id": "composite", "version": "1.0.0" },
  "candidate_definition": "<composite snapshot bất biến: children + policy + weights>",
  "candidate_hash": "sha256:9f2a7c31be4708d5c6a1e3f0b2d8419c7e5a6b3d1f0c8e2a4b6d8f0a2c4e6b81",
  "market": {
    "dataset_version": "binance-btcusdt-5m-20260101-20260301",
    "provider": "binance",
    "symbol": "BTCUSDT",
    "timeframe": "5m",
    "range_from": "2026-01-01T00:00:00Z",
    "range_to": "2026-03-01T00:00:00Z",
    "candle_count": 17280,
    "content_hash": "sha256:7a1e3c9d5b2f8046a1c3e5b7d9f1a3c5e7b9d1f3a5c7e9b1d3f5a7c9e1b3d5f7"
  },
  "execution": {
    "initial_capital": "10000.00",
    "fee_bps": 10,
    "slippage_bps": 5,
    "fill_policy": "next_candle_open",
    "position_policy": "long_only",
    "open_position_at_end": "close_at_last_candle"
  },
  "evaluator_version": "1.0.0",
  "created_at": "2026-08-11T09:14:22Z"
}
```

> **`candidate_definition` là snapshot, không phải tham chiếu.** Nó nhúng cả `children` (mỗi child có `strategy_id` + `version` + `parameters` + `weight`) và `combination.policy` + `threshold` + `encoding`. Nếu chỉ lưu một id trỏ tới "cấu hình composite hiện tại", thì sửa cấu hình đó ba tháng sau sẽ làm sai nghĩa mọi experiment cũ. Cấu trúc chi tiết ở `specs/composite-strategy.md`, cơ sở lý luận ở `design.md` §5.4 và ADR-003.

> **`content_hash` của dataset nằm trong snapshot, không chỉ `dataset_version`.** Binance đôi khi revise nến. Cùng một `(symbol, timeframe, from, to)` ở hai thời điểm có thể cho hai tập nến khác nhau. Có hash thì phát hiện được; không có thì hai experiment "cùng dataset" thực ra chạy trên dữ liệu khác nhau mà không ai biết (`specs/market-data.md` luồng E).

Schema — tên cột dùng đúng như `design.md` §4.2:

```sql
experiments(id UUID PK, owner_id FK users, strategy_version_id UUID NOT NULL FK strategy_versions(id),
            candidate_definition JSONB NOT NULL, candidate_hash CHAR(64) NOT NULL,
            market_dataset_id UUID NOT NULL FK market_datasets(id),
            initial_capital NUMERIC(20,8) DEFAULT 10000, fee_bps SMALLINT DEFAULT 10,
            slippage_bps SMALLINT DEFAULT 5,
            fill_policy fill_policy_enum DEFAULT 'next_candle_open',   -- next_candle_open|same_candle_close
            position_policy position_policy_enum DEFAULT 'long_only',  -- long_only|long_short
            open_position_at_end VARCHAR(24) DEFAULT 'close_at_last_candle',
            evaluator_version VARCHAR(24) NOT NULL,
            search_candidate_id UUID FK search_candidates(id),         -- NULL nếu tạo tay
            created_at,
            CHECK (fee_bps >= 0 AND slippage_bps >= 0), CHECK (initial_capital > 0));
CREATE INDEX idx_experiments_owner ON experiments(owner_id, created_at DESC);
CREATE INDEX idx_experiments_hash  ON experiments(candidate_hash, market_dataset_id);
```

```sql
backtest_jobs(id UUID PK,
              experiment_id UUID UNIQUE NOT NULL FK experiments(id) ON DELETE CASCADE,
              status job_status DEFAULT 'queued',   -- queued|leased|completed|failed
              priority SMALLINT DEFAULT 100,        -- tạo tay 100 < search candidate 200
              attempt SMALLINT DEFAULT 0, max_attempts SMALLINT DEFAULT 3,
              leased_by VARCHAR(64), lease_expires_at TIMESTAMPTZ, last_error TEXT,
              enqueued_at, completed_at);
CREATE INDEX idx_jobs_claimable ON backtest_jobs(priority, enqueued_at) WHERE status = 'queued';
CREATE INDEX idx_jobs_expired_lease ON backtest_jobs(lease_expires_at) WHERE status = 'leased';

backtest_runs(id UUID PK,
              experiment_id UUID UNIQUE NOT NULL FK experiments(id) ON DELETE CASCADE,
              status run_status DEFAULT 'queued',   -- queued|running|completed|failed|cancelled
              worker_id VARCHAR(64), candles_read INT, signals_count INT, duration_ms INT,
              error_code VARCHAR(48), error_detail TEXT, started_at, finished_at, created_at);
```

> **`experiment_id` UNIQUE trên cả hai bảng là cơ chế chặn double-execution.** Queue có semantics at-least-once: khi lease hết hạn đúng lúc worker 1 vẫn còn sống (GC pause dài, network partition ngắn), worker 2 có thể nhận cùng job. Nhưng chỉ **một** trong hai `INSERT backtest_runs` thành công; worker thua nhận UNIQUE violation, đọc lại row đã có và bỏ qua job. Đây là điểm quan trọng: bảo đảm exactly-once **không** đến từ việc lease "chính xác" — lease là heuristic và sẽ sai — mà đến từ một constraint ở tầng DB. Nếu chỉ dựa vào lease thì bug này chỉ xuất hiện dưới tải và không reproduce được.

Hai index partial giải quyết hai câu truy vấn khác nhau và không thay thế nhau được: `idx_jobs_claimable` làm "lấy job tiếp theo" không full-scan khi bảng có 100K row (`WHERE status='queued'` lọc trước, `ORDER BY priority, enqueued_at` khớp thứ tự index); `idx_jobs_expired_lease` cho sweeper tìm lease hết hạn mà không quét toàn bộ job đã hoàn thành.

Priority: experiment tạo tay `priority=100`, search candidate `priority=200`, **số nhỏ = ưu tiên cao**. Lý do: một user đang ngồi chờ kết quả của một backtest cụ thể không nên bị xếp sau 500 candidate của search run chạy nền. Không có priority thì trải nghiệm "bấm Run rồi chờ 40 phút" là hành vi mặc định ngay khi có một search run hoạt động.

## Luồng chính

### A. Tạo experiment — `POST /api/v1/experiments` trả `202`

```mermaid
sequenceDiagram
    autonumber
    actor U as Researcher
    participant GO as Go API
    participant EXS as ExperimentService
    participant MS as MarketService
    participant DB as PostgreSQL
    participant HUB as WS Hub

    U->>GO: POST /api/v1/experiments
    GO->>GO: L1-L4 auth, RBAC, rate limit, validate schema
    GO->>EXS: create_experiment payload kèm X-Correlation-ID
    EXS->>EXS: validate LẠI, không tin caller nội bộ
    EXS->>DB: resolve strategy_version_id từ strategy_id và version
    Note over EXS,DB: Không tìm thấy → 422 unknown_strategy_version.<br/>FK bảo đảm snapshot không trỏ tới version không tồn tại.
    EXS->>MS: ensure_dataset symbol, timeframe, from, to
    MS->>MS: ước lượng số nến, so với max_candles_per_experiment
    Note over MS: Vượt 20.000 → 422 dataset_too_large,<br/>KHÔNG nạp nến rồi mới báo lỗi
    MS-->>EXS: market_dataset_id, candle_count, content_hash
    EXS->>EXS: candidate_hash = sha256 canonical_json của definition
    EXS->>DB: tìm experiment đã completed cùng hash, dataset, execution, evaluator
    alt trùng và force = false
        DB-->>EXS: experiment cũ đã completed
        EXS-->>GO: 200 run_id cũ kèm reused = true
    else mới hoặc force = true
        EXS->>DB: BEGIN
        EXS->>DB: INSERT experiments snapshot bất biến
        EXS->>DB: INSERT backtest_jobs status queued, priority 100
        EXS->>DB: COMMIT
        EXS->>HUB: BacktestQueued experiment_id, job_id, priority
        EXS-->>GO: 202 run_id, status queued
    end
    GO-->>U: 202 run_id
```

`INSERT experiments` và `INSERT backtest_jobs` nằm trong **cùng một transaction**. Hai điều xấu bị chặn: một job trỏ tới experiment không tồn tại (nếu job commit trước), và một experiment mồ côi không bao giờ được chạy (nếu experiment commit rồi process chết trước khi enqueue). Đây là lợi ích cụ thể, đo được của việc dùng bảng PostgreSQL làm queue — với broker riêng đây là dual-write và cần Outbox pattern để đạt cùng bảo đảm.

### B. Dedup thông minh và cờ `force`

1. Tính `candidate_hash = sha256(canonical_json(candidate_definition))`. Canonical hoá: sort key, chuẩn hoá số, UTF-8 NFC — nếu không thì `{"a":1,"b":2}` và `{"b":2,"a":1}` cho hai hash khác nhau và dedup vô hiệu một cách âm thầm.
2. Tra `idx_experiments_hash` theo `(candidate_hash, market_dataset_id)`.
3. Lọc tiếp trên **toàn bộ** execution config (`initial_capital`, `fee_bps`, `slippage_bps`, `fill_policy`, `position_policy`, `open_position_at_end`) và `evaluator_version`. Khác một field nào trong nhóm này là một thí nghiệm khác — `fee_bps=10` và `fee_bps=30` cho hai Total Return khác nhau, nên không được coi là trùng.
4. Nếu tìm thấy và `backtest_runs.status = 'completed'` → trả `200` với `run_id` cũ, không tạo job. Endpoint trở thành idempotent theo nội dung và tiết kiệm CPU worker.
5. Nếu tìm thấy nhưng run đang `queued`/`running` → trả `202` với `run_id` đang chạy, cũng không tạo job thứ hai.
6. Nếu run cũ `failed` → **tạo mới**. Một lần chạy lỗi không phải là kết quả, và người dùng có quyền thử lại.

> **Đánh đổi phải nêu:** dedup theo nội dung mâu thuẫn với một nhu cầu hợp lệ — chạy lại chính xác cùng một cấu hình để **kiểm chứng determinism** (demo S5: chạy hai lần phải ra cùng con số). Vì vậy có `force=true`: bỏ qua bước 3–5, luôn tạo experiment mới. Không có cờ này thì bài kiểm chứng quan trọng nhất của Reproducibility lại là bài duy nhất hệ thống không cho làm. Cờ này không mở lỗ hổng vì nó vẫn đi qua quota và rate limit.

### C. Worker claim job — `FOR UPDATE SKIP LOCKED`

```sql
WITH claimed AS (
    SELECT id FROM backtest_jobs
    WHERE status = 'queued'
       OR (status = 'leased' AND lease_expires_at < now())   -- thu hồi lease của worker đã chết
    ORDER BY priority ASC, enqueued_at ASC
    FOR UPDATE SKIP LOCKED LIMIT 1
)
UPDATE backtest_jobs j
SET status = 'leased', leased_by = $1,
    lease_expires_at = now() + interval '120 seconds',
    attempt = j.attempt + 1
FROM claimed c WHERE j.id = c.id
RETURNING j.id, j.experiment_id, j.attempt, j.max_attempts;
```

| Cách                              | Vấn đề                                                                                     |
| --------------------------------- | ------------------------------------------------------------------------------------------ |
| `SELECT ... FOR UPDATE` thường    | Worker 2 **chờ** worker 1 nhả lock → serialize hoàn toàn, mất hết lợi ích của multi-worker  |
| `UPDATE ... RETURNING` không lock | Race: hai worker cùng đọc `status='queued'` rồi cùng UPDATE → **một job chạy hai lần**      |
| Advisory lock                     | Được, nhưng phải tự quản lý key space và tự viết cơ chế phát hiện worker chết               |
| **`FOR UPDATE SKIP LOCKED`** ✅    | Worker 2 **bỏ qua** row đang bị lock và nhận row tiếp theo ngay — đúng semantics competing consumer |

Worker rỗi polling mỗi **500 ms** với backoff tới 2 s khi queue trống liên tục. Broker cho push và không có latency này; với backtest kéo dài 2–40 s thì 500 ms là dưới 2% và không đáng thêm một service (ADR-005).

### D. Thực thi, heartbeat và ranh giới ghi kết quả

```mermaid
sequenceDiagram
    autonumber
    participant W as Worker
    participant DB as PostgreSQL
    participant ENG as BacktestEngine
    participant EVA as Evaluator

    W->>DB: claim job, SKIP LOCKED
    DB-->>W: job_id, experiment_id, attempt 1 of 3
    W->>DB: INSERT backtest_runs status running, worker_id, started_at
    Note over W,DB: UNIQUE experiment_id vi phạm → worker khác đã chạy.<br/>Worker này bỏ job, KHÔNG chạy lại engine.
    W->>DB: SELECT snapshot và nến của market_dataset_id
    W->>DB: BacktestStarted qua domain_events
    par Vòng lặp backtest
        W->>ENG: run snapshot, candles
        ENG-->>W: trades, signals, equity points
    and Heartbeat mỗi 30 giây
        W->>DB: UPDATE lease_expires_at = now + 120s WHERE leased_by = self
    end
    W->>DB: BEGIN
    W->>DB: INSERT trades, run_signals, equity_points theo batch
    W->>DB: UPDATE backtest_runs status completed, duration_ms, candles_read, signals_count
    W->>DB: UPDATE backtest_jobs status completed, completed_at
    W->>DB: COMMIT
    W->>EVA: BacktestCompleted backtest_run_id, trade_count, duration_ms
    Note over W,EVA: Worker KHÔNG tính metric.<br/>Evaluator là consumer riêng, xem specs/evaluation.md
```

Heartbeat gia hạn `lease_expires_at` mỗi **30 s** trong lúc chạy job dài, với lease dài **120 s**. Tỉ lệ 4:1 cho phép mất ba nhịp heartbeat liên tiếp (GC pause, DB chậm tức thời) mà job vẫn không bị thu hồi oan. `UPDATE ... WHERE leased_by = self` là điều kiện bắt buộc: nếu job đã bị worker khác claim thì heartbeat này phải **thất bại**, để worker cũ biết mình đã mất job và dừng lại thay vì tiếp tục tính rồi ghi kết quả trùng.

Kết quả và trạng thái được ghi trong **một** transaction. Nếu tách, sẽ có cửa sổ mà `backtest_runs.status='completed'` nhưng `trades` chưa có row — và API `GET /experiments/{id}/trades` trả mảng rỗng cho một run đã xong.

### E. Worker chết, lease hết hạn, cạn `max_attempts`

```mermaid
sequenceDiagram
    autonumber
    participant W1 as Worker 1
    participant DB as PostgreSQL
    participant W2 as Worker 2
    participant SRS as SearchRunService

    W1->>DB: claim job J, attempt 1, lease tới T+120s
    W1->>DB: heartbeat tại T+30s và T+60s
    Note over W1: ✕ container bị OOM-kill tại T+75s
    Note over DB: heartbeat dừng, lease vẫn tới T+180s
    W2->>DB: claim, điều kiện leased AND lease_expires_at nhỏ hơn now
    Note over W2,DB: Trước T+180s: KHÔNG nhận được J.<br/>Đây là cái giá của lease: trễ tối đa 120 s.
    W2->>DB: tại T+185s claim J thành công, attempt 2
    W2->>DB: INSERT backtest_runs
    Note over W2,DB: Row đã tồn tại từ W1 với status running →<br/>UPDATE về running, worker_id = w2, KHÔNG tạo row thứ hai
    W2->>W2: chạy lại từ đầu, backtest là hàm thuần nên an toàn
    W2->>DB: UPDATE status completed
```

Sau `max_attempts = 3`, job chuyển `status='failed'` với `last_error` ghi rõ, `backtest_runs.status='failed'` với `error_code`, và **candidate tương ứng được đánh `failed`** thay vì treo `queued` mãi — nếu bỏ bước cuối, `SearchRunService` sẽ đếm mãi không đủ `candidates_tested` và search run không bao giờ đạt stop condition (`specs/search-loop.md`).

> **Chi tiết dễ bỏ sót: retry chỉ an toàn vì backtest là hàm thuần.** `BacktestEngine.run(snapshot, candles)` không có side effect ngoài giá trị trả về; snapshot bất biến, nến bất biến. Chạy lại lần thứ hai cho đúng kết quả lần thứ nhất. Nếu engine có state ngoài (ghi file tạm, cập nhật counter global) thì retry sẽ cho kết quả khác nhau tuỳ số lần retry, và đó là loại lỗi không tái hiện được.

### F. State machine của `backtest_runs.status`

```mermaid
stateDiagram-v2
    [*] --> queued : INSERT cùng transaction với job
    queued --> running : worker claim và ghi started_at
    running --> completed : trades và equity đã COMMIT
    running --> failed : lỗi engine hoặc cạn max_attempts
    queued --> cancelled : search run bị cancel trước khi chạy
    running --> cancelled : OPERATOR hoặc owner cancel search run
    completed --> [*]
    failed --> [*]
    cancelled --> [*]

    note right of completed
        3 state terminal.
        Không có đường quay lại queued
        từ bất kỳ state terminal nào.
        Mọi lệnh tới đây bị reject 409.
    end note
```

Không có cạnh `failed → queued`: retry là việc của **job** (`attempt += 1`), không phải của run. Run giữ đúng nghĩa "một lần thực thi có kết cục", còn job giữ nghĩa "công việc cần hoàn thành". Trộn hai khái niệm này lại là lý do rất nhiều hệ thống queue có state machine mà không ai đọc nổi.

### G. Đọc kết quả

| Method | Route | Auth | Ghi chú |
| --- | --- | --- | --- |
| POST | `/api/v1/experiments` | Auth | → `202 {run_id}`; validate + quota; `200` nếu dedup hit |
| GET | `/api/v1/experiments/{id}` | **Owner** | status + result summary + provenance |
| GET | `/api/v1/experiments/{id}/trades` | Owner | phân trang, max **200**/page |
| GET | `/api/v1/experiments/{id}/equity` | Owner | decimate xuống ≤ **2000** điểm |
| GET | `/api/v1/experiments/{id}/overlays` | Owner | signal + entry/exit/SL/TP marker, tính ở backend |

`Owner` nghĩa là `experiments.owner_id = principal.id` **hoặc** role ∈ `(OPERATOR, ADMIN)`. Không khớp → `404`, không `403`: `403` xác nhận resource tồn tại và biến endpoint thành oracle dò UUID (`specs/auth.md`).

Decimate equity xuống 2000 điểm không phải để "nhẹ mạng" mà vì một run 20.000 nến có 20.000 điểm equity, trong khi chart rộng nhất chỉ có khoảng 2000 pixel ngang — phần còn lại là byte không ai thấy được. Downsample giữ điểm min/max trong mỗi bucket để **không làm mất hình dạng drawdown**; lấy mẫu đều đơn giản có thể bỏ đúng điểm đáy và làm biểu đồ đẹp hơn thực tế.

Event của module: `BacktestQueued` (publisher `ExperimentService`), `BacktestStarted` / `BacktestCompleted` / `BacktestFailed` (publisher Worker). Consumer chi tiết ở `design.md` §5.6. Worker **không** gọi `Evaluator.evaluate()` trực tiếp — nó publish `BacktestCompleted` (đề bài §34).

## Kịch bản lỗi

| Tình huống | Phản ứng |
|---|---|
| `strategy_id@version` không có trong registry | `422 unknown_strategy_version` trước khi mở transaction. FK `strategy_version_id` là lớp phòng thủ thứ hai |
| `code_fingerprint` của strategy lệch với DB | Worker và API **fail fast lúc startup**, không chạy job nào với provenance sai (ADR-009) |
| Số nến yêu cầu > `max_candles_per_experiment` | `422 dataset_too_large` kèm `max_candles` và `suggested_ranges`. Kiểm tra trên **ước lượng** từ `(to-from)/interval`, không nạp nến rồi mới báo |
| `from=2017-01-01`, `timeframe=1m` | Chính là ca trên: 4,7 triệu nến, đủ OOM Python process. Chặn ở Go **và** ở Python (ADR-014) |
| Process chết sau `INSERT experiments`, trước `INSERT backtest_jobs` | Không xảy ra: cùng transaction, chưa COMMIT thì cả hai bị rollback |
| Hai request `POST /experiments` giống nhau đồng thời | Cả hai qua dedup check (chưa có row `completed`) → hai experiment. Chấp nhận: dedup là tối ưu CPU, không phải khoá tính đúng đắn. Muốn chặt hơn thì client gửi `force=false` và retry sau khi run đầu xong |
| Lease hết hạn khi worker 1 vẫn sống | Worker 2 claim, `INSERT backtest_runs` gặp `UNIQUE experiment_id` → nhận biết và bỏ job. Heartbeat của worker 1 thất bại vì `leased_by` đã đổi → worker 1 dừng, không ghi kết quả |
| Worker bị OOM-kill giữa job | Heartbeat dừng → lease hết hạn sau ≤ 120 s → job về `queued`, `attempt += 1`. Trễ tối đa 120 s là cái giá đã biết của lease-based recovery |
| Job fail 3 lần liên tiếp | `backtest_jobs.status='failed'` + `last_error`; `backtest_runs.status='failed'` + `error_code`; candidate đánh `failed`; `SearchRunService` tăng `candidates_failed` và có thể chạm `max_failure_rate` |
| Strategy plugin có vòng lặp vô hạn | Deadline trên `analyze()` → `error_code='strategy_timeout'`, job **không** retry (không retryable), search run tiếp tục. Một plugin xấu không được phép giết cả run |
| Plugin ném `ZeroDivisionError` / `IndexError` | Catch ở biên gọi, log kèm `strategy_id@version`, `error_code='strategy_error'`, worker **không** crash |
| Duplicate `BacktestCompleted` tới Evaluator | `event_consumptions(event_id, consumer)` chặn lớp một; `UNIQUE (backtest_run_id, evaluator_version)` chặn lớp hai. Không tạo hai evaluation (R12) |
| PostgreSQL down khi worker đang chạy | Worker retry ghi với backoff 1s→2s→4s, tối đa 30 s; thất bại → thoát để lease hết hạn tự nhiên. **Không** ghi kết quả một nửa |
| Dataset bị xoá trong lúc job còn `queued` | `ON DELETE` bị FK chặn — `market_datasets` không cho xoá khi còn experiment tham chiếu. Retention chỉ xoá dataset không còn ai trỏ tới (`design.md` §4.4) |
| Cancel search run khi 3 job đang `leased` | Job đang chạy hoàn thành bình thường (không kill giữa dòng); job còn `queued` chuyển `cancelled`. Trạng thái quan sát được, không có job zombie |
| `GET /experiments/{id}` khi run còn `queued` | `200` với `status: "queued"`, `result: null`, `queue_position`. **Không** `404`, và không chờ cho tới khi xong |
| `RESEARCHER` đọc experiment của người khác | `404 not_found`, response không chứa field nào của experiment. Log `reason=ownership_denied` |
| Clock skew giữa worker và DB | Mọi so sánh lease dùng `now()` **của DB**, không của process. Hai worker lệch clock 5 s không tạo hành vi khác nhau |

## Ràng buộc

**Tính đúng đắn**

- `experiments` là append-only. Không có endpoint nào UPDATE row của bảng này; kiểm chứng bằng test static `grep -rn "UPDATE experiments" ai/app/` → **0** khớp.
- `INSERT experiments` + `INSERT backtest_jobs` trong **một** transaction, không có ngoại lệ.
- `experiment_id` UNIQUE trên `backtest_jobs` và `backtest_runs` — exactly-once đến từ constraint DB, không từ độ chính xác của lease.
- Mọi giá trị tiền dùng `NUMERIC`, không `float`. Sai số float64 tích luỹ qua hàng nghìn trade đủ để lật dấu Total Return.
- `CHECK (fee_bps >= 0 AND slippage_bps >= 0)` và `CHECK (initial_capital > 0)` là lớp phòng thủ cuối nếu validation có bug.
- Mọi timestamp là `TIMESTAMPTZ` UTC; so sánh lease bằng `now()` của DB.

**Hiệu năng**

- `POST /api/v1/experiments` (đường tạo mới): p95 **< 250 ms**, gồm resolve version + ensure dataset khi nến đã có sẵn trong DB.
- Dedup hit: p95 **< 80 ms** — một index lookup trên `idx_experiments_hash`.
- Claim job: p95 **< 20 ms** với 100.000 row trong `backtest_jobs`, nhờ `idx_jobs_claimable` partial.
- Ghi kết quả một run 20.000 nến (khoảng 80 trade, 20.000 equity point): **< 2 s** bằng batch insert kiểu `execute_values`, không loop từng row.
- Polling khi rỗi: 500 ms, backoff tới 2 s. Overhead của polling < **1%** một core khi queue trống.
- `GET /experiments/{id}/equity`: p95 **< 300 ms** cho 2000 điểm sau decimate.

**Bảo mật**

- Ownership check trên **mọi** route `GET /experiments/*`; sai chủ → `404`, không `403`.
- Quota kiểm tra **trong cùng transaction** với `INSERT`. Check ngoài transaction là TOCTOU: hai request đồng thời đều thấy còn slot rồi đều insert.
- `error_detail` của run không bao giờ đi ra client nguyên văn — API chỉ trả `error_code` domain-level và `request_id`. Stack trace, tên bảng, SQL message chỉ nằm trong log server.
- Snapshot chỉ nhận `symbol` thuộc `market_pairs` active và `timeframe` thuộc enum; không có đường nào để một chuỗi tự do từ client đi vào truy vấn nến.
- Worker không mở cổng nào, không nhận HTTP request. Nó chỉ đọc queue — bề mặt tấn công của nó là **rỗng** về phía network.

**Khả năng mở rộng**

- 1 worker → N worker: `docker compose up --scale worker=N`, **0 dòng code đổi**. `SKIP LOCKED` đã là competing consumer từ ngày đầu.
- Đổi sang broker (Redis Stream / RabbitMQ) = thay `PostgresJobDispatcher` bằng `BrokerJobDispatcher`. `ExperimentSnapshot`, event payload, public API, `BacktestEngine.run()`: không đổi.
- Thêm field vào `execution` (ví dụ `funding_rate_bps`) = thêm 1 cột + 1 key trong snapshot. Không đổi queue, không đổi worker loop.
- Ngưỡng chuyển sang broker phải **đo** rồi mới đổi: `job_queue_wait_seconds` cao do contention, hoặc số worker > ~20 khiến polling tạo tải đáng kể.

**Quan sát được**

- `jobs_queued` gauge, `jobs_leased` gauge — hai số trả lời "queue có đang tắc không".
- `jobs_completed_total`, `jobs_failed_total{error_code}` counter — `error_code` là label nên đếm được theo loại lỗi mà không parse log.
- `job_queue_wait_seconds` histogram (từ `enqueued_at` tới lúc claim) — chính là tín hiệu quyết định có cần thêm worker.
- `backtest_duration_seconds` histogram với label `strategy_family` và `candle_count_bucket`.
- Log JSON structured kèm `correlation_id` xuyên Go → Python → worker; một `request_id` trên UI grep ra được toàn bộ chuỗi (`design.md` §8.4).
- **Không** dùng `experiment_id` hay `user_id` làm label metric: cardinality explosion và PII.

## Tiêu chí chấp nhận

- [ ] AC-01: `POST /api/v1/experiments` với dataset 200 nến → phản hồi là `202` kèm `run_id` trong **< 250 ms**, và `backtest_runs.status` lúc đó là `queued` — chứng minh không có đường inline nào.
- [ ] AC-02: Test static `grep -rn "UPDATE experiments" ai/app/` → **0** khớp; `grep -rn "run_backtest" server/` → 0 khớp (Go không chạy domain).
- [ ] AC-03: Kill process Python giữa lúc `INSERT experiments` và `INSERT backtest_jobs` (inject exception) → `SELECT count(*) FROM experiments` không tăng, `backtest_jobs` không tăng.
- [ ] AC-04: Chạy 4 worker, enqueue 40 job → `SELECT experiment_id, count(*) FROM backtest_runs GROUP BY 1 HAVING count(*) > 1` trả **0 row**; tổng `trades` bằng đúng tổng của 40 run chạy tuần tự.
- [ ] AC-05: `SIGKILL` một worker giữa job → trong **≤ 120 s** job đó có `status='queued'`, `attempt=2`; sau đó hoàn thành với `worker_id` khác. Không job nào còn `leased` sau khi queue rỗng.
- [ ] AC-06: Inject lỗi khiến một job fail 3 lần → `backtest_jobs.status='failed'`, `last_error` khác NULL, `search_candidates.status='failed'`, và search run vẫn đạt được stop condition.
- [ ] AC-07: Enqueue 10 job `priority=200` rồi 1 job `priority=100` → job `priority=100` được claim **trước** cả 10 job kia.
- [ ] AC-08: `POST /experiments` hai lần với payload giống hệt, chờ lần đầu `completed` → lần hai trả `200` với **cùng** `run_id` và `reused: true`; `count(*) FROM experiments` chỉ tăng 1.
- [ ] AC-09: Cùng payload với `force=true` → tạo experiment **mới**, và hai run cho `total_return_pct` **giống nhau đến từng chữ số** (kiểm chứng determinism).
- [ ] AC-10: `POST /experiments` với `from=2017-01-01&to=2026-01-01&timeframe=1m` → `422 dataset_too_large`; RSS của process Python không tăng quá **50 MiB** trong lúc xử lý request đó.
- [ ] AC-11: User A tạo experiment, user B (`RESEARCHER`) gọi cả 4 route `GET /experiments/{id}*` → cả 4 trả `404` và response không chứa `candidate_hash`, `owner_id`, hay bất kỳ metric nào.
- [ ] AC-12: `GET /experiments/{id}` ngay sau khi tạo → `200` với `status="queued"`, `result=null`; sau khi worker xong → `200` với `status="completed"` và đầy đủ provenance (strategy version, dataset `content_hash`, `fee_bps`, `fill_policy`, `evaluator_version`).
- [ ] AC-13: `GET /experiments/{id}/equity` của run 20.000 nến → **≤ 2000** điểm, và giá trị `max_drawdown` tính từ chuỗi đã decimate lệch **< 0,1** điểm phần trăm so với chuỗi gốc.
- [ ] AC-14: Publish `BacktestCompleted` hai lần cho cùng run → `count(*) FROM evaluations WHERE backtest_run_id=$1` bằng **1**; `leaderboard_entries` không có row trùng.
- [ ] AC-15: Chạy search run 40 candidate với 1 worker rồi với 4 worker trên cùng dataset → thời gian giảm **≥ 3×**, `git diff` giữa hai lần chạy **rỗng**.
