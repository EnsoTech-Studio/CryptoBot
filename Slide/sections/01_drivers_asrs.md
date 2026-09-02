<!-- _class: lead -->
# CRYPTO STRATEGY LAB (CryptoBot)
## Báo Cáo Thiết Kế Kiến Trúc Phần Mềm (Software Architecture)
**Đề tài:** Nền tảng Nghiên cứu, Khám phá & Đánh giá Chiến lược Giao dịch Tiền mã hóa Tự động

---

## 1. Bối cảnh & 4 Nhóm Architectural Drivers

<div class="columns">
<div>

### Động lực Nghiệp vụ (ASRs Drivers)
* **Realtime Market Ingestion:** Dữ liệu biến động mili-giây, stream liên tục và tự bù khoảng trống nến (gap backfill).
* **High Modifiability:** Thêm/bớt chiến lược đơn và composite (Handcraft/LLM Agent) không sửa Core.
* **Massive Search Scalability:** Khám phá hàng ngàn tham số (Loop Discovery) không nghẽn UI.
* **Unstructured News Intelligence:** Crawl tin đa nguồn, tự phục hồi khi đổi DOM và định lượng sentiment.

</div>
<div>

### Quyết định Kiến trúc Tương ứng
* **Driver 1 → Streaming & Kappa Architecture:** Tách biệt luồng WSS trực tiếp và Historical Backfill.
* **Driver 2 → Plugin Architecture & AST Sandbox:** Chuẩn hóa IStrategy contract, nạp plugin động.
* **Driver 3 → Event-Driven Job Queue & Worker:** Phân tán tải Backtest qua PostgreSQL Outbox & Worker pool.
* **Driver 4 → Multi-Agent & LLM Fallback:** Tự phát hiện cấu trúc HTML và chấm điểm sentiment.

</div>
</div>

---

## 2. Hệ Thống Quality Attributes (ASRs Taxonomy)

| Thuộc tính (QA) | Trọng tâm Thiết kế | Tactic / Kỹ thuật Kiến trúc Áp dụng |
| :--- | :--- | :--- |
| **Modifiability** | Thêm mới Strategy, Search, Data Provider không sửa Core | Plugin Architecture, Open-Closed Principle, Dynamic Registry |
| **Scalability** | Xử lý tải >100,000 backtests và stream nến realtime | Scale-out Python Worker pool, Job Queue, Redis Caching |
| **Realtime / Perf** | Độ trễ cập nhật nến < 200ms, thông lượng Backtest cao | Go Edge Gateway, WebSocket Streaming, Vectorized Engine |
| **Reliability** | Lỗi crawl/search không sập API; tự reconnect sàn | Failure Isolation, Transactional Outbox, Lease Takeover |
| **Observability** | Theo dõi trạng thái Worker, tiến độ Search Loop | Structured Logging, State Machine tracking, Run Metrics |
| **Reproducibility** | Kết quả Backtest và Leaderboard phải có nguồn gốc bất biến | Immutable Dataset snapshots, Run Config Hash, Seed Lock |

---

## 3. Kịch Bản ASR Chi Tiết (Modifiability & Scalability)

<div class="columns">
<div>

### ASR-1: Modifiability (Thêm Strategy mới)
* **Source:** Quant Researcher / AI Agent.
* **Stimulus:** Thêm class chiến lược mới (`MACDStrategy`).
* **Artifact:** Strategy Subsystem & UI Registry.
* **Environment:** Hệ thống đang chạy (Runtime).
* **Response:** Tự phát hiện, nạp metadata lên UI không cần compile lại Go Gateway hay sửa Core.
* **Measure:** Thao tác trên 1 file Python độc lập, 0 downtime.

</div>
<div>

### ASR-2: Scalability (Tải Backtest lớn)
* **Source:** Người dùng kích hoạt Auto Search Loop.
* **Stimulus:** 10,000 công việc backtest vào hàng đợi cùng lúc.
* **Artifact:** Job Queue & Python Worker Pool.
* **Environment:** Tải hệ thống cao điểm.
* **Response:** Phân phối đều qua Lease Heartbeat, worker scale-out, không tràn RAM.
* **Measure:** Tỷ lệ hoàn thành 100%, 0 dropped job, CPU ổn định.

</div>
</div>

---

## 4. Kịch Bản ASR Chi Tiết (Realtime & Reliability)

<div class="columns">
<div>

### ASR-3: Realtime & Data Parity
* **Source:** Sàn Binance (WSS drop / network jitter).
* **Stimulus:** Mất kết nối mạng trong 30 giây.
* **Artifact:** Go Market Gateway & Postgres Candle Storage.
* **Environment:** Production Trading Hours.
* **Response:** Tự Reconnect, kích hoạt REST Backfill bù nến thiếu, deduplicate bằng Open Time.
* **Measure:** Chuỗi nến liên tục, không trùng lặp, độ trễ bắt kịp < 2s.

</div>
<div>

### ASR-4: Fault Tolerance (Worker Crash)
* **Source:** Python Worker tiến trình backtest bị kill đột ngột (OOM).
* **Stimulus:** Job đang xử lý dở dang (RUNNING).
* **Artifact:** Job Queue & Outbox Manager.
* **Environment:** Đang chạy tác vụ tính toán nặng.
* **Response:** Hết hạn Lease Heartbeat (30s), Worker khác tự động chiếm quyền (Takeover) và chạy lại.
* **Measure:** Job hoàn thành thành công, 0 stuck job.

</div>
</div>
