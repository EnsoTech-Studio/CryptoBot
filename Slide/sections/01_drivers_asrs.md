<!-- _class: lead -->
<div class="lead-institution">
  <div class="lead-uni">Trường Đại học Khoa học Tự nhiên - ĐHQG HCM</div>
  <div class="lead-faculty">Khoa Công nghệ thông tin</div>
</div>

![SELab Logo](../selab.jpeg)

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
  * Cần môi trường ingest candle low-latency (<200ms) đa timeframe (1m, 5m, 1h, 1d).
  * Backtest strategy chính xác, đo lường Sharpe Ratio, Max Drawdown, Profit Factor, Win Rate.
* **Autonomous AI Agents (LLM Multi-Agent):**
  * Tự động crawl financial news, scoring sentiment.
  * Tự generate strategy code, debug và scan hyperparameter space.

</div>
</div>

---

## 2. Bài Toán Thực Tế & Thách Thức (Problem Statement)

<div class="columns-equal">
<div>

### Thách Thức Về Market Data & Order Execution
* **Realtime Data Jitter & Packet Drop:**
  * WebSocket bị drop/jitter làm mất candle → Sai lệch entry/exit signals.
  * *Yêu cầu:* Auto-detect candle gap & bù dữ liệu tự động (Gap Backfill).
* **Bẫy "Lookahead Bias" & Parity Mismatch:**
  * Backtest giả lập phi thực tế (nhìn trước tương lai, bỏ qua slippage/phí) → Khi chạy Live bị lỗ.
  * *Yêu cầu:* Deterministic Replay Engine simulate sát sao slippage, BBO limit fill và trading fees.

</div>
<div>

### Thách Thức Về Scalability & Architecture
* **Combinatorial Explosion (Bùng nổ không gian tìm kiếm):**
  * Quét hàng ngàn parameter combinations / technical indicators gây block UI nếu chạy sync.
  * *Yêu cầu:* Async Outbox Job Queue & Worker Pool.
* **Tightly Coupled & Vendor Lock-in:**
  * Source code bị trói chặt vào một sàn/thư viện duy nhất, khó scale/add strategy.
  * *Yêu cầu:* Strategy Plugin Architecture & AST Sandbox an toàn.

</div>
</div>

---

## 3. Bối cảnh & 4 Nhóm Architectural Drivers

<div class="columns">
<div>

### Architectural Drivers (ASRs)
* **Realtime Market Ingestion:** Dữ liệu biến động mili-giây, stream liên tục và tự bù candle gap (Gap Backfill).
* **High Modifiability:** Thêm/bớt single strategy và composite strategy (Handcrafted / LLM Agent) không sửa Core.
* **Massive Search Scalability:** Auto-discovery hàng ngàn parameters (Loop Discovery) non-blocking UI.
* **Unstructured News Intelligence:** Crawl multi-source news, self-healing khi DOM thay đổi và scoring sentiment.

</div>
<div>

### Quyết định Kiến trúc Tương ứng
* **Driver 1 → Dual-Channel Ingestion & Gap Repair:** Tách biệt stream WSS realtime và Historical REST Backfill, data parity.
* **Driver 2 → Strategy Plugin Architecture & AST Sandbox:** Chuẩn hóa IStrategy contract, dynamic plugin loading.
* **Driver 3 → Event-Driven Job Queue & Leased Worker:** Phân tán workload Backtest qua PostgreSQL Outbox & Worker pool.
* **Driver 4 → Multi-Agent & LLM Fallback:** Auto-detect cấu trúc HTML, LLM fallback parsing và scoring sentiment.

</div>
</div>

---

## 4. Hệ Thống Quality Attributes (ASRs Taxonomy)

| Thuộc tính (QA) | Trọng tâm Thiết kế | Tactic / Kỹ thuật Kiến trúc Áp dụng |
| :--- | :--- | :--- |
| **Modifiability** | Thêm mới Strategy, Search Algorithm, Market Provider không sửa Core | Strategy Plugin Architecture, Open-Closed Principle, Dynamic Registry |
| **Scalability** | Xử lý workload >100,000 backtests và stream candle realtime | Scale-out Python Worker pool, PostgreSQL Leased Job Queue, In-memory Broadcaster |
| **Realtime / Perf** | Latency cập nhật candle < 200ms, high throughput Backtest | Go Edge Gateway, WebSocket Streaming, Deterministic Replay Engine |
| **Reliability** | Fault isolation (lỗi crawl/search không crash API); auto-reconnect sàn | Failure Isolation, Transactional Outbox, Lease Takeover |
| **Observability** | Monitor Worker health, tiến độ Search Loop & telemetry metrics | Structured Logging, State Machine tracking, Run Metrics |
| **Reproducibility** | Kết quả Backtest và Leaderboard đảm bảo tính Deterministic & Immutable | Immutable Dataset snapshots, Run Config Hash, Seed Lock |

---

## 5. Kịch Bản ASR Chi Tiết (Modifiability & Scalability)

<div class="columns">
<div>

### ASR-1: Modifiability (Thêm Strategy mới)
* **Source:** Quant Researcher / AI Agent.
* **Stimulus:** Thêm strategy class mới (`MACDStrategy`).
* **Artifact:** Strategy Subsystem & UI Registry.
* **Environment:** Hệ thống đang chạy (Runtime).
* **Response:** Auto-discovery, load metadata lên UI không cần compile lại Go Gateway hay sửa Core.
* **Measure:** Thao tác trên 1 file Python độc lập, 0 downtime.

</div>
<div>

### ASR-2: Scalability (High Backtest Workload)
* **Source:** User trigger Auto Search Loop.
* **Stimulus:** 10,000 backtest jobs vào Job Queue đồng thời.
* **Artifact:** Job Queue & Python Worker Pool.
* **Environment:** Peak workload (tải cao điểm).
* **Response:** Phân phối jobs qua Lease Heartbeat, worker scale-out, zero OOM / memory leak.
* **Measure:** Completion rate 100%, 0 dropped job, stable CPU.

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
* **Response:** Auto-reconnect, trigger REST Backfill bù missing candles, deduplicate bằng Open Time.
* **Measure:** Continuous candle stream, 0 duplicate, catch-up latency < 2s.

</div>
<div>

### ASR-4: Fault Tolerance (Worker Crash)
* **Source:** Python Worker process bị kill đột ngột (OOM).
* **Stimulus:** Job đang xử lý dở dang (RUNNING).
* **Artifact:** Job Queue & Outbox Manager.
* **Environment:** Heavy computation workload.
* **Response:** Lease Heartbeat timeout (30s), Worker khác auto-takeover và retry job.
* **Measure:** Job hoàn thành thành công, 0 stuck / orphaned job.

</div>
</div>
