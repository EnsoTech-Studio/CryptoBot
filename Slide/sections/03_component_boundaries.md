## 12. Component Boundaries: 6 Module Cốt Lõi (Anti-God Service)

<div class="columns">
<div>

### 6 Bounded Contexts (High Cohesion)
1. **Market Realtime (Go Edge):** WSS candles/BBO, gap backfill.
2. **Strategy Engine (Python):** Single/composite runtime.
3. **Backtest (Python Worker):** Candle+BBO replay, execution facts.
4. **Discovery (Python):** Search Loop, validation, stop conditions.
5. **News Crawler (Python):** RSS/HTML, SSRF guard, quality gate.
6. **News Intelligence (Python + AI adapter):** Extraction & async sentiment.
* **Loose Coupling:** Giao tiếp qua versioned DTOs & Outbox events.

</div>
<div>

### Trách Nhiệm Công Nghệ (Go vs Python)

| Tiêu chí | Go Edge & Market Gateway | Python Strategy Platform |
| :--- | :--- | :--- |
| **Ownership** | Market Ingestion, API Edge & Fan-out | Strategy, Backtest, Discovery, News/Agents/Ranking |
| **Strengths** | Goroutines, Low RAM, high concurrency | Quantitative math, AST, AI/ML |
| **Protocols** | Public REST/WSS, signed events | Internal HTTP, DTOs, Job/Outbox |
| **Isolation** | Network drops không crash Worker | Crash strategy không sập API |

</div>
</div>

---

## 13. Đặc Tả Ranh Giới & Phạm Vi 6 Module (Component Specs)

<div class="columns">
<div>

### 1. Market Realtime & 2. Strategy Engine
* **Market Realtime:**
  * **Input/Output:** Raw Binance WSS → Normalized `Candle` & `BBO`; persist vào Postgres, broadcast `CandleClosed` event qua SSE/WebSocket.
  * **Invariant:** Continuous time-series, zero-duplicate candle.
* **Strategy Engine:**
  * **Pluggable:** Single strategy (Handcrafted/AI) qua `IStrategy`.
  * **Scope:** Strategy Registry, indicators và single/composite runtime.
  * **Invariant:** 100% execution parity giữa Live Trading và Backtest.

</div>
<div>

### 3. Backtest & 4. Discovery
* **Backtest Subsystem (Event-Driven):**
  * Replay immutable Candle+BBO với cùng `StrategyRuntime`, simulate execution và emit trade/evaluation facts qua Worker/Outbox.
* **Discovery Subsystem:**
  * Generate candidates, orchestrate Search Loop và backtest jobs qua Train/Validation/Sealed Test; enforce lineage và stop conditions.

### 5. News Crawler & 6. News Intelligence
* **News Crawler Subsystem:**
  * Fetch news từ `ApprovedSource` (RSS/HTML), SSRF protection, Quality Gate validation.
* **News Intelligence Subsystem:**
  * Orchestrate LLM/Agent extraction khi DOM thay đổi và scoring sentiment [-1.0, 1.0] async (non-blocking crawl).

</div>
</div>
