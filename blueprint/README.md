# Crypto Strategy Lab — Blueprint

Tài liệu thiết kế kiến trúc cho đồ án cuối kỳ môn Thiết kế Phần mềm (TKPM), HCMUS.

**Chủ đề**: Nền tảng phân tích, kết hợp và đánh giá chiến lược giao dịch Crypto.

**Cập nhật kiến trúc 2026-08-14**: Marketdata, Strategy, Backtest, Evaluation và
DB contract đã được reconciled. Blueprint này giữ yêu cầu sản phẩm, thiết kế và
contract ở mức product; execution detail của bốn domain nằm trong bộ tài liệu
kiến trúc sibling: [`README.md`](../../architecture/README.md),
[`blueprint-verification.md`](../../architecture/blueprint-verification.md) và
[`domain-backend.md`](../../architecture/domain-backend.md). Đọc chúng cùng nhau;
khi cần một rule thực thi cụ thể, resolution trong `blueprint-verification.md`
và contract trong `domain-backend.md` là canonical. Không ghi nhận PnL fixture
trước khi engine/evaluator thực sự tồn tại.

**Ranh giới của nhóm** *(product safety / scope decision — không phải câu trích từ đề bài)*: hệ thống là **simulation-only**. Nó không đặt lệnh, không giữ credential sàn giao dịch, không đưa ra khuyến nghị đầu tư. Binance chỉ được truy cập qua adapter read-only trên public market data endpoint. Đề bài nói trọng tâm là kiến trúc và backtest là *giả lập* (§2, §19, §47) nhưng không phát biểu ranh giới này thành yêu cầu — nhóm chọn biến nó thành ranh giới cứng để loại attack surface (không có API key thì không có gì để rò rỉ) và chống scope creep. Lập luận đầy đủ ở `proposal.md` §4.3; phân loại nguồn gốc mọi yêu cầu khác ở `proposal.md` §4.4.

## Cấu trúc thư mục

```
blueprint/
├── README.md                      # File này — index + mapping yêu cầu
├── proposal.md                    # Bối cảnh, mục tiêu định lượng, phạm vi, rủi ro, tiêu chí thành công
├── design.md                      # Tài liệu trung tâm: 13 section
├── assets/                        # Sơ đồ render sẵn — đọc offline / export PDF được
│   ├── README.md                  # Danh mục 19 sơ đồ + cách render lại
│   ├── diagrams/                  # Mermaid source (.mmd) + SVG vector
│   └── diagrams-png/              # PNG 2× cho Word/PowerPoint
├── scripts/
│   └── extract_diagrams.py        # Trích .mmd từ Markdown (Markdown là nguồn sự thật)
├── go-review-checklist.md         # Checklist handoff cho team Go
└── specs/
    ├── market-data.md             # Binance adapter, realtime, reconnect + backfill
    ├── chart-overlay.md           # Overlay live, subscription per panel, multi-timeframe
    ├── strategy-registry.md       # Plugin Architecture — lõi khả năng mở rộng
    ├── composite-strategy.md      # Kết hợp tín hiệu, combination policy
    ├── experiment.md              # ExperimentSnapshot bất biến, job queue, lease token
    ├── backtest.md                # Backtest engine, fill policy, chống look-ahead
    ├── evaluation.md              # Metrics dẫn xuất, tách khỏi trade facts
    ├── search-loop.md             # Continuous loop, stop condition, pause/resume
    ├── leaderboard.md             # Top-K, scoring policy, provenance
    ├── visualization.md           # Overlay của kết quả, trade table, equity curve
    ├── news.md                    # News collector, provider abstraction, chống SSRF
    ├── sentiment.md               # Sentiment analysis, model version, sentiment-as-strategy
    ├── auth.md                    # JWT RS256, RBAC 3 role, ownership, Defense in Depth
    └── observability.md           # Metrics, correlation ID, structured log, progress panel
```

**Canonical implementation handoff (sibling package)**: parity và execution
contract không được copy thành một cây `blueprint/verification/` thứ hai. Dùng
`../../architecture/README.md`, `../../architecture/blueprint-verification.md`
và `../../architecture/domain-backend.md`; backlog giữ task/AC, còn architecture
giữ chi tiết triển khai, lifecycle và evidence protocol.

## Sơ đồ render sẵn

Mọi sơ đồ trong tài liệu đều có **bản render sẵn** ở `assets/diagrams/*.svg` (vector) và `assets/diagrams-png/*.png` (2×). Không có URL ảnh ngoài — mở tài liệu offline hoặc export PDF thì sơ đồ vẫn hiển thị đầy đủ.

Bảy góc nhìn kiến trúc bắt buộc đều có sơ đồ tương ứng:

| Góc nhìn bắt buộc | Sơ đồ | Section |
| ----------------- | ----- | ------- |
| System Context | `01-c4-l1-system-context` | `design.md` §2.1 |
| Container / HLA | `02-c4-l2-container`, `04-high-level-architecture` | §2.2, §3 |
| Component responsibilities | `03-c4-l3-component-strategy-lab` | §2.3 |
| ERD | `06-erd` | §4.3 |
| Data Flow | `05-candle-path-binance-to-pixel`, `07-outbox-scenarios`, `13-news-sentiment-flow` | §3.2, §5.7.5, §6.4 |
| Realtime / Reconnect Flow | `09-realtime-reconnect-backfill-flow` | §6.1 |
| Strategy Flow | `10-strategy-flow` | §6.2 |
| Search / Backtest Flow | `11-search-backtest-flow`, `15-job-queue-scale`, `17`–`19` | §6.3, §8.3, `specs/experiment.md` |

Danh mục đầy đủ 19 sơ đồ và hướng dẫn render lại: **`assets/README.md`**.

## Cách đọc

1. **`proposal.md`** — đọc trước. Vấn đề kiến trúc là gì, mục tiêu định lượng nào, phạm vi ở đâu, 10 tiêu chí thành công S1–S10.
2. **`design.md`** — tài liệu trung tâm. 13 section:

   | §   | Nội dung                                       |
   | --- | ---------------------------------------------- |
   | 1   | Kiến trúc tổng thể: architectural style theo từng process, **Service Boundary & Ownership** (Go/Python), read projection, artifact vs workload, hành vi khi sự cố |
   | 2   | C4 Diagram — Level 1 (Context), Level 2 (Container), Level 3 (Component) |
   | 3   | High-Level Architecture + 6 điểm tích hợp      |
   | 4   | Thiết kế cơ sở dữ liệu (DDL đầy đủ + ERD + đường provenance) |
   | 5   | Domain contract (7 domain port + `JobDispatcher` seam) + Event vocabulary (15 event) + **transactional outbox** (§5.7) + **`POST /internal/events`** (§5.8) |
   | 6   | 4 luồng nghiệp vụ: Realtime, Strategy, Search/Backtest, News/Sentiment |
   | 7   | Kiểm soát truy cập: RBAC + ownership, Defense in Depth 4 lớp |
   | 8   | 4 cơ chế bảo vệ: Plugin Registry, Quota/Rate limit, Job Queue (+ **lease token** §8.3.1), Observability |
   | 9   | 5 anti-pattern đề bài + 3 bổ sung, kèm test kiểm chứng |
   | 10  | **17 ADR**                                     |
   | 11  | **Trả lời 8 câu hỏi kiến trúc trung tâm**      |
   | 12  | **Target Architecture vs Delivery Roadmap** (§12.0) + 7 phase + Demo script 18 bước + Truy vết yêu cầu |
   | 13  | Phụ lục: cấu trúc thư mục source code          |

3. **`specs/*.md`** — đặc tả chi tiết từng tính năng. Mỗi file có cấu trúc thống nhất:
   - **Mô tả** — tính năng làm gì + các invariant phải đảm bảo
   - **Contract** — Protocol / dataclass / JSON payload
   - **Luồng chính** — sequence diagram hoặc numbered steps
   - **Kịch bản lỗi** — bảng tình huống → phản ứng (12–18 dòng, gồm race condition)
   - **Ràng buộc** — tính đúng đắn / hiệu năng / bảo mật / mở rộng / quan sát được, có số cụ thể
   - **Tiêu chí chấp nhận** — checklist AC kiểm chứng được

4. **Bộ architecture sibling** —
   [`../../architecture/README.md`](../../architecture/README.md) mô tả topology
   và boundary; [`../../architecture/blueprint-verification.md`](../../architecture/blueprint-verification.md)
   chốt các reconciliation; [`../../architecture/domain-backend.md`](../../architecture/domain-backend.md)
   là execution standard cho marketdata/strategy/backtest/evaluation.
5. **Fixture/evidence** — dữ liệu fixture và acceptance protocol chỉ được công bố
   cùng implementation thật. Không đưa số PnL hoặc result hash suy đoán vào
   Blueprint; M2-03 trong backlog là nơi theo dõi deliverable này.

## Ba câu hỏi kiến trúc quyết định

Toàn bộ blueprint được tổ chức để trả lời dứt điểm 3 câu, **bằng `git diff` thật, không bằng lời giải thích**:

| Câu hỏi                          | Trả lời                                                     | Tài liệu                                          |
| -------------------------------- | ----------------------------------------------------------- | ------------------------------------------------- |
| Thêm strategy mới?               | **1 file mới, 0 dòng sửa core**                             | `design.md` §8.1, §11.1 · `specs/strategy-registry.md` |
| Thay thuật toán search?          | **1 file generator mới + 1 dòng config**                    | `design.md` §11.2 · `specs/search-loop.md`        |
| Scale 100 → 100.000 backtest?    | **`--scale worker=N`, 0 dòng code**                         | `design.md` §8.3, §11.4 · `specs/experiment.md`   |

## Mapping yêu cầu đề bài → tài liệu

### Deliverables (đề bài §45)

| Deliverable                        | Tài liệu                                                          |
| ---------------------------------- | ----------------------------------------------------------------- |
| 1. Source Code                     | `design.md` §13 (cấu trúc thư mục đề xuất)                        |
| 2. README (Install/Run/Architecture/Demo) | `README.md` gốc repo + `design.md` §12.2                   |
| 3. Architecture Document           | `design.md` §1–§8 (System Context, Container, Component, Data Flow, Realtime Flow, Strategy Flow, Search/Backtest Flow) |
| 4. Architectural Decisions         | `design.md` §10 — **17 ADR**                                      |
| 5. Demo                            | `design.md` §12.2 — 18 bước                                       |

### Module chức năng

| Module đề bài                          | Tài liệu chính                                  |
| -------------------------------------- | ----------------------------------------------- |
| §4 Module 1 — Realtime Market Data     | `specs/market-data.md` · `design.md` §6.1       |
| §5 Module 2 — Multi-Timeframe Chart    | `specs/chart-overlay.md` · `design.md` §3.3     |
| §6–§11 Module 3 — Strategy Engine      | `specs/strategy-registry.md` · `design.md` §6.2 |
| §12 Module 4 — Strategy Plugin         | `specs/strategy-registry.md` · `design.md` §8.1 |
| §13–§14 Module 5 — Composite Strategy  | `specs/composite-strategy.md` · `design.md` §5.4 |
| §15–§18 Module 6 — Strategy Search     | `specs/search-loop.md` · `design.md` §6.3       |
| §19–§20 Module 7 — Backtesting Engine  | `specs/backtest.md` · `specs/evaluation.md`     |
| §21–§22 Module 8 — Leaderboard, Top-K  | `specs/leaderboard.md` · `design.md` §4.1       |
| §23–§24 Module 9 — Continuous Loop     | `specs/search-loop.md`                          |
| §25–§26 Visualization, Trade Detail    | `specs/visualization.md`                        |
| §27–§28 Module 10 — News Crawler       | `specs/news.md`                                 |
| §29–§30 Module 11 — Sentiment Analysis | `specs/sentiment.md`                            |
| §35 Database                           | `design.md` §4.1, §4.2                          |
| §36 Strategy Version, Reproducibility  | `design.md` §4.2, ADR-009 · `specs/experiment.md` |

### Architectural drivers (đề bài §32)

| Driver              | Cơ chế thiết kế                                      | Tài liệu                     | Demo |
| ------------------- | ---------------------------------------------------- | ---------------------------- | ---- |
| §32.1 Modifiability | Plugin Registry + auto-discovery + metadata khai báo | `design.md` §8.1, ADR-002    | S3   |
| §32.2 Scalability   | Job Queue với contract cố định; scale = đổi replica  | `design.md` §8.3, ADR-005, ADR-015 | S10  |
| §32.3 Realtime      | Backend-mediated WebSocket + subscription per panel; `POST /internal/events` | `design.md` §6.1, §5.8, ADR-001, ADR-016 | S2   |
| §32.4 Reliability   | Reconnect + backfill; cô lập lỗi từng module; outbox không mất event; lease token | `design.md` §1.5, §5.7, §6.1, §8.3.1 | S8, S9 |
| §32.5 Performance   | `FOR UPDATE SKIP LOCKED` + N worker + bounded input  | `design.md` §8.3, §8.3.1, ADR-014 | S10  |
| §32.6 Maintainability | Ownership rõ ràng (§1.2) + 7 domain port + `JobDispatcher` seam + Dependency Inversion | `design.md` §1.2, §5.1, ADR-004 | S4   |
| §32.7 Observability | Metric theo domain + correlation ID + progress panel | `design.md` §8.4 · `specs/observability.md` | S6 |

### Scenario đánh giá và 8 câu hỏi

| Yêu cầu                              | Tài liệu                          | Demo |
| ------------------------------------ | --------------------------------- | ---- |
| §40 — 8 câu hỏi kiến trúc trung tâm  | **`design.md` §11** (đầy đủ 8 câu) | S3, S4, S8, S9, S10 |
| §41 — Scenario thêm MACD             | `design.md` §8.1, §11.1           | S3   |
| §42 — Scenario đổi Generator         | `design.md` §11.2                 | S4   |
| §43 — Scenario scalability           | `design.md` §8.3, §11.4           | S10  |
| §44 — 5 anti-pattern cần tránh       | **`design.md` §9** (+ 3 bổ sung, kèm test CI) | CI test |

## Mapping vấn đề kỹ thuật → giải pháp

| Vấn đề                                             | Giải pháp                                                              | Tài liệu                     |
| -------------------------------------------------- | ---------------------------------------------------------------------- | ---------------------------- |
| Thêm strategy phải sửa 20 module                   | Go `StrategyRegistry` + plugin self-registration                       | `specs/strategy-registry.md` |
| Hard-coded `if MA && RSI ...`                      | Composite là **dữ liệu JSON**, policy lưu trong snapshot               | `specs/composite-strategy.md` |
| Frontend phụ thuộc payload Binance                 | Adapter chuẩn hoá về `Candle`; frontend không thấy field Binance        | `specs/market-data.md`       |
| Frontend tính RSI (2 nguồn chân lý)                | Overlay **do backend tính**, frontend chỉ render                       | `specs/chart-overlay.md`     |
| Mất nến khi WebSocket disconnect                   | `last_closed_at` trong DB + backfill REST + de-dup bằng PK             | `specs/market-data.md`       |
| Binance ban IP do vượt rate limit                  | Outbound token bucket theo **weight** + hiệu chỉnh từ response header  | `specs/market-data.md`       |
| Look-ahead bias làm Leaderboard vô nghĩa           | 3 tầng: causal candles · `IndicatorView` · BBO event ordering + LIMIT crossing | `design.md` §5.2.1, ADR-007 · `specs/backtest.md` |
| SL/TP: MVP hay extension? Nến chạm cả hai thì sao?  | SL/TP cố định theo % **là MVP** (chart phải vẽ được); intrabar giải bằng `intrabar_priority` mặc định `stop_loss_first` (conservative) | `design.md` ADR-017 · `specs/backtest.md` §C1 |
| Backtest chiếm HTTP request 40 giây                | `POST /experiments` → `202 + run_id`, luôn async (không có fast path)   | `specs/experiment.md`, ADR-006 |
| Search loop chạy vô hạn                            | Stop condition bắt buộc ở **3 lớp**: schema `CHECK`, API, runtime       | `specs/search-loop.md`       |
| Search space nổ tổ hợp                             | Dedup `candidate_hash` + quota `max_candidates_per_run`                | `specs/search-loop.md`       |
| Worker chết giữa job → job treo                    | `lease_token` + `lease_expires_at` + heartbeat 30 s + `attempt`/`max_attempts`; UPSERT tiếp quản run mồ côi | `design.md` §8.3.1, `specs/experiment.md` |
| Worker cũ (lease đã mất) ghi đè kết quả worker mới | Mọi UPDATE guard bằng `AND lease_token = $token` → khớp 0 row → worker cũ tự dừng | `design.md` §8.3.1 |
| Event từ Worker mất vì in-process dispatcher       | **Transactional outbox**: state + event cùng transaction; dispatcher claim/retry; consumer idempotent | `design.md` §5.7 |
| Go WS Hub down → mất frame realtime                | `POST /internal/events` best-effort + retry/backoff + circuit breaker; state đã persist nên client refetch theo `seq` | `design.md` §5.8, ADR-016 |
| Ownership DB chồng chéo giữa Go và Python          | Go sở hữu domain write + migration; Python AI không có quyền DB | `design.md` §1.2.4, §1.2.5 |
| Duplicate event tạo entry trùng                    | `event_consumptions` + `UNIQUE (backtest_run_id, evaluator_version)`   | `specs/leaderboard.md`       |
| Kết quả Leaderboard không truy nguồn được          | Snapshot append-only 6 bảng + `code_fingerprint` + `content_hash`      | `specs/leaderboard.md`, ADR-009, ADR-012 |
| Strategy plugin lỗi giết cả worker                 | Trusted Go plugin boundary + context cancellation + lease 120 s      | `specs/strategy-registry.md` |
| Plugin đọc `indicators[t+1]` (look-ahead ẩn)        | `IndicatorView` causal — chặn `[t+1]`, `[-1]`, `len()`, `slice`         | `design.md` §5.2.1           |
| Đổi công thức score phải chạy lại backtest         | Tách trade facts (thô) khỏi metrics (dẫn xuất)                         | `specs/evaluation.md`        |
| SSRF qua news source                               | `ApprovedSource` là **server config**; validate sau mỗi redirect/DNS | `specs/news.md`              |
| Crawler phụ thuộc chặt vào ML                      | `NewsCollected` event; crawler không import model; test static ở CI    | `specs/news.md`              |
| Sentiment model down → nhãn giả                    | **Không insert row**; `sentiment: null` + `unavailable`. Không fake NEUTRAL | `specs/sentiment.md`, ADR-013 |
| Đổi model sentiment mất khả năng so sánh           | `model_version` là phần của UNIQUE key và của provenance               | `specs/sentiment.md`         |
| CORS echo Origin (lỗ hổng trong code hiện tại)     | Allowlist tường minh từ `CORS_ALLOWED_ORIGINS`                         | `specs/auth.md`, `design.md` §13.2 |
| Không biết search loop đang chạy hay treo          | 5 metric trả lời 5 câu hỏi §32.7 + progress panel                      | `specs/observability.md`     |

## Nguyên tắc thiết kế xuyên suốt

Năm nguyên tắc được áp dụng nhất quán trong toàn bộ blueprint, đáng đọc trước khi đi vào chi tiết:

1. **Ranh giới được thực thi bằng cấu trúc, không bằng quy ước.** `AnalysisContext` không có DB session — nên strategy *không thể* query SQL, không phải *không nên*. `stop_conditions` có DB `CHECK` — nên search run vô hạn *không INSERT được*. Go không có `GRANT` trên bảng domain — nên nó *không thể* ghi, không phải *không nên*. Mọi ràng buộc quan trọng đều có một test tự động hoặc một constraint DB đứng sau; quy ước chỉ nằm trong code review sẽ bị vi phạm sau vài tuần.

2. **Không fake dữ liệu khi dependency down.** Sentiment không khả dụng → `null` + `unavailable`, không phải `NEUTRAL`. Feed stale → `is_stale=true` + `last_closed_at`, không phải im lặng hiển thị nến cũ. Biến "không biết" thành "biết một giá trị cụ thể" là loại lỗi đi vào tới kết quả cuối cùng mà không có triệu chứng để debug. (ADR-013)

3. **Chỉ thêm công nghệ khi có vấn đề kiến trúc cụ thể.** Đề bài nói rõ không cộng điểm cho công nghệ phức tạp. Vì vậy: PostgreSQL làm queue thay vì RabbitMQ (và nêu điều kiện đo được để đổi); Redis là **tuỳ chọn có điều kiện**, chỉ thêm nếu benchmark ở Phase 6 thoả điều kiện tại `design.md` §12.0; không Kafka, không CQRS ở write path, không microservice per module. Mỗi lựa chọn có ADR nêu vấn đề nó giải quyết và điều kiện thay thế. Phân biệt quan trọng: **Backtest Worker không thuộc nhóm "tuỳ chọn"** — nó là kiến trúc bắt buộc (ADR-006, vì `POST /experiments` luôn async) và có từ Phase 3 với 1 replica.

4. **Reproducibility đứng trước tối ưu hoá.** Ghi đủ provenance (strategy version + params + dataset hash + fee/slippage + evaluator version) trước khi làm scoring phức tạp hay search thông minh. Một kết quả không giải thích được thì không có giá trị dù nó cao bao nhiêu. (ADR-007)

5. **Trung thực về nguồn gốc của từng yêu cầu.** Mỗi yêu cầu được gắn nhãn **[SRC]** (đề bài nói tường minh), **[PD]** (nhóm tự quyết cho sản phẩm), hoặc **[NFR]** (ngưỡng nhóm tự đặt để có cái đo) — bảng đầy đủ ở `proposal.md` §4.4. Nói "đề bài yêu cầu p95 < 1.5 s" là sai: đề bài chỉ nói "độ trễ thấp". Với **[SRC]** nhóm chỉ cần chứng minh đã cài đặt; với **[PD]** và **[NFR]** nhóm phải giải thích vấn đề kiến trúc mà nó giải quyết.

## Phiên bản

- **v1.3** — 2026-08-12 — Đóng contract read projection bằng schema/view/role/grant DDL; thêm DB guard cho artifact bất biến; version dataset `revision_no` + advisory lock; làm rõ ML integration seam, giới hạn public/internal và cách đếm domain port.
- **v1.2** — 2026-08-12 — Đồng bộ provenance với `risk_policy`; làm rõ SL/TP trigger so với execution fill; thêm virtual composite root cho FK; khóa causal `IndicatorView` và family constraint; xác nhận `requirements.html` là nguồn yêu cầu chính.
- **v1.1** — 2026-08-11 — Làm rõ ranh giới kiến trúc sau review: architectural style theo từng process (§1.1) + Service Boundary & Ownership (§1.2) + read projection cho Go (§1.2.5) + artifact vs workload (§1.3.1); chốt transactional outbox (§5.7) và `POST /internal/events` (§5.8); chốt lease token cho retry/take-over (§8.3.1); tách Target Architecture khỏi Delivery Roadmap (§12.0); thêm ADR-015, ADR-016; sửa bug `weighted_vote` với `threshold = 0`; phân loại nguồn gốc yêu cầu [SRC]/[PD]/[NFR] (`proposal.md` §4.4) + điều kiện đo cho mọi SLO (§2.2); thêm 19 sơ đồ render sẵn ở `assets/`.
- **v1.0** — 2026-08-11 — Bản blueprint đầu cho phần thiết kế kiến trúc.

## Tác giả

| Thành viên          | Phạm vi phụ trách                                                     |
| ------------------- | --------------------------------------------------------------------- |
| Thành viên A (Lead) | Market Data (Binance adapter, realtime, backfill), Chart Overlay, Web dashboard |
| Thành viên B        | Strategy Registry, Composite, Backtest Engine, Evaluator              |
| Thành viên C        | Search Loop, Leaderboard, News + Sentiment, Observability             |

## Nguồn

Mọi yêu cầu trong thư mục này được truy vết tới `Crypto Strategy Lab – Đồ án cuối kỳ.pdf`, đặc biệt §4–§14 (module chức năng), §15–§24 (search/backtest/leaderboard), §27–§30 (news/sentiment), §32 (architectural drivers), §35–§36 (database, versioning), §40–§44 (câu hỏi kiến trúc, scenario đánh giá, anti-pattern), §45–§46 (deliverables, demo).
