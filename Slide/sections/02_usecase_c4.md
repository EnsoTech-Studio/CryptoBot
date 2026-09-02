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

![Use Case Overview](../../blueprint/assets/diagrams-png/34-use-case-overview.png)

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

![C4 Context Diagram](../../blueprint/assets/diagrams-png/01-c4-l1-system-context.png)

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

![C4 Container Diagram](../../blueprint/assets/diagrams-png/02-c4-l2-container.png)

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

![C4 Component Python Platform](../../blueprint/assets/diagrams-png/03-c4-l3-python-strategy-platform.png)

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

![C4 Component Go Gateway](../../blueprint/assets/diagrams-png/35-c4-l3-go-edge-market-gateway.png)

</div>
</div>
