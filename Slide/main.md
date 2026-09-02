---
marp: true
theme: default
paginate: true
size: 16:9
header: 'CryptoBot — Software Architecture Presentation'
footer: 'Trường ĐH Khoa học Tự nhiên - ĐHQG-HCM | Bộ môn KTPM'
style: |
  section {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    font-size: 24px;
    padding: 32px 48px;
    background-color: #ffffff;
    color: #1e293b;
  }
  h1 {
    color: #0f172a;
    font-size: 36px;
    margin-bottom: 12px;
    font-weight: 700;
  }
  h2 {
    color: #1e3a8a;
    font-size: 28px;
    border-bottom: 2px solid #e2e8f0;
    padding-bottom: 8px;
    margin-top: 0;
    margin-bottom: 14px;
  }
  h3 {
    color: #2563eb;
    font-size: 23px;
    margin-top: 4px;
    margin-bottom: 8px;
  }
  p, li {
    font-size: 22px;
    line-height: 1.45;
  }
  ul {
    margin-top: 4px;
    margin-bottom: 8px;
    padding-left: 24px;
  }
  li {
    margin-bottom: 5px;
  }
  table {
    font-size: 17.5px;
    border-collapse: collapse;
    width: 100%;
    margin-top: 8px;
  }
  th {
    background-color: #f1f5f9;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    padding: 8px 12px;
    font-weight: 600;
    font-size: 18.5px;
  }
  td {
    border: 1px solid #e2e8f0;
    padding: 8px 12px;
    font-size: 17px;
    line-height: 1.4;
  }
  tr:nth-child(even) {
    background-color: #f8fafc;
  }
  .columns {
    display: grid;
    grid-template-columns: 1fr 1.15fr;
    gap: 28px;
    align-items: center;
  }
  .columns-equal {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
    align-items: start;
  }
  img {
    max-height: 480px;
    max-width: 100%;
    object-fit: contain;
    border-radius: 8px;
    border: 1px solid #e2e8f0;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
    background-color: #ffffff;
    display: block;
    margin: 0 auto;
  }
  section.lead {
    text-align: center;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
  }
  section.lead h1 {
    font-size: 42px;
    color: #1e3a8a;
  }
  section.lead h2 {
    border-bottom: none;
    font-size: 24px;
    color: #475569;
  }
---

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

---

## 7. Tổng Quan Use Case Hệ Thống

<div class="columns">
<div>

### Tác tử (Actors) & Nhóm Chức năng
* **Quant Researcher / Trader:**
  * Xem realtime candlestick chart đa timeframe (1m, 5m, 1h, 1d).
  * Thử nghiệm single strategy và composite strategy.
  * Chạy Backtest, phân tích equity curve, max drawdown, win rate.
  * Nhập prompt tự nhiên hoặc URL để AI sinh & sửa strategy code.
* **Autonomous AI Agent:**
  * Crawl financial news, trích xuất text & scoring sentiment.
  * Tự động chạy Auto Search Loop (Loop Discovery).
* **System Worker:**
  * Nạp candle định kỳ, xử lý ngầm Backtest Job Queue.

</div>
<div>

![Use Case Overview](../blueprint/assets/diagrams-png/34-use-case-overview.png)

</div>
</div>

---

## 8. C4 Model (Level 1) - System Context Diagram

<div class="columns">
<div>

### Ranh Giới & Hệ Thống Bên Ngoài
* **CryptoBot Core Platform:** Nền tảng trung tâm thu nạp market data, research strategy và chấm điểm portfolio.
* **External Systems:**
  * **Binance Exchange:** Historical candle data (REST) và BBO price stream (WebSocket).
  * **News Sources / RSS Feeds:** Cung cấp thông tin thị trường crypto đa nguồn.
  * **LLM Providers (OpenAI / Groq):** Suy luận ngôn ngữ, sentiment analysis & strategy self-repair.

</div>
<div>

![C4 Context Diagram](../blueprint/assets/diagrams-png/01-c4-l1-system-context.png)

</div>
</div>

---

## 9. C4 Model (Level 2) - Container Diagram

<div class="columns">
<div>

### Phân Rã Các Container Chính
* **Next.js Web (SPA):** UI biểu đồ realtime, cấu hình strategy & Leaderboard.
* **Go Edge Gateway (`api`):** CQRS, RBAC, Binance WSS ingestion & SSE/WS stream.
* **Python Research (`research`):** Strategy Registry, Backtest Engine & Search Loop.
* **Async Workers (`worker` pool):** Xử lý Job Queue, Outbox Events, News Crawl & AI Agent.
* **AI Service (`ai`):** Cổng LLM (Groq/OpenAI) phân tích sentiment & sinh strategy code.
* **PostgreSQL (Storage & Outbox):** Lưu trữ ACID candle data, experiments và Outbox table.

</div>
<div>

![C4 Container Diagram](../blueprint/assets/diagrams-png/02-c4-l2-container.png)

</div>
</div>

---

## 10. C4 Model (Level 3) - Python Research Platform

<div class="columns">
<div>

### Cấu Trúc Nội Bộ Python Platform
* **Strategy Registry:** Quản lý lifecycle và metadata của các strategy plugins.
* **Deterministic Backtest Engine:** Mô phỏng order execution chính xác (BBO, Slippage, Fee).
* **Search & Loop Manager:** Điều phối search algorithms (Random, Genetic, Bayesian, LLM).
* **Worker Lease Manager:** Phân phối jobs không khóa (Optimistic Lock) và tự phục hồi.
* **AST Sandbox:** Kiểm tra an toàn syntax strategy code do AI tạo ra trước khi thực thi.

</div>
<div>

![C4 Component Python Platform](../blueprint/assets/diagrams-png/03-c4-l3-python-strategy-platform.png)

</div>
</div>

---

## 11. C4 Model (Level 3) - Go Edge & Market Gateway

<div class="columns">
<div>

### Cấu Trúc Nội Bộ Go Gateway
* **Binance Adapter:** Duy trì kết nối WSS liên tục, tự động reconnect và REST Gap Backfill.
* **Candle Aggregator & BBO Streamer:** Tổng hợp provisional candle và lưu candle đóng vào CSDL.
* **CQRS Request Handler:** Phân tách rõ ràng luồng Command (tạo experiment) và Query (đọc candle, leaderboard).
* **Security & Auth Middleware:** Kiểm tra JWT token, phân quyền RBAC và rate limiting.

</div>
<div>

![C4 Component Go Gateway](../blueprint/assets/diagrams-png/35-c4-l3-go-edge-market-gateway.png)

</div>
</div>

---

## 12. Phân Định Ranh Giới 5 Module Cốt Lõi (Tránh God Service)

<div class="columns">
<div>

### 5 Miền Nghiệp Vụ Chuyên Biệt (High Cohesion)
1. **Market Realtime (Go):** Thu nạp Binance WSS candles, BBO, tự bù nến (Gap Backfill).
2. **Strategy Engine (Python):** Thực thi single & composite strategies (v1 IDs).
3. **Backtest & Discovery (Python):** Kiểm thử test set, Job Queue & Leased Worker.
4. **News Crawler (Python):** Thu thập tin RSS/HTML, kiểm soát an toàn SSRF.
5. **News Intelligence (AI):** LLM trích xuất & scoring sentiment độc lập.

* **Loose Coupling:** Giao tiếp qua standardized DTOs, PostgreSQL Outbox và Event Worker Dispatcher.

</div>
<div>

### Phân Định Trách Nhiệm Ngôn Ngữ

| Tiêu chí | Go Edge Gateway | Python Research Engine |
| :--- | :--- | :--- |
| **Miền sở hữu** | Market Ingestion & API Edge | Backtest, Strategy, Search, AI |
| **Thế mạnh** | Goroutines non-blocking, Low RAM | Toán học định lượng, AST sandbox, AI |
| **Giao thức** | REST CQRS, WSS, SSE | Worker Queue Leases, Internal DTOs |
| **Rủi ro cô lập** | Lỗi mạng sàn không làm chết Worker | Crash strategy không làm sập API |

</div>
</div>

---

## 13. Đặc Tả Ranh Giới & Phạm Vi 5 Module (Component Specs)

<div class="columns">
<div>

### 1. Market Realtime & 2. Strategy Engine
* **Market Realtime:**
  * **Input/Output:** Raw Binance WSS → `Candle` & `BBO` chuẩn hóa; lưu nến vào Postgres, phát trực tiếp `CandleClosed` qua SSE/WebSocket.
  * **Invariant:** Time-series liên tục, không duplicate candle.
* **Strategy Engine:**
  * **Thêm/Bớt:** Single strategy (Handcraft/AI) qua `IStrategy`.
  * **Discovery:** UI backtest trên historical data + Auto Search Loop.
  * **Invariant:** Parity đồng nhất 100% giữa Live Trading và Backtest.

</div>
<div>

### 3. Backtest, 4. Crawler & 5. Intelligence
* **Backtest Subsystem (Event-Driven):**
  * Chạy strategy trên test set (historical data), tối ưu hóa strategy kết hợp AI sentiment qua Job Queue & Worker.
* **News Crawler Subsystem:**
  * Thu thập tin từ `ApprovedSource` (RSS/HTML), kiểm soát SSRF, chốt chặn Quality Gate.
* **News Intelligence & Agent:**
  * LLM/Agent trích xuất khi DOM đổi và scoring sentiment [-1.0, 1.0] bất đồng bộ không nghẽn crawl.

</div>
</div>

---

## 14. UML Class Diagram: Strategy Plugin Model

<div class="columns">
<div>

### Thiết Kế Plugin Architecture (IStrategy)
* **Contract `IStrategy` Protocol:** Method `evaluate(context) -> Signal` chuẩn (`BUY`, `SELL`, `HOLD`).
* **5 Single Strategies (v1 IDs):** `ma_crossover`, `bollinger_bands`, `rsi_threshold`, `smc_structure`, `news_sentiment`.
* **Composite Strategy:** Tổ hợp 2-5 child strategies theo `CombinationPolicy` (`majority` hoặc `weighted`).
* **Strategy Registry:** Thêm file Python mới tự động nạp; triệt tiêu God Service và giảm coupling tuyệt đối.

</div>
<div>

![UML Strategy Plugin Model](../blueprint/assets/diagrams-png/36-uml-strategy-plugin-model.png)

</div>
</div>

---

## 15. UML Class Diagram: Search Algorithm & Discovery Loop

<div class="columns">
<div>

### Thiết Kế Search Algorithm & 3 Phân Vùng
* **Contract `ISearchAlgorithm`:** Method `sample(space, rng)` triển khai qua `RandomSearch`, `GeneticAlgorithm`, `BayesianOptimization`.
* **Vòng Lặp Discovery Chống Overfitting:**
  * **Train (30d):** Search & tối ưu hóa strategy variants.
  * **Validation (15d):** Đánh giá tính tổng quát (Gate check).
  * **Sealed Test (15d):** Chấm điểm độc lập cho Leaderboard.
* **Chống Nghẽn Job:** `DiscoveryTrialReservation` (reserved_jobs=4).

</div>
<div>

![UML Search Algorithm Model](../blueprint/assets/diagrams-png/37-uml-search-algorithm-model.png)

</div>
</div>

---

## 16. UML Class Diagram: Resilient News Crawler Model

<div class="columns">
<div>

### Thiết Kế Bộ Thu Thập & Phân Tích Tin Tức
* **Contract `NewsProvider` Protocol:** Kế thừa qua `RssNewsProvider` và `HtmlNewsProvider` (`ApprovedSource`).
* **Chốt Chặn An Toàn SSRF & Quality Gate:**
  * `Resolver` & `Fetcher` kiểm tra DNS, private IP, redirect.
  * `HtmlQualityGateFailed`: Kích hoạt `NewsExtractionHTTPAdapter` (LLM) khi web đổi DOM.
* **Tách Biệt Sentiment:** Scoring batch độc lập, lỗi AI không làm gián đoạn pipeline crawl.

</div>
<div>

![UML News Crawler Model](../blueprint/assets/diagrams-png/38-uml-news-crawler-model.png)

</div>
</div>

---

## 17. High-Level Architecture: Modular Monolith

<div class="columns">
<div>

### Kết Nối Kiến Trúc Toàn Cục & Kỹ Thuật
* **Frontend (Next.js):** SPA / JAMstack, Event Streaming (SSE/WS) cho biểu đồ realtime.
* **Middleware (Go API Edge):** CQRS, RBAC, Rate Limiting, Binance WSS Ingestion.
* **Backend Research (Python):** Strategy Plugin Architecture, Event-Driven Job Queue, Backtest Worker pool.
* **Database:** PostgreSQL (ACID Outbox, Candles, Experiments, News) & In-memory Ring Buffers (Go API Edge).
* **Agent & External:** Strategy AI Agent, Crawling Agent, Binance API, OpenAI/Groq.

</div>
<div>

![High-Level Architecture](../blueprint/assets/diagrams-png/04-high-level-architecture.png)

</div>
</div>

---

## 18. Các Design & Architectural Patterns Trọng Yếu

<div class="columns">
<div>

### Các Pattern Cốt Lõi Áp Dụng
* **CQRS (Go API):**
  * Tách biệt Command (tạo experiment) và Query (đọc candles, leaderboard) tối ưu latency.
* **Dual-Channel Market Engine with Parity:**
  * Đồng nhất data model cho cả luồng Realtime (WSS) và Historical Backfill (REST).
* **Transactional Outbox Pattern:**
  * Đảm bảo tính nguyên tử (Atomic) khi tạo Experiment và đẩy Job, loại bỏ rủi ro Dual-write.
* **Plugin Architecture:**
  * Tách rời hoàn toàn Core Engine khỏi strategy logic và search algorithms.

</div>
<div>

![Outbox & Retry Flow](../blueprint/assets/diagrams-png/07-outbox-retry-order.png)

</div>
</div>

---

## 19. Nền Tảng Multi-Agent & Vòng Lặp AI Tự Chủ

<div class="columns">
<div>

### Hệ Thống Multi-Agent & Vòng Lặp Tự Sửa Lỗi
* **Strategy Designer Agent:** Nhận natural language prompt / URL → sinh đặc tả Draft dạng JSON.
* **Implementation Agent:** Chuyển đổi JSON Draft thành Python code tuân thủ `IStrategy`.
* **Self-Repair Loop (AST + Sandbox):**
  * Kiểm tra cú pháp và dry-run trong execution sandbox.
  * Phản hồi runtime errors về LLM để tự sửa code (tối đa 3 lần).
* **Candidate Discovery & Crawling Agent:**
  * Tự động kết hợp hyperparameters và crawl tin tức đa nguồn.

</div>
<div>

![Agent Platform Components](../blueprint/assets/diagrams-png/25-agent-platform-components.png)

</div>
</div>

---

## 20. Runtime Flow: Luồng Nạp Nến Realtime & Gap Backfill

<div class="columns">
<div>

### Xử Lý Nến & Khôi Phục Khoảng Trống (Gap Backfill)
1. **Khởi Tạo Biểu Đồ:** Tải 1,000 historical candles từ Postgres/Binance REST cho đa timeframe (1m, 5m, 1h, 1d).
2. **Luồng Trực Tiếp (WSS Stream):** Tiếp nhận ticker & cập nhật provisional candle.
3. **Đóng Nến (Candle Close):** Lưu candle vào Postgres và phát trực tiếp sự kiện `CandleClosed` qua SSE/WebSocket broadcaster.
4. **Tự Động Bù Nến (Gap Backfill):** Khi đứt mạng WSS, tự động Reconnect và gọi REST API bù các candle bị khuyết, đảm bảo continuous time-series.

</div>
<div>

![Realtime Reconnect & Backfill Flow](../blueprint/assets/diagrams-png/09-realtime-reconnect-backfill-flow.png)

</div>
</div>

---

## 21. Runtime Flow: Thực Thi & Thêm Mới Strategy

<div class="columns">
<div>

### Run Strategy (Handcraft & Auto) & Add Strategy
* **Run Strategy Flow:**
  * Nạp `Datafeed` & `Sentiment Window` vào `StrategyContext`.
  * `IStrategy.evaluate()` sinh tín hiệu `BUY` / `SELL` / `HOLD`.
  * `CompositeStrategy` tổng hợp theo majority hoặc weighted policy.
* **Add Strategy Flow (Handcraft & AI):**
  * Handcraft: Thêm file Python vào Strategy Registry tự động load.
  * AI: LLM Agent sinh strategy code qua AST Sandbox xác thực.
* **Runtime Parity:** Strategy logic chạy đồng nhất 100% giữa Live Trading và Backtest.

</div>
<div>

![Strategy Flow](../blueprint/assets/diagrams-png/10-strategy-flow.png)

</div>
</div>

---

## 22. Runtime Flow: Pipeline Backtest Bất Đồng Bộ

<div class="columns">
<div>

### Quy Trình Thực Thi Thí Nghiệm & Khám Phá
1. **Tạo Thí Nghiệm:** Ghi thông tin experiment và events vào Outbox cùng một ACID transaction.
2. **Chiếm Quyền (Worker Lease Acquire):** Worker nhận job qua Optimistic Lock và gửi heartbeat.
3. **Thực Thi Đa Phân Vùng:** Chạy kiểm thử trên `Train` (30d) → `Validation` (15d) → `Sealed Test` (15d).
4. **Ghi Nhận Kết Quả:** Tính Sharpe Ratio, Max Drawdown, lưu Trade list và cập nhật Top-K Leaderboard.

</div>
<div>

![Search Backtest Pipeline](../blueprint/assets/diagrams-png/11-search-backtest-pipeline.png)

</div>
</div>

---

## 23. Runtime Flow: Pipeline Crawl Tin Tức & LLM Fallback

<div class="columns">
<div>

### Thu Thập & Phân Tích Tin Tức Tự Phục Hồi
1. **Kiểm Tra An Toàn SSRF:** Duyệt nguồn từ `ApprovedSource`, thẩm tra DNS và target IP.
2. **Thu Thập Chuẩn:** Trích xuất văn bản qua RSS/HTML Parser.
3. **Cổng Kiểm Tra Chất Lượng (Quality Gate):** Nếu bài viết quá ngắn hoặc web đổi DOM → Kích hoạt fallback.
4. **LLM Fallback Extraction:** Chuyển HTML sang LLM Extractor để tự động parse nội dung.
5. **Scoring Sentiment:** Chạy ngầm phân tích ngữ nghĩa và cập nhật sentiment score [-1.0, 1.0] vào CSDL.

</div>
<div>

![News HTML LLM Pipeline](../blueprint/assets/diagrams-png/13-news-html-llm-pipeline.png)

</div>
</div>

---

## 24. Kiến Trúc An Ninh: Phòng Thủ Đa Tầng

<div class="columns">
<div>

### Các Lớp Bảo Vệ Hệ Thống (Defense-in-Depth)
* **Authentication & RBAC:** Xác thực JWT, phân quyền tài nguyên theo user (cô lập dữ liệu experiment).
* **Crawler SSRF Prevention:** Chặn IP nội bộ (`127.0.0.1`, `10.0.0.0/8`, cloud metadata), chỉ duyệt domain trong `ApprovedSource`.
* **AST Sandbox & Safe Execution:** Phân tích AST mã AI sinh ra; nghiêm cấm lệnh nguy hiểm (`eval`, `subprocess`, socket).
* **Tool Invocation Boundary:** Giới hạn quyền hạn AI Agent qua DTO chặt chẽ.

</div>
<div>

![Defense in Depth](../blueprint/assets/diagrams-png/14-defense-in-depth.png)

</div>
</div>

---

## 25. Khả Năng Mở Rộng (Scalability) & Benchmark

<div class="columns">
<div>

### Scale-Out & Chiến Lược Chịu Tải 100,000 Backtests
* **Mở Rộng Ngang Không Trạng Thái (Scale-Out):**
  * Nhân bản số lượng Python Workers độc lập tùy theo tải CPU.
  * Phân phối jobs qua PostgreSQL B-Tree indexed Job Queue.
* **Kịch Bản Kiểm Thử Tải (k6 / Locust Benchmark):**
  * Mô phỏng 10,000 users gửi lệnh Backtest và query candle data đồng thời.
  * Tốc độ xử lý hàng đợi đạt > 1,500 backtests/phút trên 4 workers.
  * Độ trễ API candles và leaderboard luôn duy trì ≤ 120ms (p95).

</div>
<div>

![Job Queue Scale](../blueprint/assets/diagrams-png/15-job-queue-scale.png)

</div>
</div>

---

## 26. Xử Lý Sự Cố (Fault Tolerance) & Khôi Phục

<div class="columns">
<div>

### Cơ Chế Phục Hồi & Mô Phỏng Sự Cố
* **Chiếm Quyền Xử Lý (Worker Lease Takeover):**
  * Worker gửi heartbeat 10s/lần. Nếu worker crash, sau 30s hết hạn lease, worker khác tự động tiếp quản job.
* **Idempotency & Retry:**
  * Khóa duy nhất `idempotency_key`, loại bỏ rủi ro duplicate execution.
* **Failure Isolation & Reconnect:**
  * Lỗi 1 strategy plugin không làm sập Worker; WSS tự reconnect sàn.
* **Kịch Bản Chaos Simulation:** Chủ động tắt tiến trình worker/database để kiểm chứng khả năng self-healing.

</div>
<div>

![Worker Lease Takeover](../blueprint/assets/diagrams-png/18-worker-lease-takeover.png)

</div>
</div>

---

## 27. Triển Khai Thực Tế & MLOps

<div class="columns">
<div>

### Mô Hình Triển Khai Docker & Kubernetes Readiness
* **Container Hóa Toàn Diện (Docker Compose):**
  * Đóng gói độc lập: Next.js Web, Go Edge Gateway, Python Research API, Python Background Worker Pool (Backtest, Event, News, Agent), AI Service, PostgreSQL.
* **Health Checks Khi Triển Khai:**
  * `/healthz` và `/readyz` tự động khởi động lại container khi lỗi.
* **MLOps & Prompt Management:**
  * System prompt và API key LLM tách biệt qua biến môi trường `.env`.
* **Kubernetes Note:** Hỗ trợ replicas, scheduling, rolling update và HPA khi mở rộng quy mô lớn (MVP dùng Docker Compose).

</div>
<div>

![Deployment Topology](../blueprint/assets/diagrams-png/39-deployment-topology.png)

</div>
</div>

---

## 28. Ma Trận Đánh Đổi Kiến Trúc (Tradeoffs Matrix)

| Lựa Chọn Thiết Kế | Phương Án Được Chọn | Phương Án Thay Thế | Lý Do & Đánh Đổi Kiến Trúc (Rationale) |
| :--- | :--- | :--- | :--- |
| **Kiến trúc Tổng thể** | **Modular Monolith** | Microservices | **Chọn:** Giảm độ phức tạp vận hành mạng, đảm bảo ranh giới module rõ ràng qua contracts. |
| **Lưu trữ Candle & Jobs** | **PostgreSQL + B-Tree** | ClickHouse / InfluxDB | **Chọn:** Giữ tính ACID cho Experiments & Outbox; B-Tree index đủ đáp ứng hàng triệu candles. |
| **Hàng Đợi & Sự Kiện** | **PostgreSQL Outbox & Leases** | Apache Kafka / RabbitMQ / Redis | **Chọn:** Loại bỏ hoàn toàn Dual-write, đảm bảo Outbox nguyên tử ACID mà không cần duy trì thêm message broker ngoài. |
| **Thực Thi Mã AI Sinh** | **AST Analyzer + Sandbox** | Docker-in-Docker | **Chọn:** Khởi tạo sandbox tức thì (<10ms), kiểm soát an toàn syntax không tốn tài nguyên container. |
| **Phân Tích Sentiment** | **Hybrid: Rule + LLM Batch** | Pure LLM Realtime | **Chọn:** Tiết kiệm chi phí token API, tránh nghẽn luồng crawl; chỉ gọi LLM khi cần scoring chuyên sâu. |

---

## 29. Khả Năng Thay Thế & Mở Rộng (Replaceability)

<div class="columns">
<div>

### Dễ Dàng Thay Thế Provider & Thuật Toán
* **Thay Thế Nguồn Dữ Liệu Thị Trường (Market Provider):**
  * Thiết kế `MarketProviderAdapter` cho phép đổi từ Binance sang OKX, Bybit, Coinbase mà **không thay đổi** Frontend hay Strategy Engine.
* **Mở Rộng Thuật Toán Tìm Kiếm Nâng Cao:**
  * Sẵn sàng tích hợp mô hình Reinforcement Learning (PPO) thông qua interface `ISearchAlgorithm`.
* **Mở Rộng Nguồn Thu Thập Tin Tức:**
  * Dễ dàng bổ sung CryptoPanic, CoinDesk API qua cấu hình `ApprovedSource`.

</div>
<div>

![Market Provider Replaceability](../blueprint/assets/diagrams-png/20-market-provider-replaceability.png)

</div>
</div>

---

## 30. Tổng Kết Đồ Án & Giá Trị Kiến Trúc

<div class="columns">
<div>

### Thành Quả Đạt Được
* **Chuỗi Quyết Định Rõ Ràng:** Bám sát theo ASRs và Quality Attributes.
* **Kiến Trúc Rành Mạch, Chống Coupling:** Phân rã 5 module độc lập, triệt tiêu hoàn toàn God Service.
* **AI Agent & Tự Động Hóa:** Multi-Agent với vòng lặp self-repair và chống Overfitting (Train/Val/Test).
* **Chịu Tải & Phục Hồi Cao:** Kiểm thử 100,000 backtests, cơ chế Lease Takeover và Idempotency.

### Phần Hỏi - Đáp (Q & A)
* *Cảm ơn Thầy và các bạn đã lắng nghe!*

</div>
<div>

### Minh Chứng Đầy Đủ
* **39 Sơ Đồ Blueprint & Specs:** Đầy đủ C4 (L1-L3), UML Class, State Machine, Deployment Topology.
* **5 Màn Hình Tương Tác Sẵn Sàng:**
  1. Realtime Market Chart & Indicators
  2. Strategy Authoring & Plugin Registry
  3. Async Backtest & Trade Visualization
  4. Search Loop & Top-K Leaderboard
  5. News Crawler & Sentiment Intelligence
* **Kịch Bản Test Tự Động & Benchmark Đầy Đủ.**

</div>
</div>