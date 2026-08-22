# Crypto Strategy Lab — Project Proposal

> Phần 1 / Blueprint • Tài liệu đề xuất • Phiên bản 1.3

## 1. Vấn đề

Thị trường cryptocurrency hoạt động **24/7**, giá biến động liên tục và được biểu diễn bằng biểu đồ nến (OHLCV). Trader dùng nhiều phương pháp phân tích kỹ thuật — MA, RSI, Bollinger Bands, Support/Resistance, SMC, Wyckoff — để tìm thời điểm Buy/Sell/Hold.

Vấn đề cốt lõi: **không có một strategy đơn lẻ nào hoạt động tốt trong mọi điều kiện thị trường**.

| Strategy            | Tốt khi                     | Kém khi                                        |
| ------------------- | --------------------------- | ---------------------------------------------- |
| MA (Moving Average) | Thị trường có xu hướng rõ   | Thị trường đi ngang (sideway) → tín hiệu nhiễu |
| RSI                 | Phát hiện quá mua/quá bán   | Trend mạnh → báo "quá mua" liên tục nhưng sai  |
| Bollinger Bands     | Biến động co giãn theo chu kỳ | Breakout thật bị hiểu là mean-reversion       |
| Support/Resistance  | Xác định vùng giá quan trọng | Chất lượng phụ thuộc hoàn toàn vào thuật toán tìm vùng |

Vì vậy câu hỏi của đồ án là: **có thể xây dựng một hệ thống cho phép bổ sung nhiều strategy khác nhau, tự động kết hợp chúng thành strategy phức hợp, đánh giá hiệu quả và liên tục tìm ra những tổ hợp tốt nhất hay không?**

Nhưng cách làm sai — và là cái mà đồ án này phải tránh — là viết tất cả vào một chỗ:

```text
for 100000 strategies:
    calculate indicator
    backtest
    save DB
    update UI          ← tất cả nằm trong 1 function
```

Kiến trúc kiểu này gây ra một chuỗi hệ quả cụ thể, quan sát được:

- **Thêm 1 strategy phải sửa nhiều module**: `Controller` → `Backtester` → `UI` → `Database` → `Combination Engine` → `Evaluator`. Thêm `MACDStrategy` biến thành một PR sửa 20 file.
- **Không thay được thuật toán tìm kiếm**: đổi Random Search sang Genetic Search buộc phải viết lại Backtester vì hai thứ này bị trộn vào nhau.
- **Không thay được nguồn dữ liệu**: frontend parse trực tiếp payload Binance → thêm OKX phải sửa frontend.
- **Không tái lập được kết quả**: Leaderboard hiển thị `+18.2%` nhưng không ai biết con số đó sinh ra từ strategy version nào, tham số nào, dataset nào, phí/slippage bao nhiêu.
- **Không quan sát được**: search loop chạy 40 phút, không biết đang test candidate thứ mấy, bao nhiêu job lỗi, còn chạy hay đã treo.
- **Không scale được**: 10.000 candidate × 2 giây/candidate = 20.000 giây tuần tự (≈ 5,5 giờ) trên một process duy nhất.
- **Một lỗi nhỏ làm sập cả hệ thống**: News crawler gọi thẳng model ML; model chết → crawler chết → không có gì chạy nữa, kể cả biểu đồ giá.

Đây đều là **vấn đề kiến trúc phần mềm**, không phải vấn đề tài chính. Trọng tâm đồ án vì thế là kiến trúc, không phải tìm ra strategy đầu tư tốt nhất. [Đề bài §2, §24, §44]

## 2. Mục tiêu

### 2.1 Mục tiêu nghiệp vụ

Xây dựng nền tảng **Crypto Strategy Lab** biến bài toán "tôi có một ý tưởng strategy" thành một quy trình có hệ thống:

```text
Plugin Strategy → Combine → Backtest → Evaluate → Compare → Leaderboard → Visualize
                                     ↑                                        │
                                     └──────────── Improve ←──────────────────┘
```

Cụ thể, hệ thống phải:

1. Nhận dữ liệu thị trường crypto từ Binance (historical + realtime).
2. Hiển thị biểu đồ nến realtime, tối đa **4 khung thời gian** đồng thời, mỗi chart đổi timeframe độc lập.
3. Cho phép bổ sung strategy phân tích kỹ thuật mới **không sửa code hiện có**.
4. Kết hợp nhiều strategy thành composite strategy theo policy khai báo được.
5. Backtest trên dữ liệu lịch sử, sinh trade và metrics.
6. Xếp hạng strategy theo hiệu quả (Leaderboard Top-K).
7. Tự động tìm kiếm tổ hợp tốt hơn bằng search loop **có điều kiện dừng rõ ràng**.
8. Visualize tín hiệu và giao dịch lên biểu đồ.
9. Thu thập tin tức liên quan coin/pair và phân tích sentiment bằng ML.
10. Cho phép sentiment trở thành một strategy như mọi strategy khác.

### 2.2 Mục tiêu kiến trúc (định lượng, đo được)

Đây là các chỉ tiêu dùng để **chứng minh** kiến trúc, không phải khẩu hiệu. Mỗi dòng có một cách kiểm chứng cụ thể ở §6.

**Nguồn gốc của từng chỉ tiêu** — ba nhãn dùng xuyên suốt tài liệu này:

| Nhãn | Nghĩa |
| ---- | ----- |
| **[SRC]** *source requirement* | Đề bài nói tường minh. Không thương lượng được. |
| **[PD]** *product decision* | Nhóm tự quyết để sản phẩm dùng được / an toàn. Đề bài không nói, và cũng không cấm. |
| **[NFR]** *team target* | Ngưỡng nhóm tự đặt để có cái đo. Con số cụ thể là lựa chọn của nhóm, có thể điều chỉnh nếu môi trường đo khác. |

Ba nhãn này quan trọng vì trộn chúng lại sẽ làm sai ý nghĩa của đề bài: nói "đề bài yêu cầu p95 < 1.5 s" là **không đúng** — đề bài chỉ nói "cập nhật với độ trễ thấp" (§32.3), còn `1.5 s` là ngưỡng nhóm chọn để có thể kiểm chứng.

**Điều kiện đo chung** cho mọi chỉ tiêu có đơn vị thời gian, trừ khi dòng đó ghi khác:

| Yếu tố | Giá trị |
| ------ | ------- |
| Môi trường | `docker compose up` trên **một** máy, không container nào bị giới hạn CPU/memory tường minh; máy tham chiếu ≥ 4 core / 8 GiB RAM |
| Dataset | `ETHUSDT`, timeframe `5m`, 10.000 nến đã cache trong PostgreSQL (không gọi Binance trong lúc đo) |
| Replicas | `web=1, api=1, lab=1, worker=1` — trừ dòng scale ghi rõ `worker=4` |
| Client | 1 browser tab, 4 panel; cho load test: `k6`/`hey` 10 virtual user, 60 s, không ramp |
| Cách đo latency | p95 trên **≥ 20 mẫu**, đo từ Go API (không tính RTT internet); loại 5 request đầu (warm-up JIT/pool) |
| Trạng thái ban đầu | Migration xong, dữ liệu khởi tạo xong, `/ready` = 200 trên cả 3 service |

| Chỉ tiêu | Nguồn | Mục tiêu | Điều kiện đo riêng |
| --- | --- | --- | --- |
| Số file phải sửa khi thêm `MACDStrategy` | **[SRC]** §41 | **≤ 2 file mới + 0 file core** | `git diff --stat` giữa hai commit; "core" = Go `StrategyRegistry`, backtest/evaluator/ranking, Go API, schema, UI |
| Số file phải sửa khi đổi Random → Domain-Guided Search | **[SRC]** §42 | **1 file mới implement `CandidateGenerator`**, 0 file Backtester | `git diff --stat`; config đổi 1 dòng không tính là file core |
| Số file frontend phải sửa khi thêm `OKXAdapter` | **[SRC]** §40.3 | **0** | `git diff --stat -- web/` rỗng |
| Độ trễ Binance candle → UI (p95) | **[NFR]** cho §32.3 | **< 1.5 s** | Đo từ `kline.T` (close time trong payload Binance) tới timestamp client nhận frame WS; đồng hồ client và server sync qua NTP, sai số ghi nhận < 50 ms; 20 nến `1m` liên tiếp |
| Latency `GET /api/v1/markets/candles` (1000 nến, p95) | **[NFR]** | **< 300 ms** | Nến đã có trong PostgreSQL (cache hit); 10 VU × 60 s; đo tại Go |
| Latency `POST /api/v1/experiments` trả `run_id` (p95) | **[NFR]** cho ADR-006 | **< 500 ms** | Dataset 200 nến; đo tới lúc nhận `202`, **không** chờ backtest; 20 request tuần tự |
| Throughput backtest 1 worker | **[NFR]** | **≥ 0.5 candidate/giây** | 10.000 nến `5m`, composite 3 strategy (MA+RSI+SR), `worker=1`, không có search run khác chạy; đo trên 40 candidate liên tiếp, lấy trung bình |
| Tăng tốc khi scale 1 → 4 worker | **[SRC]** §43 (yêu cầu scale) + **[NFR]** (con số 3×) | **≥ 3×** | Cùng một `search_run` 40 candidate, cùng dataset, cùng seed; chạy `worker=1` rồi `worker=4`; so wall-clock từ `started_at` tới `finished_at` của run |
| Đổi timeframe Chart 1 làm Chart 2/3/4 re-render | **[SRC]** §5 | **0 lần** | React Profiler hoặc render counter trong `useEffect`; 4 panel đang subscribe, đổi Chart 1 từ `5m` → `1h` |
| Mất nến khi Binance WebSocket disconnect 60 s | **[SRC]** §32.4 | **0 nến đã đóng** | `docker network disconnect` container `lab` 60 s rồi nối lại; sau đó query `candles` và kiểm tra không có gap theo `open_time` và timeframe |
| Search loop chạy vô hạn | **[SRC]** §23 | **Không xảy ra** | Mọi `search_runs` row có `stop_conditions` khác NULL (DB `CHECK`); test cố INSERT run thiếu stop condition → bị từ chối |
| Kết quả Leaderboard không truy được nguồn gốc | **[SRC]** §36, §40.8 | **0 entry** | `SELECT count(*) FROM leaderboard_entries le LEFT JOIN evaluations e ... WHERE e.id IS NULL` = 0; và mỗi entry resolve đủ 6 bảng provenance (§4.3) |
| News/Sentiment down → chart và backtest technical | **[SRC]** §40.5, §40.6 | **Vẫn chạy 100%** | `docker stop` sentiment; sau đó chart nhận nến mới và một backtest technical chạy `completed`; news trả `sentiment: null` |
| Backtest cùng snapshot chạy 2 lần cho kết quả khác nhau | **[SRC]** §36 (reproducibility) | **0 ca** | Cùng `experiment` với `force=true`; so `total_return_pct`, `win_rate_pct`, `max_drawdown_pct`, `trade_count` đến **6 chữ số thập phân** |
| Outbox có event không tới được consumer | **[PD]** cho §5.7 | **0 event `dead`** ở trạng thái bình thường | `SELECT count(*) FROM domain_events WHERE dispatch_status='dead'` = 0 sau khi chạy hết demo S1–S10 |

Ba chỉ tiêu **[NFR]** về latency là ngưỡng nhóm chọn, không phải yêu cầu đề bài. Nếu môi trường đo yếu hơn máy tham chiếu, nhóm ghi lại số đo thật và điều kiện đo thay vì hạ ngưỡng âm thầm — con số kèm điều kiện có giá trị, con số không kèm điều kiện thì không kiểm chứng được.

### 2.3 Ba câu hỏi kiến trúc quyết định điểm

Toàn bộ blueprint này được tổ chức để trả lời dứt điểm 3 câu:

1. **Thêm strategy mới** → chỉ implement `Strategy` + đăng ký metadata. Không có `if strategy == "MA" ... else if ...` ở bất kỳ đâu. (§7.1, ADR-002)
2. **Thay thuật toán search** → chỉ implement `CandidateGenerator`. Pipeline phía sau chỉ nhận `CandidateStrategy`. (§7.2, ADR-004)
3. **Scale 100 → 100.000 backtest** → cùng một job contract từ ngày đầu; scale là đổi số replica của workload `worker` (`--scale worker=N`). Không đổi API, không đổi schema, không đổi `BacktestEngine.run()`. (§7.3, ADR-005)

## 3. Người dùng và nhu cầu

Hệ thống là **nền tảng nghiên cứu**, không phải sàn giao dịch. Người dùng vì thế là người phân tích, không phải người đặt lệnh.

> **Nguồn gốc: [PD] — product decision.** Đề bài không định nghĩa vai trò người dùng nào. Bốn vai trò dưới đây là nhóm suy ra từ các chức năng mà đề bài yêu cầu (§32.7 đòi hỏi ai đó *theo dõi* loop; §12 đòi hỏi ai đó *thêm* strategy; §41 mô tả giảng viên *kiểm tra* khả năng mở rộng). Việc phân vai là cơ sở cho RBAC ở §6, không phải trích dẫn từ đề bài.

| Vai trò                       | Nhu cầu chính                                                                                                      | Ràng buộc                                                                     |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------- |
| **Researcher** (vai trò chính) | Xem 4 chart multi-timeframe realtime; bật/tắt indicator; chạy backtest; xem Leaderboard; click 1 entry để xem trade và tín hiệu trên chart | Dùng desktop browser; cần thấy tiến trình search chứ không chỉ kết quả cuối |
| **Strategy Developer**        | Thêm strategy mới bằng cách viết 1 class; khai báo parameter schema; strategy tự xuất hiện trong UI                | Không được đụng vào core engine; strategy phải test được offline không cần DB/HTTP |
| **Operator**                  | Biết loop đang chạy hay dừng, đã thử bao nhiêu candidate, bao nhiêu job lỗi, Top-1 hiện tại; pause/resume/cancel run | Chỉ có UI + log + metrics; không SSH vào container để đoán               |
| **Giảng viên / Reviewer**     | Kiểm tra khả năng mở rộng bằng scenario trực tiếp ("thêm MACD đi"); truy nguồn 1 con số trên Leaderboard           | Đánh giá kiến trúc qua diff code và tài liệu, không qua lợi nhuận strategy    |

Phân vai trò này là lý do có **RBAC 3 role** (§6) chứ không phải hệ thống một-người-dùng: `Operator` được pause search run của người khác, `Researcher` chỉ thao tác trên experiment của mình. RBAC, JWT RS256 và quota cũng là **[PD]** — đề bài không yêu cầu authentication; nhóm thêm vì một hệ thống nhận request tạo work nặng mà không có principal thì không kiểm soát được quota, và quota là điều kiện để §32.5 (Performance) có nghĩa. Chi tiết phân loại ở §4.4.

## 4. Phạm vi

### 4.1 Trong phạm vi (In scope)

**Market & Chart**

- Binance adapter: REST historical klines + WebSocket realtime kline stream.
- Chuẩn hoá về `Candle` nội bộ; frontend **không bao giờ** thấy payload Binance.
- Dashboard 4 panel độc lập; mỗi panel có `(provider, symbol, timeframe)` riêng, subscription riêng.
- Overlay: candlestick, volume, MA, Bollinger Bands, Support/Resistance zone, Buy/Sell signal; entry/exit/SL/TP marker khi chọn một experiment result.

**Strategy & Combination**

- Strategy registry theo Plugin Architecture; ≥ 4 strategy đơn lẻ: `MAStrategy`, `RSIStrategy`, `BollingerStrategy`, `SupportResistanceStrategy`.
- `NewsSentimentStrategy` là strategy thứ 5, dùng đúng contract, khai báo `family="information"` — chứng minh kiến trúc không giới hạn ở Technical Analysis.
- Composite strategy với ≥ 2 combination policy: `majority_vote` và `weighted_vote` (policy lưu trong snapshot, không hard-code).

**Experiment & Search**

- `ExperimentSnapshot` bất biến: candidate definition + dataset version + execution assumptions (fee, slippage, fill policy, **risk policy**) + evaluator version.
- Backtest engine deterministic, merge BBO + CandleClosed, fill LIMIT theo executable quote, không look-ahead (causal candle/indicator view + event ordering).
- **Stop Loss / Take Profit** cố định theo % của `entry_price`, kèm `intrabar_priority` để giả định "SL hay TP chạm trước" là tường minh chứ không ẩn trong code. Đây là **MVP** vì chart phải vẽ được SL/TP theo yêu cầu đề bài — xem `design.md` ADR-017.
- Evaluator tách khỏi backtester: Total Return, Win Rate, Max Drawdown, Number of Trades, Profit Factor, Sharpe Ratio.
- `RandomSearchGenerator` (bắt buộc) + `DomainGuidedGenerator` (chứng minh replaceability, dùng phân nhóm Trend/Momentum/Volatility/Structure/Information).
- Search run có **stop condition bắt buộc**: max candidate / max duration / max non-improving; hỗ trợ pause/resume/cancel idempotent.
- Leaderboard Top-K với scoring policy có version.

**News & Sentiment**

- News provider adapter (RSS + News API) trả về `Item` chuẩn hoá; crawler **không** biết gì về ML.
- Sentiment service riêng (FastAPI hiện có): `POSITIVE | NEUTRAL | NEGATIVE` + score + `model_version`.

**Nền tảng & Vận hành**

- **Code artifacts — 3 image**: Next.js web, Go Strategy Service, Python AI inference. **Runtime workloads — 4 loại**: `web`, `api`, `worker` (dùng lại image Go, khác entrypoint), và `ai`. Thêm PostgreSQL. Phân biệt artifact/workload ở `design.md` §1.3.1.
- **Backtest Worker là kiến trúc bắt buộc**, không phải tính năng tuỳ chọn: `POST /experiments` **luôn** async (ADR-006) nên phải có worker consume job. Có từ **Phase 3** với 1 replica; scale lên N replica ở Phase 6 chỉ là lúc **đo để chứng minh** (demo S10), không phải lúc mới được phép scale.
- **Redis là tuỳ chọn có điều kiện**: chỉ thêm ở Phase 6 nếu benchmark thoả điều kiện ở `design.md` §12.0. Không thêm cũng là một kết quả hợp lệ.
- Job queue cho backtest: bảng `backtest_jobs` trong PostgreSQL + `SELECT ... FOR UPDATE SKIP LOCKED` + `lease_token`, không cần broker.
- Transactional outbox (`domain_events` + `event_consumptions`) cho event cross-process giữa Worker và Evaluator/Ranking (`design.md` §5.7).
- Observability: structured log + `/metrics` Prometheus + UI progress panel.
- `docker compose up` chạy toàn bộ stack có dữ liệu khởi tạo sẵn.

### 4.2 Ngoài phạm vi (Out of scope)

| Không làm                                             | Lý do                                                                                            |
| ----------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| **Giao dịch tiền thật, đặt lệnh, lưu API key sàn**    | Ranh giới nhóm tự đặt (**[PD]**, §4.3): hệ thống là simulation-only. Không có custody, không có order. |
| Tư vấn đầu tư / khuyến nghị mua bán                   | Không phải mục tiêu đồ án; mọi output là kết quả mô phỏng.                                       |
| Genetic Algorithm, Bayesian Optimization, RL, LLM-generated strategy | Phần mở rộng của đề bài. Kiến trúc *cho phép* cắm vào (`CandidateGenerator`) nhưng không implement. |
| SMC, Wyckoff đầy đủ                                   | Đề bài không bắt buộc. Chỉ cần chứng minh kiến trúc admit được — có `strategy family: structure` sẵn. |
| Kafka, RabbitMQ, CQRS, Event Sourcing, microservice per module | Đề bài nói rõ: **không cộng điểm vì dùng công nghệ phức tạp**. Chỉ thêm khi có vấn đề kiến trúc cụ thể. |
| Multi-exchange (OKX/Bybit) thật                       | Chỉ chứng minh bằng port `MarketDataProvider` + 1 adapter fixture trong test.                     |
| Multi-coin, multi-asset ở MVP                         | Schema đã có `market_pairs`; MVP demo ETHUSDT.                                                    |
| Long/Short, Trailing Stop, Position Sizing nâng cao   | MVP one-net LONG/SHORT + fixed notional `10 USDT`; trailing stop và sizing khác là extension. |
| Mobile app                                            | Dashboard là desktop-first (4 chart cùng lúc).                                                     |
| Hạ tầng production (auto-scaling, multi-region, CDN)  | Chạy Docker Compose 1 node.                                                                       |

### 4.3 Ranh giới quan trọng nhất

> Hệ thống **không** giữ credential sàn giao dịch và **không** đặt lệnh. Binance chỉ được truy cập qua adapter read-only (public market data endpoint).

**Nguồn gốc: [PD] — product safety / scope decision của nhóm.** Đề bài **không** phát biểu ranh giới này thành một câu yêu cầu. Cái đề bài nói là mục tiêu và trọng tâm: *"Trọng tâm của đồ án là Kiến trúc phần mềm, không phải tìm ra strategy đầu tư tốt nhất"* (§2), *"Backtesting nghĩa là giả lập"* (§19), và *"Đồ án không nhằm chứng minh rằng MA + RSI + SMC có thể kiếm tiền thật"* (§47). Không có chỗ nào yêu cầu — cũng không có chỗ nào cấm — việc kết nối tài khoản thật.

Nhóm **chọn** biến điều đó thành một ranh giới cứng, vì hai lý do kiến trúc cụ thể chứ không phải để cho an toàn chung chung:

1. **Attack surface.** Không có API key sàn nghĩa là không có secret nào để rò rỉ, không cần key rotation, không cần vault, không có đường nào từ một lỗi RCE tới thiệt hại tài chính. Đây là cách rẻ nhất để loại một nhóm rủi ro bảo mật khỏi hệ thống — bằng cách không có thứ để mất.
2. **Chống scope creep (R15).** "Thêm chức năng đặt lệnh" là mở rộng nghe hợp lý nhưng kéo theo order state machine, reconciliation với sàn, xử lý partial fill, idempotency của lệnh — tức là một hệ thống thứ hai, và nó sẽ lấy hết thời gian còn lại của phần kiến trúc mà đồ án thực sự được đánh giá.

Vì là **[PD]** chứ không phải **[SRC]**, đây là một quyết định *có thể* xem lại — nhưng xem lại thì phải mở lại cả hai lý do trên và phải là quyết định tường minh, không phải trôi dần vào.

### 4.4 Phân loại nguồn gốc yêu cầu (traceability)

Bảng này để không ai — kể cả nhóm — nhầm điều nhóm tự quyết với điều đề bài yêu cầu. Ba nhãn định nghĩa ở §2.2.

| Nội dung | Nhãn | Căn cứ |
| --- | --- | --- |
| 4 strategy đơn lẻ MA/RSI/Bollinger/SR | **[SRC]** | §37 MVP nói tường minh "ít nhất 4 strategy đơn lẻ, ví dụ: MA, RSI, Bollinger, Support/Resistance" |
| Composite strategy + combination policy | **[SRC]** | §13–§14 |
| Random Search bắt buộc | **[SRC]** | §37 "ít nhất một phương pháp: Random Search" |
| Metrics Return / Win Rate / MDD / Trades | **[SRC]** | §37 |
| Leaderboard Top-K | **[SRC]** | §21–§22, §37 |
| Stop condition cho loop | **[SRC]** | §23 "Không được để `while(true)` chạy vô hạn mà không kiểm soát" |
| Tối đa 4 timeframe, mỗi chart đổi độc lập | **[SRC]** | §5 |
| Chart phải visualize Entry / Stop Loss / Take Profit | **[SRC] + [PD]** | §5 yêu cầu marker; nhóm chọn fixed-percent `risk_policy` và `intrabar_priority` để biến capability đó thành MVP, còn trailing/position sizing là extension |
| Pipeline news `Collect → Store → Analyze sentiment` | **[SRC]** | §37 |
| Strategy có version, không overwrite kết quả cũ | **[SRC]** | §36 |
| Frontend không phụ thuộc payload Binance | **[SRC]** | §4 "Không được để frontend phụ thuộc trực tiếp vào cấu trúc dữ liệu Binance" |
| Event-driven để giảm coupling | **[SRC]** | §34 |
| 5 anti-pattern phải tránh | **[SRC]** | §44 |
| **Simulation-only, không giữ API key sàn** | **[PD]** | §4.3 — suy ra từ §2/§19/§47, không phải câu yêu cầu |
| **Authentication (JWT RS256) + refresh token** | **[PD]** | Đề bài không yêu cầu auth. Nhóm thêm vì cần principal để enforce quota (điều kiện của §32.5) |
| **RBAC 3 role + ownership check** | **[PD]** | Suy ra từ việc §32.7 cần vai trò *theo dõi* và §12 cần vai trò *thêm strategy*; đề bài không định nghĩa role |
| **Quota per-user** (concurrent run, candidate/run, nến/experiment) | **[PD]** | Cơ chế để §32.5 và §43 có nghĩa: không có quota thì "1.000 strategy cần backtest" là một request bất kỳ ai gửi được |
| **Chống SSRF ở news source (allowlist server-side)** | **[PD]** | §27–§28 chỉ yêu cầu provider abstraction. Nhóm thêm allowlist vì cho nhập URL từ browser là một lỗ SSRF thật |
| **Transactional outbox cho event cross-process** | **[PD]** | §34 yêu cầu event-driven nhưng không nói cơ chế delivery. Outbox là lựa chọn của nhóm để event không mất (§5.7) |
| **`code_fingerprint` fail-fast** | **[PD]** | §36 yêu cầu version; fingerprint là cơ chế nhóm chọn để version không chỉ là quy ước (ADR-009) |
| **Không fake dữ liệu khi dependency down** | **[PD]** | ADR-013. Đề bài không nói; nhóm chọn vì nhãn giả đi vào kết quả Leaderboard mà không có triệu chứng |
| **Python Strategy Platform (canonical, float64)** | **[PD]** | Strategy, backtest, evaluation, search, ranking/leaderboard, visualization, news extraction/tagging và sentiment/AI orchestration thuộc backend FastAPI riêng (service `research`, codebase `app/` ở repo root), dùng `float64`; Go giữ realtime market/edge/auth/quota. Đảo ngược ADR-011 — không phải yêu cầu đề bài. Chi tiết `specs/python-research.md` |
| Ngưỡng **p95 < 1.5 s** cho candle → UI | **[NFR]** | §32.3 chỉ nói "độ trễ thấp". Con số là của nhóm |
| Ngưỡng **p95 < 300 ms** cho `GET /candles` | **[NFR]** | Không có căn cứ trong đề bài |
| Ngưỡng **p95 < 500 ms** cho `POST /experiments` | **[NFR]** | Suy ra từ ADR-006 (phải trả nhanh vì async), con số là của nhóm |
| Ngưỡng **≥ 3×** khi scale 1→4 worker | **[NFR]** | §43 yêu cầu scale được; "3×" là ngưỡng nhóm chọn để chứng minh |
| **≥ 0.5 candidate/giây** 1 worker | **[NFR]** | Không có căn cứ trong đề bài |
| **Startup < 120 s** | **[NFR]** | Không có căn cứ trong đề bài |
| Observability: 5 metric + correlation ID + progress panel | **[SRC]** cho *5 câu hỏi*, **[PD]** cho *cách trả lời* | §32.7 liệt kê đúng 5 câu hỏi. Việc trả lời bằng Prometheus metric + correlation ID là lựa chọn của nhóm |

Cách dùng bảng này khi trình bày: với mọi thứ **[SRC]** nhóm chỉ cần chỉ ra nó đã được cài đặt. Với **[PD]** và **[NFR]**, nhóm phải giải thích **vấn đề kiến trúc** mà nó giải quyết — đúng như §38 đòi hỏi cho mọi công nghệ được thêm vào.

## 5. Rủi ro và ràng buộc đã biết

| #   | Rủi ro / Ràng buộc                                                                | Tác động                                                        | Hướng giảm thiểu                                                                                            | Tài liệu                        |
| --- | --------------------------------------------------------------------------------- | --------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- | ------------------------------- |
| R1  | **Binance WebSocket disconnect** (mạng, rate limit, maintenance)                  | Mất nến → chart sai, backtest sai                               | Reconnect exponential backoff (capped) + ghi `last_closed_at` + **backfill REST** khoảng thiếu + de-dup theo `(provider, symbol, timeframe, open_time)` | `specs/market-data.md`          |
| R2  | **Binance REST rate limit** (weight-based, provider-configured; MVP 6000/phút)      | 429/418 → ban IP tạm thời                                       | Token bucket **outbound** theo weight + đọc `X-MBX-USED-WEIGHT-1M` + cache nến đã đóng vào PostgreSQL + không refetch dữ liệu đã có | `specs/market-data.md`          |
| R3  | **Look-ahead bias** trong backtest                                                | Kết quả đẹp giả tạo → toàn bộ Leaderboard vô nghĩa               | **3 tầng**: (a) causal candles; (b) causal `IndicatorView` → `LookAheadError`; (c) event ordering + BBO LIMIT chỉ dùng quote đã đến. Kèm fixture structural test | `design.md` §5.2.1 · `specs/backtest.md` |
| R4  | **Search space nổ tổ hợp** (4 strategy × nhiều param → hàng vạn candidate)        | Chạy vô hạn, đốt CPU, treo hệ thống                             | Stop condition bắt buộc (candidate/duration/no-improvement) + dedup theo `candidate_hash` + quota per-principal | `specs/search-loop.md`          |
| R5  | **Backtest chiếm HTTP request** (10.000 nến × 3 strategy có thể mất > 30 s)        | Timeout, connection pool cạn, UI treo                           | `POST /experiments` trả `202 + run_id` ngay; thực thi qua job record; UI polling/stream tiến trình           | `specs/experiment.md`           |
| R6  | **Kết quả Leaderboard không tái lập được**                                        | Không bảo vệ được đồ án: "+18.2% từ đâu ra?"                    | Snapshot bất biến append-only: strategy version + params + dataset version + fee/slippage + evaluator version | `specs/leaderboard.md`          |
| R7  | **Strategy plugin lỗi làm sập worker** (chia cho 0, index out of range, vòng lặp vô hạn) | Cả search run chết                                        | Trusted Go plugin boundary + context cancellation + worker lease 120 s. Exception/look-ahead → `candidate.status = failed` + `failure_reason`, run tiếp | `specs/strategy-registry.md`    |
| R8  | **News provider chết hoặc trả HTML rác**                                          | Pipeline news dừng                                              | Job news độc lập; failure chỉ ảnh hưởng job đó; chart/backtest technical không phụ thuộc                     | `specs/news.md`                 |
| R9  | **SSRF qua news source** (nếu cho phép nhập URL)                                  | Đọc được metadata service nội bộ / port scan                    | `ApprovedSource` là **server config**, không nhận URL từ browser; allowlist HTTPS origin + chặn private/loopback IP sau mỗi redirect/DNS | `specs/news.md` §Bảo mật        |
| R10 | **Sentiment model đổi version** → kết quả cũ không so được với mới                | Backtest có sentiment mất tính so sánh                          | `model_version` là phần của snapshot; đổi model = dataset mới, không ghi đè kết quả cũ                        | `specs/sentiment.md`            |
| R11 | **Sentiment model down**                                                          | News không có nhãn                                              | Lưu news **không có** sentiment, đánh dấu `unavailable`. **Không** fake `NEUTRAL` (sẽ làm sai strategy)      | `specs/sentiment.md`            |
| R12 | **Duplicate event `BacktestCompleted`**                                           | 1 candidate xuất hiện 2 lần trên Leaderboard                    | Consumer idempotent theo `event_id`; UNIQUE `(backtest_run_id)` trên `evaluations`                            | `specs/leaderboard.md`          |
| R13 | **PostgreSQL down**                                                               | Không ghi được experiment                                       | Readiness fail → API trả 503; **không** báo job "completed" khi chưa ghi được kết quả                       | `design.md` §1.5                |
| R14 | **Frontend chứa business logic** (tính RSI trong React)                           | Vi phạm anti-pattern đề bài; UI và backend lệch kết quả          | Overlay **do backend tính**, trả qua `GET /markets/chart-overlays`; frontend chỉ render                       | `design.md` §7.4, `specs/chart-overlay.md` |
| R15 | **Scope trôi thành trading bot**                                                  | Rủi ro pháp lý + lệch mục tiêu môn học                          | §4.3 là ranh giới nhóm tự đặt và **cố ý giữ cứng**; review scope mỗi phase. Đổi ranh giới này phải là quyết định tường minh, không được trôi dần vào | `proposal.md` §4.3              |
| R16 | **Team 3 người, thời gian giới hạn**                                              | Làm không kịp hoặc over-engineer                                | Phase hoá 7 giai đoạn (`design.md` §12.1), tách khỏi Target Architecture (`design.md` §12.0). Worker bắt buộc từ Phase 3; Redis chỉ vào Phase 6 **nếu** số đo thoả điều kiện | `design.md` §12.0, §12.1 |

> **R6 provenance invariant:** snapshot phải giữ toàn bộ execution assumptions — `fee_bps`, `slippage_bps`, `fill_policy`, `position_policy`, `open_position_at_end`, `risk_policy` — cùng strategy version, dataset content hash và evaluator version.

## 6. Tiêu chí thành công (Success Criteria)

Đồ án được xem là thành công khi **10 demo dưới đây chạy được từ `docker compose up` trên máy sạch**. Mỗi tiêu chí là một bài kiểm tra kiến trúc, không phải một tính năng UI.

| #   | Demo                            | Kịch bản                                                                                                         | Bằng chứng đạt                                                                                                        |
| --- | ------------------------------- | ---------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| S1  | **Multi-timeframe độc lập**     | Mở ETHUSDT với `5m / 15m / 1h / 4h`. Đổi Chart 1 từ `5m → 1h`.                                                   | Chỉ Chart 1 gọi API và re-render. Render counter của Chart 2–4 = 0. Network tab chỉ có 1 request mới.                  |
| S2  | **Realtime latency**            | Chờ nến 1m đóng trên Binance.                                                                                    | UI cập nhật trong **< 1.5 s** (p95 trên 20 lần đo). Log có `CandleClosed` với `correlation_id`.                        |
| S3  | **Thêm strategy (scenario đề bài §41)** | Giảng viên yêu cầu thêm `MACDStrategy` tại chỗ.                                                         | `git diff` cho thấy **1 file Python plugin mới** + **0 dòng sửa** trong BacktestEngine/Evaluator/Controller/UI/schema. MACD xuất hiện trong `GET /strategies` và trong search space ngay sau restart. |
| S4  | **Thay search algorithm (§42)** | Đổi `RandomSearchGenerator` → `DomainGuidedGenerator` qua config.                                                | `git diff` = 1 file generator mới + 1 dòng config. Backtester/Evaluator/Leaderboard **không đổi 1 dòng**.              |
| S5  | **Backtest đúng và tái lập được** | Chạy fixture 200 nến có kết quả tính tay trước.                                                                | Trades, Return, Win Rate, MDD khớp **chính xác** với giá trị kỳ vọng. Chạy lại lần 2 ra **kết quả byte-identical**.    |
| S6  | **Search loop có kiểm soát**    | Start search với `max_candidates=50`. Bấm Pause ở candidate ~20, chờ 10 s, Resume, rồi Cancel.                    | UI hiển thị `tested/queued/failed/best_score/current_candidate/elapsed`. Loop dừng đúng 50 hoặc đúng lúc cancel. Không có `while(true)`. |
| S7  | **Truy nguồn Leaderboard**      | Click Top-1, mở tab Provenance.                                                                                  | Hiển thị `strategy_id@version`, toàn bộ params, `dataset_version`, `from/to`, toàn bộ execution assumptions (`fee_bps`, `slippage_bps`, `fill_policy`, `position_policy`, `open_position_at_end`, `risk_policy`), `evaluator_version`. Sửa param → **version mới**, entry cũ **không bị ghi đè**. |
| S8  | **Cô lập lỗi**                  | `docker stop` service sentiment (hoặc set news provider = URL chết).                                             | Chart realtime **vẫn chạy**. Backtest technical **vẫn chạy**. News hiển thị `sentiment: unavailable`, **không** có nhãn NEUTRAL giả. |
| S9  | **Reconnect + backfill**        | `docker network disconnect` market provider Binance khỏi internet 60 s rồi nối lại.                              | Log có reconnect với backoff. Sau khi nối lại, **0 nến đã đóng bị thiếu** (query `candles` liên tục, không gap).       |
| S10 | **Scale proof**                 | Chạy cùng 1 search run 40 candidate với `WORKER_REPLICAS=1` rồi `=4`.                                             | Thời gian giảm **≥ 3×**. **0 dòng** thay đổi trong API contract, schema, hay experiment snapshot format.               |

Điều kiện chung: `docker compose up` → toàn bộ service healthy + migration xong + seed data sẵn trong **< 120 s**.

## 7. Định nghĩa hoàn thành (Definition of Done)

Đồ án hoàn thành khi cả 3 điều đồng thời đúng:

1. **10 demo S1–S10** ở §6 diễn ra được liên tục trong một lần trình bày, từ trạng thái compose sạch.
2. **Mọi con số hiển thị trên UI** đều truy được về một `experiment_id` bất biến trong PostgreSQL.
3. **Ba câu hỏi kiến trúc** ở §2.3 trả lời được bằng `git diff` thật, không bằng lời giải thích.

## 8. Tác giả

| Thành viên | Phạm vi phụ trách                                                             |
| ---------- | ----------------------------------------------------------------------------- |
| Thành viên A (Lead) | Market Data (Binance adapter, realtime, backfill), Chart Overlay, Web dashboard |
| Thành viên B | Strategy Registry, Composite, Backtest Engine, Evaluator                        |
| Thành viên C | Search Loop, Leaderboard, News + Sentiment, Observability                       |

## 9. Phiên bản

- **v1.3** — 2026-08-12 — Đóng contract read projection bằng schema/view/role/grant DDL; thêm DB guard cho artifact bất biến; version dataset `revision_no` + advisory lock; làm rõ ML integration seam, giới hạn public/internal và cách đếm domain port.
- **v1.2** — 2026-08-12 — Đồng bộ provenance với `risk_policy`; làm rõ SL/TP trigger so với execution fill; thêm virtual composite root cho FK; khóa causal `IndicatorView` và family constraint; xác nhận `requirements.html` là nguồn yêu cầu chính.
- **v1.1** — 2026-08-11 — Phân loại nguồn gốc yêu cầu [SRC]/[PD]/[NFR] (§2.2, §4.4); thêm điều kiện đo cho mọi SLO; ghi rõ simulation-only là product decision của nhóm (§4.3); chốt Worker bắt buộc từ Phase 3 và Redis là tuỳ chọn có điều kiện (§4.1).
- **v1.0** — 2026-08-11 — Bản blueprint đầu cho phần thiết kế kiến trúc.
