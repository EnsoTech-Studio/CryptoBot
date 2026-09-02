## 12. UML Class Diagram: Strategy Plugin Model

<div class="columns">
<div>

### Thiết Kế Plugin Architecture (IStrategy)
* **Contract `IStrategy` Protocol:** Phương thức `evaluate(context) -> Signal` chuẩn (`BUY`, `SELL`, `HOLD`).
* **5 Single Strategies (v1 IDs):** `ma_crossover`, `bollinger_bands`, `rsi_threshold`, `smc_structure`, `news_sentiment`.
* **Composite Strategy:** Tổ hợp 2-5 chiến lược con theo `CombinationPolicy` (`majority` hoặc `weighted`).
* **Strategy Registry:** Thêm file Python mới tự động nạp; triệt tiêu God Service và giảm coupling tuyệt đối.

</div>
<div>

![UML Strategy Plugin Model](../../blueprint/assets/diagrams-png/36-uml-strategy-plugin-model.png)

</div>
</div>

---

## 13. UML Class Diagram: Search Algorithm & Discovery Loop

<div class="columns">
<div>

### Thiết Kế Search Algorithm & 3 Phân Vùng
* **Contract `ISearchAlgorithm`:** Phương thức `sample(space, rng)` triển khai qua `RandomSearch`, `GeneticAlgorithm`, `BayesianOptimization`.
* **Vòng Lặp Discovery Chống Overfitting:**
  * **Train (30d):** Tìm kiếm và huấn luyện biến thể.
  * **Validation (15d):** Đánh giá tính tổng quát (Gate check).
  * **Sealed Test (15d):** Chấm điểm độc lập cho Leaderboard.
* **Chống Nghẽn Job:** `DiscoveryTrialReservation` (reserved_jobs=4).

</div>
<div>

![UML Search Algorithm Model](../../blueprint/assets/diagrams-png/37-uml-search-algorithm-model.png)

</div>
</div>

---

## 14. UML Class Diagram: Resilient News Crawler Model

<div class="columns">
<div>

### Thiết Kế Bộ Thu Thập & Phân Tích Tin Tức
* **Contract `NewsProvider` Protocol:** Kế thừa qua `RssNewsProvider` và `HtmlNewsProvider` (`ApprovedSource`).
* **Chốt Chặn An Toàn SSRF & Quality Gate:**
  * `Resolver` & `Fetcher` kiểm tra DNS, IP nội bộ, redirect.
  * `HtmlQualityGateFailed`: Kích hoạt `NewsExtractionHTTPAdapter` (LLM) khi web đổi DOM.
* **Tách Biệt Sentiment:** Chấm điểm batch độc lập, lỗi AI không làm sập luồng crawl.

</div>
<div>

![UML News Crawler Model](../../blueprint/assets/diagrams-png/38-uml-news-crawler-model.png)

</div>
</div>
