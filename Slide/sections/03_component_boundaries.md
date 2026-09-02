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
