## 10. Phân Định Ranh Giới 5 Module Cốt Lõi (Tránh God Service)

<div class="columns">
<div>

### 5 Miền Nghiệp Vụ Chuyên Biệt (High Cohesion)
1. **Market Realtime (Go):** Thu nạp nến Binance WSS, BBO, tự bù nến (Backfill).
2. **Strategy Engine (Python):** Thực thi chiến lược đơn / composite (v1 IDs).
3. **Backtest & Discovery (Python):** Kiểm thử test set, Job Queue & Worker.
4. **News Crawler (Python):** Thu thập tin RSS/HTML, kiểm soát an toàn SSRF.
5. **News Intelligence (AI):** LLM trích xuất & chấm điểm sentiment độc lập.

* **Loose Coupling:** Giao tiếp qua DTO chuẩn hóa, PostgreSQL Outbox và Redis Event Bus.

</div>
<div>

### Phân Định Trách Nhiệm Ngôn Ngữ

| Tiêu chí | Go Edge Gateway | Python Research Engine |
| :--- | :--- | :--- |
| **Miền sở hữu** | Market Ingestion & API Edge | Backtest, Strategy, Search, AI |
| **Thế mạnh** | Goroutines non-blocking, Low RAM | Toán học, Vectorization, AST parsing |
| **Giao thức** | REST CQRS, WSS, SSE | Worker Queue Leases, Internal DTOs |
| **Rủi ro cô lập** | Lỗi mạng sàn không làm chết Worker | Crash thuật toán không làm sập API |

</div>
</div>

---

## 11. Đặc Tả Ranh Giới & Phạm Vi 5 Module (Component Specs)

<div class="columns">
<div>

### 1. Market Realtime & 2. Strategy Engine
* **Market Realtime:**
  * **Input/Output:** Raw Binance WSS → `Candle` & `BBO` chuẩn hóa; đóng nến vào Postgres, bắn `CandleClosed` qua Redis.
  * **Invariant:** Chuỗi thời gian liên tục, không duplicate.
* **Strategy Engine:**
  * **Thêm/Bớt:** Chiến lược đơn (Handcraft/AI) qua `IStrategy`.
  * **Discovery:** UI chạy trên data quá khứ + Auto Search.
  * **Invariant:** Logic chạy đồng nhất trên Live và Backtest.

</div>
<div>

### 3. Backtest, 4. Crawler & 5. Intelligence
* **Backtest Subsystem (Event-Driven):**
  * Chạy strategy trên test set (dữ liệu đầu tư), tìm kiếm chiến lược kết hợp AI sentiment qua Job Queue & Worker.
* **News Crawler Subsystem:**
  * Thu thập tin từ `ApprovedSource` (RSS/HTML), kiểm soát SSRF, chốt chặn Quality Gate.
* **News Intelligence & Agent:**
  * LLMs/Agents trích xuất khi DOM đổi và chấm điểm sentiment [-1.0, 1.0] bất đồng bộ không nghẽn crawl.

</div>
</div>
