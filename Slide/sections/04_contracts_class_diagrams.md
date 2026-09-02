## 14. UML Class Diagram: Strategy Plugin Model

<div class="columns">
<div>

### Strategy Plugin Architecture (IStrategy Contract)
* **Contract `IStrategy` Protocol:** Method `evaluate(context) -> Signal` (`BUY`, `SELL`, `HOLD`).
* **5 Single Strategies (v1 IDs):** `ma_crossover`, `bollinger_bands`, `rsi_threshold`, `smc_structure`, `news_sentiment`.
* **Composite Strategy:** Combine 2-5 child strategies theo `CombinationPolicy` (`majority` hoặc `weighted`).
* **Strategy Registry:** Dynamic loading file Python mới; loại bỏ God Service, loose coupling.

</div>
<div>

![UML Strategy Plugin Model](../../blueprint/assets/diagrams-png/36-uml-strategy-plugin-model.png)

</div>
</div>

---

## 15. UML Class Diagram: Search Algorithm & Discovery Loop

<div class="columns">
<div>

### Search Algorithms & 3-Split Dataset Partitioning
* **Contract `ISearchAlgorithm`:** Method `sample(space, rng)` implement qua `RandomSearch`, `GeneticAlgorithm`, `BayesianOptimization`.
* **Discovery Loop chống Overfitting (Data Leakage):**
  * **Train (30d):** Search & optimize strategy variants.
  * **Validation (15d):** Generalization evaluation (Gate check).
  * **Sealed Test (15d):** Out-of-sample benchmark cho Leaderboard.
* **Job Throttling & Fair Scheduling:** `DiscoveryTrialReservation` (reserved_jobs=4).

</div>
<div>

![UML Search Algorithm Model](../../blueprint/assets/diagrams-png/37-uml-search-algorithm-model.png)

</div>
</div>

---

## 16. UML Class Diagram: Resilient News Crawler Model

<div class="columns">
<div>

### Resilient News Crawler & Sentiment Architecture
* **Contract `NewsProvider` Protocol:** Implemented by `RssNewsProvider` và `HtmlNewsProvider` (`ApprovedSource`).
* **SSRF Guard & Quality Gate Pipeline:**
  * `Resolver` & `Fetcher` validate DNS, private IP blocking, safe redirect.
  * `HtmlQualityGateFailed`: Trigger `NewsExtractionHTTPAdapter` (LLM fallback) khi DOM thay đổi.
* **Decoupled Sentiment Scoring:** Async batch scoring, AI errors không block crawl pipeline.

</div>
<div>

![UML News Crawler Model](../../blueprint/assets/diagrams-png/38-uml-news-crawler-model.png)

</div>
</div>
