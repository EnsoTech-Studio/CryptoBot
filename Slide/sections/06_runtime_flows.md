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

![Realtime Reconnect & Backfill Flow](../../blueprint/assets/diagrams-png/09-realtime-reconnect-backfill-flow.png)

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

![Strategy Flow](../../blueprint/assets/diagrams-png/10-strategy-flow.png)

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

![Search Backtest Pipeline](../../blueprint/assets/diagrams-png/11-search-backtest-pipeline.png)

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

![News HTML LLM Pipeline](../../blueprint/assets/diagrams-png/13-news-html-llm-pipeline.png)

</div>
</div>
