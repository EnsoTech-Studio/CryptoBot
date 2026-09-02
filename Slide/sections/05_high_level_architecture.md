## 17. High-Level Architecture: Modular Monolith

<div class="columns">
<div>

### Global Architecture & Technology Stack
* **Frontend (Next.js):** React SPA, Event Streaming (SSE/WS) cho realtime chart & telemetry.
* **API Gateway (Go Edge):** CQRS, RBAC, Rate Limiting, Binance WSS Ingestion & Broadcaster.
* **Backend Research (Python):** Strategy Plugin Architecture, Event-Driven Job Queue, Backtest Worker Pool.
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

### Core Architectural & Design Patterns
* **CQRS (Go API):**
  * Tách biệt Command (tạo experiment) và Query (đọc candles, leaderboard), optimize latency.
* **Dual-Channel Market Engine with Parity:**
  * Schema & execution parity cho cả luồng Realtime (WSS) và Historical Backfill (REST).
* **Transactional Outbox Pattern:**
  * Atomic consistency khi tạo Experiment và dispatch Job, eliminate dual-write risk.
* **Plugin Architecture:**
  * Decouple hoàn toàn Core Engine khỏi strategy logic và search algorithms (Open-Closed Principle).

</div>
<div>

![Outbox & Retry Flow](../../blueprint/assets/diagrams-png/07-outbox-retry-order.png)

</div>
</div>

---

## 19. Nền Tảng Multi-Agent & Vòng Lặp AI Tự Chủ

<div class="columns">
<div>

### Multi-Agent System & Self-Repair Loop
* **Strategy Designer Agent:** Nhận natural language prompt / URL → generate Draft spec (JSON).
* **Implementation Agent:** Transform JSON Draft thành Python code tuân thủ `IStrategy` protocol.
* **Self-Repair Loop (AST + Sandbox):**
  * Static AST syntax validation & isolated dry-run trong Sandbox.
  * Feed runtime traceback về LLM để auto self-repair code (tối đa 3 retry cycles).
* **Candidate Discovery & Crawling Agent:**
  * Automated hyperparameter sampling & multi-source news crawling.

</div>
<div>

![Agent Platform Components](../../blueprint/assets/diagrams-png/25-agent-platform-components.png)

</div>
</div>
