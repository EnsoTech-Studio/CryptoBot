<!-- _class: lead -->
# CRYPTO STRATEGY LAB (CryptoBot)
## Báo Cáo Thiết Kế Kiến Trúc Phần Mềm (Software Architecture)
**Đề tài:** Nền tảng Research, Auto-Discovery & Đánh giá Trading Strategy Tự động

---

## 1. Miền Nghiệp Vụ & Bối Cảnh (Business Domain)

<div class="columns">
<div>

### Binance USDT-M Futures & Algo-Trading
* **Perpetual Futures Market (USDT-M):**
  * Giao dịch leverage 2 chiều **Long / Short** 24/7/365.
  * Order execution theo **BBO (Best Bid / Best Offer)** realtime.
* **Đặc tính Tài chính Khắt khe:**
  * **Funding Rate:** Cân bằng giá Index & Mark Price mỗi 8h.
  * **Trading Fee & Slippage:** Phí Maker/Taker (0.02% / 0.05%), Slippage khi thị trường biến động mạnh.
  * **Rủi ro Liquidation:** Quản trị Margin, Stop-Loss & Take-Profit nghiêm ngặt.

</div>
<div>

### Đối Tượng Sử Dụng & Nhu Cầu Cốt Lõi
* **Quant Researcher / Algorithmic Trader:**
  * Cần môi trường nạp candle độ trễ thấp (<200ms) đa timeframe (1m, 5m, 1h, 1d).
  * Backtest strategy chính xác, đo lường Sharpe Ratio, Max Drawdown, Profit Factor, Win Rate.
* **Autonomous AI Agents (LLM Multi-Agent):**
  * Tự động crawl financial news, scoring sentiment.
  * Tự sinh strategy code, debug và scan hyperparameter space.

</div>
</div>

---

## 2. Bài Toán Thực Tế & Thách Thức (Problem Statement)

<div class="columns-equal">
<div>

### Thách Thức Về Market Data & Order Execution
* **Phân mảnh & Bất định Realtime Data:**
  * WebSocket bị drop/jitter làm mất candle → Sai lệch entry/exit signals.
  * *Yêu cầu:* Tự phát hiện candle gap & bù dữ liệu tự động (Gap Backfill).
* **Bẫy "Lookahead Bias" & Parity Mismatch:**
  * Backtest giả lập phi thực tế (nhìn trước tương lai, bỏ qua slippage/phí) → Khi chạy Live bị lỗ.
  * *Yêu cầu:* Deterministic Replay Engine mô phỏng sát sao slippage, BBO limit fill và trading fees.

</div>
<div>

### Thách Thức Về Scalability & Architecture
* **Bùng nổ Tổ hợp Tìm kiếm (Combinatorial Explosion):**
  * Quét hàng ngàn parameter combinations / technical indicators gây nghẽn UI nếu chạy đồng bộ.
  * *Yêu cầu:* Asynchronous Outbox Job Queue & Worker Pool.
* **Bẫy Gắn Chặt Hệ Thống (Vendor Lock-in):**
  * Source code bị trói chặt vào một sàn/thư viện duy nhất, khó thêm strategy mới.
  * *Yêu cầu:* Strategy Plugin Architecture & AST Sandbox an toàn.

</div>
</div>

---

## 3. Bối cảnh & 4 Nhóm Architectural Drivers

<div class="columns">
<div>

### Động lực Nghiệp vụ (ASRs Drivers)
* **Realtime Market Ingestion:** Dữ liệu biến động mili-giây, stream liên tục và tự bù candle gap (Gap Backfill).
* **High Modifiability:** Thêm/bớt single strategy và composite strategy (Handcraft/LLM Agent) không sửa Core.
* **Massive Search Scalability:** Auto-discovery hàng ngàn parameters (Loop Discovery) không nghẽn UI.
* **Unstructured News Intelligence:** Crawl tin đa nguồn, tự phục hồi khi đổi DOM và định lượng sentiment.

</div>
<div>

### Quyết định Kiến trúc Tương ứng
* **Driver 1 → Dual-Channel Ingestion & Gap Repair:** Tách biệt luồng WSS trực tiếp và Historical Backfill đồng nhất schema.
* **Driver 2 → Strategy Plugin Architecture & AST Sandbox:** Chuẩn hóa IStrategy contract, nạp plugin động.
* **Driver 3 → Event-Driven Job Queue & Leased Worker:** Phân tán tải Backtest qua PostgreSQL Outbox & Worker pool.
* **Driver 4 → Multi-Agent & LLM Fallback:** Tự phát hiện cấu trúc HTML và scoring sentiment.

</div>
</div>

---

## 4. Hệ Thống Quality Attributes (ASRs Taxonomy)

| Thuộc tính (QA) | Trọng tâm Thiết kế | Tactic / Kỹ thuật Kiến trúc Áp dụng |
| :--- | :--- | :--- |
| **Modifiability** | Thêm mới Strategy, Search Algorithm, Market Provider không sửa Core | Strategy Plugin Architecture, Open-Closed Principle, Dynamic Registry |
| **Scalability** | Xử lý tải >100,000 backtests và stream candle realtime | Scale-out Python Worker pool, PostgreSQL Leased Job Queue, In-memory Broadcaster |
| **Realtime / Perf** | Độ trễ cập nhật candle < 200ms, thông lượng Backtest cao | Go Edge Gateway, WebSocket Streaming, Deterministic Replay Engine |
| **Reliability** | Lỗi crawl/search không sập API; tự reconnect sàn | Failure Isolation, Transactional Outbox, Lease Takeover |
| **Observability** | Theo dõi Worker health, tiến độ Search Loop & metrics | Structured Logging, State Machine tracking, Run Metrics |
| **Reproducibility** | Kết quả Backtest và Leaderboard phải có nguồn gốc bất biến | Immutable Dataset snapshots, Run Config Hash, Seed Lock |

---

## 5. Kịch Bản ASR Chi Tiết (Modifiability & Scalability)

<div class="columns">
<div>

### ASR-1: Modifiability (Thêm Strategy mới)
* **Source:** Quant Researcher / AI Agent.
* **Stimulus:** Thêm strategy class mới (`MACDStrategy`).
* **Artifact:** Strategy Subsystem & UI Registry.
* **Environment:** Hệ thống đang chạy (Runtime).
* **Response:** Tự phát hiện, nạp metadata lên UI không cần compile lại Go Gateway hay sửa Core.
* **Measure:** Thao tác trên 1 file Python độc lập, 0 downtime.

</div>
<div>

### ASR-2: Scalability (Tải Backtest lớn)
* **Source:** Người dùng kích hoạt Auto Search Loop.
* **Stimulus:** 10,000 backtest jobs vào Job Queue cùng lúc.
* **Artifact:** Job Queue & Python Worker Pool.
* **Environment:** Tải hệ thống cao điểm.
* **Response:** Phân phối đều qua Lease Heartbeat, worker scale-out, không tràn RAM.
* **Measure:** Tỷ lệ hoàn thành 100%, 0 dropped job, CPU ổn định.

</div>
</div>

---

## 6. Kịch Bản ASR Chi Tiết (Realtime & Reliability)

<div class="columns">
<div>

### ASR-3: Realtime & Data Parity
* **Source:** Binance Exchange (WSS drop / network jitter).
* **Stimulus:** Mất kết nối mạng trong 30 giây.
* **Artifact:** Go Market Gateway & Postgres Candle Storage.
* **Environment:** Production Trading Hours.
* **Response:** Tự Reconnect, kích hoạt REST Backfill bù candle thiếu, deduplicate bằng Open Time.
* **Measure:** Chuỗi candle liên tục, không duplicate, latency bắt kịp < 2s.

</div>
<div>

### ASR-4: Fault Tolerance (Worker Crash)
* **Source:** Python Worker tiến trình backtest bị kill đột ngột (OOM).
* **Stimulus:** Job đang xử lý dở dang (RUNNING).
* **Artifact:** Job Queue & Outbox Manager.
* **Environment:** Đang chạy tác vụ tính toán nặng.
* **Response:** Hết hạn Lease Heartbeat (30s), Worker khác tự động takeover và chạy lại.
* **Measure:** Job hoàn thành thành công, 0 stuck job.

</div>
</div>
