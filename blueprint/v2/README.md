# Crypto Strategy Lab — Target Architecture V2

V2 là bộ kiến trúc đích bổ sung các yêu cầu mới của giảng viên mà V1 và runtime
hiện tại chưa đáp ứng đầy đủ. Bộ tài liệu này **không mô tả trạng thái đã triển
khai** và không thay thế hay chỉnh sửa bất kỳ file V1/source code nào.

## Quy ước trạng thái

- Tất cả sơ đồ trong `assets/diagrams-v2/` được định danh bằng hậu tố `-v2` và
  thuộc bộ **TARGET V2**; đây không phải sơ đồ trạng thái hiện tại.
- Sơ đồ mô tả contract, ownership và pipeline cần đạt; không phải bằng chứng code
  hiện tại đã hoàn thành.
- Bằng chứng hoàn thành sau này phải đến từ test, benchmark, demo và provenance
  record thật; sơ đồ không tự chứng minh implementation.

## Quyết định ngôn ngữ V2

- **Go Edge & Market Gateway** sở hữu public REST/WebSocket, auth/RBAC, kết nối
  realtime tới exchange, chuẩn hóa Candle/BBO và fan-out dữ liệu tới browser.
- **Python Strategy Platform** sở hữu Strategy Runtime, strategy authoring bằng
  AI/DSL, indicator, composite, realtime analysis, search, backtest, execution
  simulation, evaluation, ranking, news extraction/tagging và sentiment.
- Realtime và backtest dùng **cùng một Strategy Runtime Python**. Go truyền market
  event chuẩn hóa qua internal stream; không port strategy Python sang Go.
- **Python Worker** dùng cùng image/package với Python Strategy API nhưng là
  workload riêng, có thể scale từ 1 tới N replica.
- PostgreSQL là nguồn sự thật và đồng thời cung cấp durable job queue,
  transactional outbox và immutable dataset snapshot trong giai đoạn đầu.

## Danh mục sơ đồ

| # | Slug | Nội dung chính | Yêu cầu được chốt |
|---|---|---|---|
| 01 | `01-c4-l1-system-context-v2` | Actor và hệ thống ngoài | AI strategy input, nhiều provider |
| 02 | `02-c4-l2-container-v2` | Runtime/container ownership | Go realtime, Python strategy/backtest |
| 03 | `03-c4-l3-python-strategy-platform-v2` | Component Python theo ports/adapters | Registry, generator, AI, BBO execution |
| 04 | `04-high-level-architecture-v2` | High-level pipeline toàn hệ thống | Tích hợp mọi luồng V2 |
| 05 | `05-market-realtime-candle-bbo-v2` | Candle + BBO từ exchange tới UI/Python | WSS, normalized DTO, no porting |
| 06 | `06-market-provider-replaceability-v2` | Thêm Binance/OKX qua registry | Frontend không đổi |
| 07 | `07-ai-strategy-authoring-v2` | Text/URL thành StrategySpec an toàn | AI/LLM, version, approval |
| 08 | `08-strategy-runtime-parity-v2` | Một runtime cho realtime/backtest | Không có hai nguồn chân lý |
| 09 | `09-search-backtest-pipeline-v2` | Generator registry → worker → rank | Search thay được, bounded loop |
| 10 | `10-bbo-long-short-execution-v2` | Mô phỏng LONG/SHORT bằng BBO | Fee, spread, slippage, SL/TP |
| 11 | `11-trade-result-provenance-v2` | Trade detail và provenance chain | Truy nguồn đầy đủ |
| 12 | `12-erd-v2` | ERD dữ liệu V2 | Candle/BBO snapshot, AI specs/tags |
| 13 | `13-news-html-llm-pipeline-v2` | RSS/HTML → extract → tag → sentiment | Lưu tag để tái sử dụng |
| 14 | `14-outbox-retry-order-v2` | Retry, duplicate, ordering | At-least-once + idempotency |
| 15 | `15-outbox-event-state-v2` | State machine event | Backoff, dead-letter |
| 16 | `16-job-queue-scale-v2` | 1 → N worker → broker | Scale 100.000 có metric/gate |
| 17 | `17-experiment-create-transaction-v2` | Snapshot + job atomic | Dataset bất biến |
| 18 | `18-python-worker-execution-v2` | Claim/heartbeat/execute/commit | Lease token, BBO snapshot |
| 19 | `19-worker-lease-takeover-v2` | Worker chết và takeover | Không mất job/không stale write |
| 20 | `20-search-run-state-v2` | Search state machine | Pause/resume/cancel/stop |
| 21 | `21-backtest-run-state-v2` | Backtest state machine | Retryable failure rõ ràng |
| 22 | `22-defense-in-depth-ai-strategy-v2` | Security + AI/plugin guardrails | SSRF, sandbox, human approval |

## Mười gap được bao phủ

1. Strategy mới đi qua Registry/StrategySpec, không thêm `switch` trong core.
2. Text hoặc URL được AI chuyển thành declarative StrategySpec có validation,
   preview và human approval; không chạy code LLM sinh trực tiếp.
3. Search algorithm được resolve qua GeneratorRegistry/CandidateGenerator port.
4. Provider được resolve qua MarketProviderRegistry và DTO Candle/BBO chuẩn hóa.
5. Realtime dùng exchange WSS, reconnect/backoff, checkpoint và REST backfill.
6. Execution state hỗ trợ FLAT/LONG/SHORT.
7. TradeFact ghi đủ pair, thời gian, side, notional, giá, SL/TP, fee, spread,
   slippage, gross/net PnL.
8. BBO được lưu và đóng băng cùng dataset để mô phỏng fill; fallback 5 bps phải
   được đánh dấu trong provenance nếu BBO thiếu.
9. News hỗ trợ RSS và article HTML, LLM tagging có model/prompt version và lưu DB.
10. Queue có lease, retry, dedup, ordering, dead-letter; leaderboard truy tới
    immutable strategy/dataset/execution/model versions và có benchmark scale.

## Nguồn sự thật và render

Các file `.mmd` trong `blueprint/assets/diagrams-v2/` là nguồn sự thật của V2.
SVG cùng thư mục và PNG trong `blueprint/assets/diagrams-png-v2/` là output
render, không sửa bằng tay. V1 tiếp tục dùng quy trình riêng hiện có.
