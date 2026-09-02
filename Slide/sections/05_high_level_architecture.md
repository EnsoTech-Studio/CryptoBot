## 15. High-Level Architecture: Modular Monolith

<div class="columns">
<div>

### Kết Nối Kiến Trúc Toàn Cục & Kỹ Thuật
* **Frontend (Next.js):** SPA / JAMstack, Event Streaming (SSE/WS) cho biểu đồ realtime.
* **Middleware (Go API Edge):** CQRS, RBAC, Rate Limiting, Binance WSS Adapter.
* **Backend Research (Python):** Plugin Architecture, Event-Driven Job Queue, Backtest Worker pool.
* **Database (Tách nhóm data):** PostgreSQL (ACID Outbox, Candles, Experiments) & Redis (Pub/Sub, Indicator cache).
* **Agent & External:** Strategy AI Agent, Crawling Agent, Binance API, OpenAI/Groq.

</div>
<div>

![High-Level Architecture](../../blueprint/assets/diagrams-png/04-high-level-architecture.png)

</div>
</div>

---

## 16. Các Design & Architectural Patterns Trọng Yếu

<div class="columns">
<div>

### Các Pattern Cốt Lõi Áp Dụng
* **CQRS (Go API):**
  * Tách biệt lệnh Command (tạo thí nghiệm) và Query (đọc nến, leaderboard) tối ưu hiệu năng.
* **Event Streaming & Kappa Architecture:**
  * Đồng nhất mô hình dữ liệu nến cho cả luồng Realtime (WSS) và Historical (Backtest dataset).
* **Transactional Outbox Pattern:**
  * Đảm bảo tính nguyên tử (Atomic) khi tạo Experiment và đẩy Job, loại bỏ rủi ro Dual-write.
* **Plugin Architecture:**
  * Tách rời hoàn toàn Core Engine khỏi logic chiến lược và thuật toán tìm kiếm.

</div>
<div>

![Outbox & Retry Flow](../../blueprint/assets/diagrams-png/07-outbox-retry-order.png)

</div>
</div>

---

## 17. Nền Tảng Multi-Agent & Vòng Lặp AI Tự Chủ

<div class="columns">
<div>

### Hệ Thống Multi-Agent & Vòng Lặp Tự Sửa Lỗi
* **Strategy Designer Agent:** Nhận prompt tự nhiên hoặc URL → sinh đặc tả Draft dạng JSON.
* **Implementation Agent:** Chuyển đổi JSON Draft thành mã Python tuân thủ `IStrategy`.
* **Self-Repair Loop (AST + Sandbox):**
  * Kiểm tra cú pháp và chạy thử trong sandbox.
  * Phản hồi lỗi runtime về LLM để tự sửa mã (tối đa 3 lần).
* **Candidate Discovery & Crawling Agent:**
  * Tự động kết hợp tham số và crawl tin tức đa nguồn.

</div>
<div>

![Agent Platform Components](../../blueprint/assets/diagrams-png/25-agent-platform-components.png)

</div>
</div>
