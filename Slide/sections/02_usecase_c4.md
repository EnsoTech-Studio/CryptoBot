## 7. Tổng Quan Use Case Hệ Thống

<div class="columns">
<div>

### Actors & Chức Năng Chính
* **Quant Researcher / Trader:**
  * Xem realtime candlestick chart đa timeframe (1m, 5m, 1h, 1d).
  * Thử nghiệm single strategy và composite strategy.
  * Chạy Backtest, phân tích equity curve, max drawdown, win rate.
  * Nhập natural language prompt hoặc URL để AI generate & self-repair strategy code.
* **Autonomous AI Agent:**
  * Crawl financial news, extract text & scoring sentiment.
  * Tự động trigger Auto Search Loop (Loop Discovery).
* **System Worker:**
  * Ingest candle định kỳ, process async Backtest Job Queue.

</div>
<div>

![Use Case Overview](../../blueprint/assets/diagrams-png/34-use-case-overview.png)

</div>
</div>

---

## 8. C4 Model (Level 1) - System Context Diagram

<div class="columns">
<div>

### System Boundaries & External Systems
* **CryptoBot Core Platform:** Platform trung tâm cho market data ingestion, strategy research và portfolio ranking.
* **External Systems:**
  * **Binance Exchange:** Historical candle data (REST) và BBO price stream (WebSocket).
  * **News Sources / RSS Feeds:** Cung cấp thông tin thị trường crypto đa nguồn.
  * **LLM Providers (OpenAI / Groq):** LLM reasoning, sentiment analysis & strategy self-repair.

</div>
<div>

![C4 Context Diagram](../../blueprint/assets/diagrams-png/01-c4-l1-system-context.png)

</div>
</div>

---

## 9. C4 Model (Level 2) - Container Diagram

<div class="columns">
<div>

### Container Architecture (C4 Level 2)
* **Next.js Dashboard:** Render-only UI: chart, authoring, search, backtest, trade detail & news.
* **Go Edge & Market Gateway:** Public REST/WSS, auth/quota, Candle/BBO normalization & realtime fan-out.
* **Python Research API:** Strategy/Agent runtime, experiment/search, news/sentiment orchestration & queries.
* **Python Research Worker × N:** Leased backtest/agent jobs; immutable Candle+BBO; execution; facts/outbox.
* **PostgreSQL:** Source of truth: market, strategies, jobs/results, news/sentiment & outbox.
* **Object Storage / Broker (optional):** Raw HTML by hash; replaceable queue/stream adapter.

</div>
<div>

![C4 Container Diagram](../../blueprint/assets/diagrams-png/02-c4-l2-container.png)

</div>
</div>

---

## 10. C4 Model (Level 3) - Python Research Platform

<div class="columns">
<div>

### Component Breakdown: Python Research Platform
* **Application services:** `Research API`, `Experiment/Search/Ranking`, `News/Sentiment` & `AgentOrchestrator`.
* **Domain runtime:** `StrategyRegistry + StrategyRuntime`; `Backtest Engine + Execution Simulator`; news rules; agent state/artifacts.
* **Python-owned ports:** `MarketDataPort`, `ModelGatewayPort`, `Artifact/Sandbox/Approval` & `Repository/Job/Outbox` ports.
* **Infrastructure adapters:** Go Market adapter, internal AI/LLM adapter, isolated Sandbox Runner, SafeFetcher/Readability & PostgreSQL repositories.

</div>
<div>

![C4 Component Python Platform](../../blueprint/assets/diagrams-png/03-c4-l3-python-strategy-platform.png)

</div>
</div>

---

## 11. C4 Model (Level 3) - Go Edge & Market Gateway

<div class="columns">
<div>

### Component Breakdown: Go Edge & Market Gateway
* **REST API + Auth and Ownership Guard:** Request validation/DTO mapping, JWT, RBAC & quota.
* **Public WebSocket Hub:** Subscription fan-out theo panel key.
* **MarketProviderRegistry + BinanceAdapter:** Resolve provider, REST history & WSS kline/BBO.
* **MarketNormalizer + MarketService:** Validate symbol/timeframe/decimal/timestamp/sequence; checkpoint, de-dup, persistence, reconnect & backfill.
* **Python Research Client + Internal Event Ingress:** Signed commands, queries và progress/result events.

</div>
<div>

![C4 Component Go Gateway](../../blueprint/assets/diagrams-png/35-c4-l3-go-edge-market-gateway.png)

</div>
</div>
