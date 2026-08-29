# Go API & Market Data Review Checklist

> Canonical v1.5: checklist này chỉ áp dụng cho `server/`. Strategy, indicator/composite, experiment, backtest, evaluation, search, ranking/Leaderboard, news/sentiment và Agent Platform thuộc Python `app/`.

## 1. Boundary gate

- [ ] `server/` không chứa package/runtime cho strategy, indicator, composite, experiment, backtest, evaluation, search, ranking, news, sentiment hoặc agent.
- [ ] Browser chỉ gọi public Go REST/WSS; Go proxy Python-domain command/query qua versioned internal client.
- [ ] Signed internal request có principal ID, role/scopes, correlation ID, deadline và contract version; Python vẫn re-check ownership.
- [ ] Go không đọc/ghi bảng gốc thuộc Python; không tính signal, indicator, fill, PnL, metric, score hoặc provenance join.
- [ ] Python event được persist/outbox trước khi `POST /internal/events`; Go chỉ de-duplicate, map subscription và WebSocket fan-out.
- [ ] `ai` không có public route do Go expose; mọi inference đi từ Python `research`.

## 2. Public API / edge

- [ ] Middleware order được test: request ID → CORS allowlist → rate limit/quota → auth → RBAC → body/schema validation → handler.
- [ ] CORS dùng exact allowlist, không echo `Origin`; cookie write route có CSRF + strict Origin.
- [ ] Auth dùng RS256/audience/issuer/expiry; refresh token hash + rotation/reuse detection; log không chứa token/secret.
- [ ] Error envelope ổn định, không lộ stack/internal URL; `X-Request-ID` được trả về.
- [ ] State-changing request hỗ trợ idempotency hoặc trả conflict rõ ràng.
- [ ] Body, page, timeframe/range và WebSocket subscription đều bounded; `429` có `Retry-After`.
- [ ] Public Python-domain DTO chỉ được transport-map; OpenAPI/contract test phát hiện breaking change.

## 3. Market Data correctness

- [ ] Raw Binance payload chỉ tồn tại trong provider adapter; domain/transport dùng normalized `Candle`, `KlineUpdate`, `BBO`.
- [ ] `Candle` canonical luôn closed; `Final=false` chỉ là provisional memory/UI state, không persist và không vào Strategy Runtime.
- [ ] Closed candle de-duplicate theo `(provider, symbol, timeframe, open_time)`.
- [ ] Mỗi panel bootstrap đúng 1.000 closed candles mới nhất; provisional cùng `open_time` thì replace, mới hơn thì append.
- [ ] Đổi một panel chỉ cancel/replace history request + subscription của panel đó.
- [ ] BBO có executable bid/ask semantics, sequence/update ID và bounded memory/replay path; không ghi nhầm vào candle table.
- [ ] REST backfill chạy sau reconnect từ checkpoint/last closed time; overlap an toàn và chỉ emit recovery sau persistence/ACK boundary.
- [ ] Provider REST weight limiter dùng weight thật + deadline/backoff; `429/418` không tạo retry storm.

## 4. WebSocket lifecycle

- [ ] Chỉ dùng một WebSocket library/adaptor; raw connection không rò vào domain ports.
- [ ] Một reader sở hữu inbound frames; một writer serialize control/data writes.
- [ ] Desired subscriptions được lưu và restore sau reconnect; control ACK/timeout được theo dõi.
- [ ] Ingress/fan-out channels bounded, overflow policy có metric/log và không block toàn hub.
- [ ] `Run(ctx)` có terminal path; `Close` idempotent; shutdown unblock I/O, đợi goroutine và không reconnect lại.
- [ ] Subscription key đủ `provider/symbol/timeframe` và overlay key đủ `strategy_version/config_hash` khi fan-out Python event.
- [ ] Client gap được phát hiện bằng sequence/event ID và có REST refetch path.

## 5. Concurrency and resource safety

- [ ] Goroutine ownership/lifecycle rõ; sender đóng channel; shared state có mutex/actor ownership.
- [ ] Context là tham số đầu của I/O path; loop kiểm tra cancellation; mọi outbound call có deadline.
- [ ] Không dùng sleep để đồng bộ test; race test không phát hiện data race.
- [ ] DB/HTTP/WS body được close; pool, buffer, slice và payload size có giới hạn.
- [ ] Error wrap bằng `%w`; panic chỉ cho startup invariant không thể phục hồi.

## 6. Persistence ownership

- [ ] Go migration chỉ tạo market/auth/edge schema và grants tương ứng.
- [ ] Runtime role Go không có quyền trên Python research/agent tables.
- [ ] Closed-candle write + checkpoint ordering không tạo checkpoint vượt quá dữ liệu đã commit.
- [ ] Market cache revision không làm thay đổi immutable dataset/version mà experiment đã tham chiếu.
- [ ] Internal event de-dup key và retention policy được test.

## 7. Verification before merge

- [ ] Unit/contract tests: provider mapping, kline final boundary, BBO, history limit=1000, provisional merge, API proxy/signature, auth/RBAC/quota/error mapping.
- [ ] Integration tests: reconnect + REST backfill + de-dup; Python unavailable; duplicate `/internal/events`; browser cannot reach Python/AI directly.
- [ ] Lifecycle/race tests: close during read/write/backoff, slow client, queue overflow, shutdown.
- [ ] `go test ./...`, race suite, vet/lint and architecture-boundary test pass.
- [ ] Logs/metrics carry `request_id`/`correlation_id`; no secret, raw article HTML hoặc model prompt bị log.
- [ ] Không claim performance/reliability complete nếu chưa có benchmark/demo evidence liên kết trong `traceability.md`.
