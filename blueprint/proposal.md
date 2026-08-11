# Crypto Strategy Lab — Project Proposal

> Phần 1 / Blueprint • Tài liệu đề xuất • Phiên bản 1.0

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

| Chỉ tiêu                                                              | Mục tiêu                                                       |
| --------------------------------------------------------------------- | -------------------------------------------------------------- |
| Số file phải sửa khi thêm `MACDStrategy`                              | **≤ 2 file mới + 0 file core** (registry tự phát hiện)         |
| Số file phải sửa khi đổi Random Search → Domain-Guided Search         | **1 file mới implement `CandidateGenerator`**, 0 file Backtester |
| Số file frontend phải sửa khi thêm `OKXAdapter`                       | **0**                                                          |
| Độ trễ Binance candle → UI (p95)                                      | **< 1.5 s**                                                    |
| Latency `GET /api/v1/markets/candles` (1000 nến, cache hit, p95)      | **< 300 ms**                                                   |
| Latency `POST /api/v1/experiments` trả `run_id` (p95)                 | **< 500 ms** (không chờ backtest xong)                         |
| Throughput backtest 1 worker (10.000 nến 5m, composite 3 strategy)    | **≥ 0.5 candidate/giây**                                       |
| Tăng tốc khi scale 1 → 4 worker                                       | **≥ 3×** (đo bằng cùng một search run)                         |
| Đổi timeframe Chart 1 làm Chart 2/3/4 re-render                        | **0 lần** (đo bằng React Profiler / render counter)            |
| Mất nến khi Binance WebSocket disconnect 60 giây                       | **0 nến đã đóng** (backfill bù đủ)                             |
| Search loop chạy vô hạn                                                | **Không xảy ra** — mọi run có stop condition bắt buộc          |
| Kết quả Leaderboard không truy được nguồn gốc                          | **0 entry** — mọi entry link tới experiment snapshot bất biến  |
| News/Sentiment service down → chart và backtest technical             | **Vẫn chạy 100%**                                              |
| Backtest cùng snapshot chạy 2 lần cho kết quả khác nhau                | **0 ca** (deterministic, cùng seed cùng dataset)               |

### 2.3 Ba câu hỏi kiến trúc quyết định điểm

Toàn bộ blueprint này được tổ chức để trả lời dứt điểm 3 câu:

1. **Thêm strategy mới** → chỉ implement `Strategy` + đăng ký metadata. Không có `if strategy == "MA" ... else if ...` ở bất kỳ đâu. (§7.1, ADR-002)
2. **Thay thuật toán search** → chỉ implement `CandidateGenerator`. Pipeline phía sau chỉ nhận `CandidateStrategy`. (§7.2, ADR-004)
3. **Scale 100 → 100.000 backtest** → cùng một job contract, chuyển từ in-process sang queue + N worker. Không đổi API, không đổi schema. (§7.3, ADR-005)

## 3. Người dùng và nhu cầu

Hệ thống là **nền tảng nghiên cứu**, không phải sàn giao dịch. Người dùng vì thế là người phân tích, không phải người đặt lệnh.

| Vai trò                       | Nhu cầu chính                                                                                                      | Ràng buộc                                                                     |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------- |
| **Researcher** (vai trò chính) | Xem 4 chart multi-timeframe realtime; bật/tắt indicator; chạy backtest; xem Leaderboard; click 1 entry để xem trade và tín hiệu trên chart | Dùng desktop browser; cần thấy tiến trình search chứ không chỉ kết quả cuối |
| **Strategy Developer**        | Thêm strategy mới bằng cách viết 1 class; khai báo parameter schema; strategy tự xuất hiện trong UI                | Không được đụng vào core engine; strategy phải test được offline không cần DB/HTTP |
| **Operator**                  | Biết loop đang chạy hay dừng, đã thử bao nhiêu candidate, bao nhiêu job lỗi, Top-1 hiện tại; pause/resume/cancel run | Chỉ có UI + log + metrics; không SSH vào container để đoán               |
| **Giảng viên / Reviewer**     | Kiểm tra khả năng mở rộng bằng scenario trực tiếp ("thêm MACD đi"); truy nguồn 1 con số trên Leaderboard           | Đánh giá kiến trúc qua diff code và tài liệu, không qua lợi nhuận strategy    |

Phân vai trò này là lý do có **RBAC 3 role** (§6) chứ không phải hệ thống một-người-dùng: `Operator` được pause search run của người khác, `Researcher` chỉ thao tác trên experiment của mình.

## 4. Phạm vi

### 4.1 Trong phạm vi (In scope)

**Market & Chart**

- Binance adapter: REST historical klines + WebSocket realtime kline stream.
- Chuẩn hoá về `Candle` nội bộ; frontend **không bao giờ** thấy payload Binance.
- Dashboard 4 panel độc lập; mỗi panel có `(symbol, timeframe)` riêng, subscription riêng.
- Overlay: candlestick, volume, MA, Bollinger Bands, Support/Resistance zone, Buy/Sell signal; entry/exit/SL/TP marker khi chọn một experiment result.

**Strategy & Combination**

- Strategy registry theo Plugin Architecture; ≥ 4 strategy đơn lẻ: `MAStrategy`, `RSIStrategy`, `BollingerStrategy`, `SupportResistanceStrategy`.
- `NewsSentimentStrategy` là strategy thứ 5, dùng đúng contract — chứng minh kiến trúc không giới hạn ở Technical Analysis.
- Composite strategy với ≥ 2 combination policy: `majority_vote` và `weighted_vote` (policy lưu trong snapshot, không hard-code).

**Experiment & Search**

- `ExperimentSnapshot` bất biến: candidate definition + dataset version + execution assumptions (fee, slippage, fill policy) + evaluator version.
- Backtest engine chronological, fill ở `next_candle_open`, không look-ahead.
- Evaluator tách khỏi backtester: Total Return, Win Rate, Max Drawdown, Number of Trades, Profit Factor, Sharpe Ratio.
- `RandomSearchGenerator` (bắt buộc) + `DomainGuidedGenerator` (chứng minh replaceability, dùng phân nhóm Trend/Momentum/Volatility/Structure/Information).
- Search run có **stop condition bắt buộc**: max candidate / max duration / max non-improving; hỗ trợ pause/resume/cancel idempotent.
- Leaderboard Top-K với scoring policy có version.

**News & Sentiment**

- News provider adapter (RSS + News API) trả về `NewsItem` chuẩn hoá; crawler **không** biết gì về ML.
- Sentiment service riêng (FastAPI hiện có): `POSITIVE | NEUTRAL | NEGATIVE` + score + `model_version`.

**Nền tảng & Vận hành**

- 3 deployable đã có: Next.js web, Go API, Python service. Thêm PostgreSQL. Thêm Redis + worker **chỉ ở Phase 6** khi có số đo chứng minh cần.
- Job queue cho backtest (bắt đầu bằng bảng `backtest_jobs` trong PostgreSQL + `SELECT ... FOR UPDATE SKIP LOCKED`, không cần broker).
- Observability: structured log + `/metrics` Prometheus + UI progress panel.
- `docker compose up` chạy toàn bộ stack có seed data.

### 4.2 Ngoài phạm vi (Out of scope)

| Không làm                                             | Lý do                                                                                            |
| ----------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| **Giao dịch tiền thật, đặt lệnh, lưu API key sàn**    | Ranh giới **không thương lượng**: hệ thống là simulation-only. Không có custody, không có order. |
| Tư vấn đầu tư / khuyến nghị mua bán                   | Không phải mục tiêu đồ án; mọi output là kết quả mô phỏng.                                       |
| Genetic Algorithm, Bayesian Optimization, RL, LLM-generated strategy | Phần mở rộng của đề bài. Kiến trúc *cho phép* cắm vào (`CandidateGenerator`) nhưng không implement. |
| SMC, Wyckoff đầy đủ                                   | Đề bài không bắt buộc. Chỉ cần chứng minh kiến trúc admit được — có `strategy family: structure` sẵn. |
| Kafka, RabbitMQ, CQRS, Event Sourcing, microservice per module | Đề bài nói rõ: **không cộng điểm vì dùng công nghệ phức tạp**. Chỉ thêm khi có vấn đề kiến trúc cụ thể. |
| Multi-exchange (OKX/Bybit) thật                       | Chỉ chứng minh bằng port `MarketDataProvider` + 1 adapter fixture trong test.                     |
| Multi-coin, multi-asset ở MVP                         | Schema đã có `market_pairs`; MVP demo BTCUSDT.                                                    |
| Long/Short, Trailing Stop, Position Sizing nâng cao   | MVP `long_only`; `position_policy` là field trong snapshot nên mở rộng được.                      |
| Mobile app                                            | Dashboard là desktop-first (4 chart cùng lúc).                                                     |
| Hạ tầng production (auto-scaling, multi-region, CDN)  | Chạy Docker Compose 1 node.                                                                       |

### 4.3 Ranh giới quan trọng nhất

> Hệ thống **không** giữ credential sàn giao dịch và **không** đặt lệnh. Binance chỉ được truy cập qua adapter read-only (public market data endpoint). Đây là quyết định về attack surface, không chỉ về scope: không có API key nghĩa là không có gì để rò rỉ.

## 5. Rủi ro và ràng buộc đã biết

| #   | Rủi ro / Ràng buộc                                                                | Tác động                                                        | Hướng giảm thiểu                                                                                            | Tài liệu                        |
| --- | --------------------------------------------------------------------------------- | --------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- | ------------------------------- |
| R1  | **Binance WebSocket disconnect** (mạng, rate limit, maintenance)                  | Mất nến → chart sai, backtest sai                               | Reconnect exponential backoff (capped) + ghi `last_closed_at` + **backfill REST** khoảng thiếu + de-dup theo `(provider, symbol, timeframe, close_time)` | `specs/market-data.md`          |
| R2  | **Binance REST rate limit** (weight-based, 1200/phút)                             | 429/418 → ban IP tạm thời                                       | Token bucket **outbound** theo weight + cache nến đã đóng vào PostgreSQL + không refetch dữ liệu đã có       | `specs/market-data.md`          |
| R3  | **Look-ahead bias** trong backtest                                                | Kết quả đẹp giả tạo → toàn bộ Leaderboard vô nghĩa               | Fill ở `next_candle_open`; indicator chỉ đọc nến `≤ t`; fixture test có kết quả kỳ vọng tính bằng tay        | `specs/backtest.md`             |
| R4  | **Search space nổ tổ hợp** (4 strategy × nhiều param → hàng vạn candidate)        | Chạy vô hạn, đốt CPU, treo hệ thống                             | Stop condition bắt buộc (candidate/duration/no-improvement) + dedup theo `candidate_hash` + quota per-principal | `specs/search-loop.md`          |
| R5  | **Backtest chiếm HTTP request** (10.000 nến × 3 strategy có thể mất > 30 s)        | Timeout, connection pool cạn, UI treo                           | `POST /experiments` trả `202 + run_id` ngay; thực thi qua job record; UI polling/stream tiến trình           | `specs/experiment.md`           |
| R6  | **Kết quả Leaderboard không tái lập được**                                        | Không bảo vệ được đồ án: "+18.2% từ đâu ra?"                    | Snapshot bất biến append-only: strategy version + params + dataset version + fee/slippage + evaluator version | `specs/leaderboard.md`          |
| R7  | **Strategy plugin lỗi làm sập worker** (chia cho 0, index out of range, vòng lặp vô hạn) | Cả search run chết                                        | Strategy chạy trong sandbox có timeout; exception → `candidate.status = failed` + `failure_reason`, run tiếp | `specs/strategy-registry.md`    |
| R8  | **News provider chết hoặc trả HTML rác**                                          | Pipeline news dừng                                              | Job news độc lập; failure chỉ ảnh hưởng job đó; chart/backtest technical không phụ thuộc                     | `specs/news.md`                 |
| R9  | **SSRF qua news source** (nếu cho phép nhập URL)                                  | Đọc được metadata service nội bộ / port scan                    | `ApprovedNewsSource` là **server config**, không nhận URL từ browser; allowlist HTTPS origin + chặn private/loopback IP sau mỗi redirect/DNS | `specs/news.md` §Bảo mật        |
| R10 | **Sentiment model đổi version** → kết quả cũ không so được với mới                | Backtest có sentiment mất tính so sánh                          | `model_version` là phần của snapshot; đổi model = dataset mới, không ghi đè kết quả cũ                        | `specs/sentiment.md`            |
| R11 | **Sentiment model down**                                                          | News không có nhãn                                              | Lưu news **không có** sentiment, đánh dấu `unavailable`. **Không** fake `NEUTRAL` (sẽ làm sai strategy)      | `specs/sentiment.md`            |
| R12 | **Duplicate event `BacktestCompleted`**                                           | 1 candidate xuất hiện 2 lần trên Leaderboard                    | Consumer idempotent theo `event_id`; UNIQUE `(backtest_run_id)` trên `evaluations`                            | `specs/leaderboard.md`          |
| R13 | **PostgreSQL down**                                                               | Không ghi được experiment                                       | Readiness fail → API trả 503; **không** báo job "completed" khi chưa ghi được kết quả                       | `design.md` §1.4                |
| R14 | **Frontend chứa business logic** (tính RSI trong React)                           | Vi phạm anti-pattern đề bài; UI và backend lệch kết quả          | Overlay **do backend tính**, trả qua `GET /markets/chart-overlays`; frontend chỉ render                       | `design.md` §7.4, `specs/chart-overlay.md` |
| R15 | **Scope trôi thành trading bot**                                                  | Rủi ro pháp lý + lệch mục tiêu môn học                          | §4.3 là ranh giới không thương lượng; review scope mỗi phase                                                 | `proposal.md` §4.3              |
| R16 | **Team 3 người, thời gian giới hạn**                                              | Làm không kịp hoặc over-engineer                                | Phase hoá 7 giai đoạn (§`design.md` §10); Redis/queue/worker chỉ vào Phase 6 khi có số đo                     | `design.md` §10                 |

## 6. Tiêu chí thành công (Success Criteria)

Đồ án được xem là thành công khi **9 demo dưới đây chạy được từ `docker compose up` trên máy sạch**. Mỗi tiêu chí là một bài kiểm tra kiến trúc, không phải một tính năng UI.

| #   | Demo                            | Kịch bản                                                                                                         | Bằng chứng đạt                                                                                                        |
| --- | ------------------------------- | ---------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| S1  | **Multi-timeframe độc lập**     | Mở BTCUSDT với `5m / 15m / 1h / 4h`. Đổi Chart 1 từ `5m → 1h`.                                                   | Chỉ Chart 1 gọi API và re-render. Render counter của Chart 2–4 = 0. Network tab chỉ có 1 request mới.                  |
| S2  | **Realtime latency**            | Chờ nến 1m đóng trên Binance.                                                                                    | UI cập nhật trong **< 1.5 s** (p95 trên 20 lần đo). Log có `CandleClosed` với `correlation_id`.                        |
| S3  | **Thêm strategy (scenario đề bài §41)** | Giảng viên yêu cầu thêm `MACDStrategy` tại chỗ.                                                         | `git diff` cho thấy **1 file mới** + **0 dòng sửa** trong backtester/evaluator/controller/UI/schema. MACD xuất hiện trong `GET /strategies` và trong search space ngay sau restart. |
| S4  | **Thay search algorithm (§42)** | Đổi `RandomSearchGenerator` → `DomainGuidedGenerator` qua config.                                                | `git diff` = 1 file generator mới + 1 dòng config. Backtester/Evaluator/Leaderboard **không đổi 1 dòng**.              |
| S5  | **Backtest đúng và tái lập được** | Chạy fixture 200 nến có kết quả tính tay trước.                                                                | Trades, Return, Win Rate, MDD khớp **chính xác** với giá trị kỳ vọng. Chạy lại lần 2 ra **kết quả byte-identical**.    |
| S6  | **Search loop có kiểm soát**    | Start search với `max_candidates=50`. Bấm Pause ở candidate ~20, chờ 10 s, Resume, rồi Cancel.                    | UI hiển thị `tested/queued/failed/best_score/current_candidate/elapsed`. Loop dừng đúng 50 hoặc đúng lúc cancel. Không có `while(true)`. |
| S7  | **Truy nguồn Leaderboard**      | Click Top-1, mở tab Provenance.                                                                                  | Hiển thị `strategy_id@version`, toàn bộ params, `dataset_version`, `from/to`, `fee_bps`, `slippage_bps`, `fill_policy`, `evaluator_version`. Sửa param → **version mới**, entry cũ **không bị ghi đè**. |
| S8  | **Cô lập lỗi**                  | `docker stop` service sentiment (hoặc set news provider = URL chết).                                             | Chart realtime **vẫn chạy**. Backtest technical **vẫn chạy**. News hiển thị `sentiment: unavailable`, **không** có nhãn NEUTRAL giả. |
| S9  | **Reconnect + backfill**        | `docker network disconnect` service Python khỏi internet 60 s rồi nối lại.                                        | Log có reconnect với backoff. Sau khi nối lại, **0 nến đã đóng bị thiếu** (query `candles` liên tục, không gap).       |
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

- **v1.0** — 2026-08-11 — Bản blueprint đầu cho phần thiết kế kiến trúc.
