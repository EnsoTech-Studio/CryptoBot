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

![High-Level Architecture](../../blueprint/assets/diagrams-png/04-high-level-architecture.png)

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

![Outbox & Retry Flow](../../blueprint/assets/diagrams-png/07-outbox-retry-order.png)

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

![Agent Platform Components](../../blueprint/assets/diagrams-png/25-agent-platform-components.png)

</div>
</div>
