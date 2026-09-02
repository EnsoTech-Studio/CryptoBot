## 20. Runtime Flow: Realtime Ingestion & Gap Backfill

<div class="columns">
<div>

### Realtime Ingestion & Gap Backfill Flow
1. **Chart Initialization:** Fetch 1,000 historical candles từ Postgres/Binance REST đa timeframe (1m, 5m, 1h, 1d).
2. **WSS Stream Ingestion:** Ingest ticker & update provisional candle theo realtime ticks.
3. **Candle Close Event:** Persist candle vào Postgres và broadcast event `CandleClosed` qua SSE/WebSocket broadcaster.
4. **Gap Backfill:** Khi WSS connection drop, auto-reconnect và trigger REST API backfill bù missing candles, đảm bảo continuous time-series.

</div>
<div>

![Realtime Reconnect & Backfill Flow](../../blueprint/assets/diagrams-png/09-realtime-reconnect-backfill-flow.png)

</div>
</div>

---

## 21. Runtime Flow: Strategy Execution & Dynamic Registration

<div class="columns">
<div>

### Strategy Execution (Handcrafted / AI) & Dynamic Add Flow
* **Run Strategy Flow:**
  * Load `Datafeed` & `Sentiment Window` vào `StrategyContext`.
  * `IStrategy.evaluate()` emit trading signal `BUY` / `SELL` / `HOLD`.
  * `CompositeStrategy` aggregate signals theo majority hoặc weighted policy.
* **Add Strategy Flow (Handcrafted & AI-Generated):**
  * Handcrafted: Drop Python file vào Strategy Registry → auto-discovery & dynamic load.
  * AI-Generated: LLM Agent generate strategy code → AST validator & Sandbox verification.
* **Runtime Parity:** 100% deterministic parity giữa Live Trading và Backtest execution.

</div>
<div>

![Strategy Flow](../../blueprint/assets/diagrams-png/10-strategy-flow.png)

</div>
</div>

---

## 22. Runtime Flow: Async Backtest Pipeline

<div class="columns">
<div>

### Async Experiment & Discovery Execution Pipeline
1. **Create Experiment:** Persist experiment metadata và job event vào Outbox trong cùng một ACID transaction.
2. **Worker Lease Acquire:** Worker claim job qua Optimistic Lock (FOR UPDATE SKIP LOCKED) và duy trì heartbeat.
3. **Multi-Split Execution:** Run backtest trên `Train` (30d) → `Validation` (15d) → `Sealed Test` (15d).
4. **Compute Metrics & Leaderboard:** Calculate Sharpe Ratio, Max Drawdown, Profit Factor; persist Trade logs và update Top-K Leaderboard.

</div>
<div>

![Search Backtest Pipeline](../../blueprint/assets/diagrams-png/11-search-backtest-pipeline.png)

</div>
</div>

---

## 23. Runtime Flow: Resilient News Crawl & LLM Fallback Pipeline

<div class="columns">
<div>

### Self-Healing News Crawl & Sentiment Pipeline
1. **SSRF Validation:** Whitelist check qua `ApprovedSource`, resolve DNS và block internal/private IPs.
2. **Standard Ingestion:** Fetch & extract article content qua RSS/HTML Parser (Readability).
3. **Quality Gate Check:** Nếu DOM structure thay đổi hoặc text extraction rỗng → trigger fallback.
4. **LLM Fallback Extraction:** Dispatch raw HTML sang LLM Agent để parse structured content.
5. **Async Sentiment Scoring:** Background worker scoring sentiment [-1.0, 1.0] và persist vào PostgreSQL.

</div>
<div>

![News HTML LLM Pipeline](../../blueprint/assets/diagrams-png/13-news-html-llm-pipeline.png)

</div>
</div>
