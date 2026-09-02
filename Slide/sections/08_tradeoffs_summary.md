## 28. Architectural Tradeoffs Matrix

| Lựa Chọn Thiết Kế | Phương Án Được Chọn | Phương Án Thay Thế | Lý Do & Đánh Đổi Kiến Trúc (Rationale) |
| :--- | :--- | :--- | :--- |
| **System Architecture** | **Modular Monolith** | Microservices | **Chọn:** Giảm overhead vận hành mạng/distributed latency; enforce module boundaries qua contracts. |
| **Candle & Job Storage** | **PostgreSQL + B-Tree** | ClickHouse / InfluxDB | **Chọn:** Giữ tính ACID cho Experiments & Outbox; B-Tree indexing đủ đáp ứng hàng triệu candles. |
| **Job Queue & Event Ingress** | **PostgreSQL Outbox & Leases** | Apache Kafka / RabbitMQ / Redis | **Chọn:** Loại bỏ dual-write, ACID transactional guarantees, zero additional infrastructure dependencies. |
| **AI Code Execution** | **AST Analyzer + Sandbox** | Docker-in-Docker | **Chọn:** Low latency initialization (<10ms), static syntax safety check, minimal container resource overhead. |
| **Sentiment Analysis Pipeline** | **Hybrid: Rule + LLM Batch** | Pure LLM Realtime | **Chọn:** Optimize token cost & API rate limits; non-blocking crawl pipeline, deep LLM scoring theo batch. |

---

## 29. Replaceability & Extensibility Architecture

<div class="columns">
<div>

### Pluggable Providers & Extensible Algorithms
* **Pluggable Market Data Providers:**
  * `MarketProviderAdapter` interface cho phép switch từ Binance sang OKX, Bybit, Coinbase mà **không thay đổi** Core Frontend hay Strategy Engine.
* **Extensible Search Algorithms:**
  * Sẵn sàng plug-in Reinforcement Learning (PPO) hoặc Custom Optimizers qua interface `ISearchAlgorithm`.
* **Extensible News Ingestion:**
  * Dễ dàng add new sources (CryptoPanic, CoinDesk API) qua config `ApprovedSource`.

</div>
<div>

![Market Provider Replaceability](../../blueprint/assets/diagrams-png/20-market-provider-replaceability.png)

</div>
</div>

---

## 30. Architectural Summary & Project Conclusion

<div class="columns">
<div>

### Architectural Highlights & Key Takeaways
* **ASR-Driven Architecture:** Bám sát 4 Architectural Drivers & Quality Attributes taxonomy.
* **Clean Boundaries & Anti-God Service:** Phân rã 6 bounded contexts, zero tight-coupling.
* **Multi-Agent & Automation:** Self-repair loop (AST + Sandbox) & anti-overfitting data partitioning (Train/Val/Test).
* **High Scalability & Self-Healing:** Scale-out 100,000 backtests, Lease Takeover & Idempotent execution.

### Q & A
* *Cảm ơn Thầy và các bạn đã lắng nghe!*

</div>
<div>

### Architecture Artifacts & Verification
* **39 Blueprint Diagrams & Specs:** C4 Model (L1-L3), UML Class, State Machines, Sequence Flows, Deployment Topology.
* **5 Interactive Working Dashboards:**
  1. Realtime Market Chart & Indicators
  2. Strategy Authoring & Plugin Registry
  3. Async Backtest & Trade Visualization
  4. Search Loop & Top-K Leaderboard
  5. News Crawler & Sentiment Intelligence
* **Automated Test Scenarios & Benchmark Suite.**

</div>
</div>
