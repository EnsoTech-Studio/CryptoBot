## 20. Runtime Flow: Luồng Nạp Nến Realtime & Gap Backfill

<div class="columns">
<div>

### Xử Lý Nến & Khôi Phục Khoảng Trống (Gap Backfill)
1. **Khởi Tạo Biểu Đồ:** Tải 1,000 nến lịch sử từ Postgres/Binance REST cho đa khung thời gian (1m, 5m, 1h, 1d).
2. **Luồng Trực Tiếp (WSS Stream):** Tiếp nhận ticker & cập nhật nến tạm thời (provisional candle).
3. **Đóng Nến (Candle Close):** Ghi nến vào Postgres và phát tán trực tiếp sự kiện `CandleClosed` qua SSE/WebSocket broadcaster.
4. **Tự Động Bù Nến (Gap Backfill):** Khi đứt mạng WSS, tự động Reconnect và gọi REST API bù các nến bị khuyết, đảm bảo chuỗi thời gian liên tục.

</div>
<div>

![Realtime Reconnect & Backfill Flow](../../blueprint/assets/diagrams-png/09-realtime-reconnect-backfill-flow.png)

</div>
</div>

---

## 21. Runtime Flow: Thực Thi & Thêm Mới Chiến Lược

<div class="columns">
<div>

### Run Strategy (Handcraft & Auto) & Add Strategy
* **Run Strategy Flow:**
  * Nạp `Datafeed` & `Sentiment Window` vào `StrategyContext`.
  * `IStrategy.evaluate()` sinh tín hiệu `BUY` / `SELL` / `HOLD`.
  * `CompositeStrategy` tổng hợp theo trọng số hoặc đa số.
* **Add Strategy Flow (Handcraft & AI):**
  * Handcraft: Thêm file Python vào Registry tự động load.
  * AI: LLM Agent sinh code qua AST Sandbox xác thực.
* **Runtime Parity:** Logic chạy đồng nhất 100% trên cả Live và Backtest.

</div>
<div>

![Strategy Flow](../../blueprint/assets/diagrams-png/10-strategy-flow.png)

</div>
</div>

---

## 22. Runtime Flow: Pipeline Backtest Bất Đồng Bộ

<div class="columns">
<div>

### Quy Trình Thực Thi Thí Nghiệm & Khám Phá
1. **Tạo Thí Nghiệm:** Ghi thông tin thí nghiệm và sự kiện vào Outbox cùng một ACID transaction.
2. **Chiếm Quyền (Worker Lease Acquire):** Worker nhận job qua khóa lạc quan (Optimistic Lock) và gửi heartbeat.
3. **Thực Thi Đa Phân Vùng:** Chạy kiểm thử trên `Train` (30d) → `Validation` (15d) → `Sealed Test` (15d).
4. **Ghi Nhận Kết Quả:** Tính Sharpe, Drawdown, lưu Trade list và cập nhật Top-K Leaderboard.

</div>
<div>

![Search Backtest Pipeline](../../blueprint/assets/diagrams-png/11-search-backtest-pipeline.png)

</div>
</div>

---

## 23. Runtime Flow: Pipeline Crawl Tin Tức & LLM Fallback

<div class="columns">
<div>

### Thu Thập & Phân Tích Tin Tức Tự Phục Hồi
1. **Kiểm Tra An Toàn SSRF:** Duyệt nguồn từ `ApprovedSource`, thẩm tra DNS và IP đích.
2. **Thu Thập Chuẩn:** Trích xuất văn bản qua RSS/HTML Parser.
3. **Cổng Kiểm Tra Chất Lượng (Quality Gate):** Nếu độ dài bài viết quá ngắn hoặc web đổi DOM → Kích hoạt fallback.
4. **LLM Fallback Extraction:** Chuyển HTML sang LLM Extractor để tự động nhận diện nội dung.
5. **Chấm Điểm Sentiment:** Chạy ngầm phân tích ngữ nghĩa và cập nhật điểm [-1.0, 1.0] vào cơ sở dữ liệu.

</div>
<div>

![News HTML LLM Pipeline](../../blueprint/assets/diagrams-png/13-news-html-llm-pipeline.png)

</div>
</div>
