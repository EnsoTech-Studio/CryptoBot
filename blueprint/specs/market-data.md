# Đặc tả: Market Data (Binance Adapter, Realtime, Backfill)

## Mô tả

Module duy nhất trong hệ thống biết Binance tồn tại. Trách nhiệm:

- Lấy nến lịch sử (REST `/api/v3/klines`) và nến realtime (WSS `<symbol>@kline_<interval>`).
- Chuẩn hoá payload Binance thành `Candle` nội bộ — **không để field name của Binance rò rỉ ra bất kỳ module nào khác**.
- Tự phục hồi khi mất kết nối: reconnect có backoff + backfill khoảng nến đã mất.
- Chống vượt rate limit của Binance (weight-based).
- Đóng gói một tập nến thành `market_dataset` bất biến để experiment tái lập được. `candles` là cache vận hành; bản snapshot dùng cho backtest nằm ở `market_dataset_candles`.

Đặc biệt phải đảm bảo:

- **0 nến đã đóng bị mất** sau bất kỳ lần disconnect nào.
- **0 nến trùng** dù backfill chạy chồng lấp nhiều lần.
- Nến chưa đóng (`provisional`) **không bao giờ** được ghi làm nguồn sự thật lịch sử.
- Thêm sàn mới (OKX, Bybit) **không sửa** `MarketService`, API contract, hay frontend.

## Contract

```python
class MarketDataProvider(Protocol):
    def provider_id(self) -> str: ...
    def list_candles(self, symbol: str, timeframe: Timeframe,
                     from_: datetime, to: datetime) -> list[Candle]: ...
    def stream_candles(self, subscriptions: list[StreamKey],
                       publish: Callable[[CandleEvent], None]) -> Subscription: ...
```

```python
@dataclass(frozen=True)
class Candle:
    provider:   str          # 'binance'
    symbol:     str          # 'BTCUSDT'
    timeframe:  Timeframe
    open_time:  datetime
    close_time: datetime
    open:  Decimal
    high:  Decimal
    low:   Decimal
    close: Decimal
    volume: Decimal
    trade_count: int | None
    is_closed: bool          # False = provisional
```

Ánh xạ từ Binance (chỉ tồn tại bên trong adapter):

| Binance field | `Candle` field | Ghi chú                                    |
| ------------- | -------------- | ------------------------------------------ |
| `k.t`         | `open_time`    | ms epoch → UTC datetime                    |
| `k.T`         | `close_time`   | ms epoch → UTC datetime                    |
| `k.o/h/l/c`   | `open/high/low/close` | string → `Decimal` (**không** float) |
| `k.v`         | `volume`       | string → `Decimal`                         |
| `k.n`         | `trade_count`  |                                            |
| `k.x`         | `is_closed`    | `false` → provisional                      |

> **`Decimal`, không `float`.** Giá BTC có 8 chữ số thập phân; float64 làm tròn và sai số tích luỹ qua hàng nghìn trade trong backtest. Sai số này đủ để lật dấu Total Return của strategy giao dịch thường xuyên.

## Luồng chính

Hai đường gọi dùng chung adapter/cache nhưng có giới hạn khác nhau:

| Đường gọi | Mục đích | Giới hạn |
| --- | --- | --- |
| Public `GET /api/v1/markets/candles` -> `MarketService.get_candles` | Vẽ chart và đọc lịch sử | Tối đa **1.000 nến/response**; Go và Python đều kiểm tra |
| Internal `MarketService.ensure_dataset` | Chuẩn bị snapshot bất biến cho experiment/search/backtest | Tối đa **20.000 nến/experiment**; không trả trực tiếp cho browser |

`get_candles` có thể đọc operational cache; `ensure_dataset` luôn kết thúc bằng
`market_dataset_candles`. Hai giới hạn này không được trộn vào cùng một contract.

### A. Nạp nến lịch sử (bounded)

1. `MarketService.get_candles(provider, symbol, timeframe, from, to)` phục vụ public chart; `MarketService.ensure_dataset(...)` gọi cùng adapter/cache khi chuẩn bị snapshot nội bộ.
2. Validate pair/timeframe/range ở cả hai path. Public path giới hạn **1.000 nến/response** → `422 range_too_large`; dataset path giới hạn `max_candles_per_experiment` (**20.000**) → `422 dataset_too_large`. `provider` là một phần bắt buộc của request và dataset identity, không được mặc định ngầm khi có nhiều provider cùng symbol.
3. Query `candles` trong DB cho khoảng `[from, to]`. Đây là operational cache phục vụ chart và phát hiện gap, không phải nguồn input trực tiếp của backtest.
4. Phát hiện gap: so số nến thực tế với số nến kỳ vọng `(to − from) / interval`.
5. Nếu có gap → `BinanceAdapter.list_candles()` cho **từng đoạn gap** (không refetch cả khoảng).
6. Adapter chia nhỏ theo `limit=1000/request`, mỗi request đi qua `WeightLimiter`.
7. UPSERT vào `candles` (`ON CONFLICT (provider, symbol, timeframe, close_time) DO UPDATE`). Đây là cache hiện tại; việc update row ở đây không được phép làm thay đổi dataset snapshot đã tạo.
8. Trả về danh sách nến sắp xếp theo `close_time` tăng dần.

### B. Stream realtime

```mermaid
sequenceDiagram
    autonumber
    participant BN as Binance WSS
    participant AD as BinanceAdapter
    participant MS as MarketService
    participant DB as candles
    participant CK as stream_checkpoints
    participant HUB as WS Hub (Go)

    Note over AD,BN: 1 connection, multiplex nhiều stream
    AD->>BN: SUBSCRIBE btcusdt@kline_5m, btcusdt@kline_15m, ...

    loop mỗi tick (~1-2s)
        BN->>AD: {"k":{"t":...,"c":"118150","x":false}}
        AD->>AD: validate schema → Candle(is_closed=False)
        AD->>MS: MarketPriceUpdated
        MS->>HUB: candle delta (provisional)
        Note over MS,DB: KHÔNG ghi DB — nến chưa đóng
    end

    BN->>AD: {"k":{...,"x":true}}
    AD->>MS: CandleClosed
    MS->>DB: UPSERT (idempotent)
    MS->>CK: last_closed_at = T, is_stale = false
    MS->>HUB: candle closed + trigger overlay
```

Quy tắc ping/pong: Binance gửi ping mỗi 3 phút, adapter phải pong trong 10 phút hoặc bị ngắt. Adapter cũng tự gửi ping mỗi 30 s để **phát hiện** connection chết (TCP có thể "im lặng chết" mà không có close frame).

### C. Reconnect + Backfill

1. Detect disconnect: close frame, hoặc ping timeout, hoặc lỗi đọc socket.
2. `stream_checkpoints`: `is_stale = true`, `reconnect_count += 1`. Publish `StreamStale`.
3. Reconnect với backoff: `min(30s, 1s × 2^attempt)` + jitter `±20%`.
4. Sau khi connect thành công:
   - Đọc `last_closed_at = T1` từ `stream_checkpoints` (**từ DB, không từ RAM** — RAM mất khi process restart).
   - `list_candles(symbol, timeframe, from=T1, to=now())`.
   - UPSERT theo thứ tự thời gian tăng dần.
   - `last_closed_at = Tn`, `is_stale = false`. Publish `StreamRecovered`.
5. Nếu khoảng thiếu > 1000 nến → chia nhiều request, mỗi request qua `WeightLimiter`.

### D. Outbound weight limiter

Binance tính **weight**, không tính số request:

| Endpoint                          | Weight                             |
| --------------------------------- | ---------------------------------- |
| `/api/v3/klines` limit ≤ 100      | 1                                  |
| `/api/v3/klines` limit 101–500    | 2                                  |
| `/api/v3/klines` limit 501–1000   | 5                                  |
| `/api/v3/klines` limit 1001–1500  | 10                                 |
| Giới hạn                          | `provider_weight_limit_per_minute` (**6000** ở MVP; đổi được theo tài liệu provider; đọc và hiệu chỉnh theo header `X-MBX-USED-WEIGHT-1M`) |

Cơ chế: token bucket với capacity = 80% `provider_weight_limit_per_minute` (để lại đệm), refill theo giây. Mọi call REST đi qua `WeightLimiter.acquire(weight)`. Nếu không có token trong deadline của request → trả `502 market_provider_throttled` thay vì chờ vô hạn.

Adapter đọc header `X-MBX-USED-WEIGHT-1M` từ mỗi response và **hiệu chỉnh** bucket theo giá trị thật. Đây là điểm quan trọng: bucket local có thể lệch với thực tế (nhiều process, hoặc Binance đổi ngưỡng), và header là nguồn sự thật.

### E. Đóng gói `market_dataset`

Khi tạo experiment hoặc search run:

1. Nhận `(provider, symbol, timeframe, from, to)`.
2. Đảm bảo đủ nến (luồng A).
3. Sắp xếp nến theo `close_time` và tính `content_hash` từ toàn bộ field có ý nghĩa của snapshot: `canonical(list[(open_time, close_time, o, h, l, c, v, trade_count)])`. `NULL` của `trade_count` có encoding riêng, không được biến thành `0`.
4. Mở transaction và khoá identity bằng `pg_advisory_xact_lock(hashtextextended(canonical_identity, 0))`, trong đó `canonical_identity = provider|symbol|timeframe|range_from|range_to`. Khoá này chỉ serialize hai lần tạo dataset cho cùng một range, không khoá provider/range khác.
5. Tìm `market_datasets` có cùng `(provider, symbol, timeframe, range_from, range_to)`:
   - Không có → INSERT `revision_no = 1` với `dataset_version = "{provider}-{symbol}-{tf}-{from:%Y%m%d}-{to:%Y%m%d}"`, rồi bulk INSERT toàn bộ nến vào `market_dataset_candles` trong cùng transaction.
   - Có và `content_hash` **khớp** → kiểm tra snapshot tồn tại đủ `candle_count` row rồi dùng lại.
   - Có và `content_hash` **khác** → dữ liệu đã bị revise. Lấy `next_revision = max(revision_no) + 1`, INSERT dataset với suffix `-r{next_revision}` (`-r2`, `-r3`, ...), rồi INSERT snapshot mới trong cùng transaction và log cảnh báo. **Không** sửa hoặc xoá snapshot cũ.
6. `ExperimentService` lưu `market_dataset_id`; Worker nạp input bằng `SELECT ... FROM market_dataset_candles WHERE market_dataset_id = ? ORDER BY close_time`. Không có backtest nào đọc trực tiếp cache `candles`.

## Kịch bản lỗi

| Tình huống                                          | Phản ứng                                                                                                     |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| WebSocket disconnect 60 s                           | `is_stale=true` → UI badge STALE; reconnect backoff; backfill từ `last_closed_at` → **0 nến mất**             |
| WebSocket disconnect trong lúc backfill đang chạy   | Backfill là idempotent (UPSERT) → chạy lại từ đầu an toàn, không tạo nến trùng                                |
| Process restart giữa lúc mất kết nối                | `last_closed_at` nằm trong DB → backfill vẫn đúng điểm neo                                                   |
| Binance trả `429`                                   | `WeightLimiter` hiệu chỉnh xuống theo `Retry-After`; request hiện tại retry sau backoff; nếu quá deadline → `502` |
| Binance trả `418` (IP bị ban tạm)                   | Dừng mọi outbound REST tới hết `Retry-After`; `is_stale=true`; log CRITICAL; UI hiện "nguồn dữ liệu tạm không khả dụng" |
| Binance trả nến có `high < low` (dữ liệu lỗi)       | Adapter reject nến đó, log WARN với payload gốc, **không** ghi DB. `CHECK (high >= low)` là lớp phòng thủ thứ hai |
| Nến trả về có `close_time` trong tương lai           | Reject (clock skew hoặc payload lỗi); log WARN                                                                |
| Backfill trả về nến khác với nến đã có trong DB     | `ON CONFLICT DO UPDATE` chỉ cập nhật operational cache; nếu nến đó đã thuộc một `market_dataset` → tạo dataset `-r{next_revision}` với snapshot mới. Snapshot cũ không đổi |
| Gap không thể lấp (Binance không có dữ liệu khoảng đó) | Ghi `stream_checkpoints` và trả về nến có thật; API trả kèm `gaps: [{from, to}]` để UI hiện rõ; **không** nội suy giá |
| Provider/symbol không tồn tại                      | `422 unknown_market_pair` (validate trước khi gọi, đối chiếu `(provider, symbol)` trong `market_pairs`)       |
| `to > now()`                                        | Clamp về `now()`, log DEBUG; không lỗi                                                                        |
| Số nến yêu cầu vượt 20.000                          | `422 dataset_too_large` kèm `max_candles` và `suggested_ranges`                                                |
| Nhiều worker cùng backfill một khoảng               | UPSERT idempotent → không hại. Khi chạy > 1 worker: shared `WeightLimiter` (Redis) để tổng weight không vượt ngưỡng — điều kiện (b) ở `design.md` §12.0        |
| Timezone: Binance trả ms epoch UTC                  | Chuẩn hoá tất cả sang `TIMESTAMPTZ` UTC ở biên adapter. **Không** có datetime naive ở bất kỳ đâu               |

## Ràng buộc

**Tính đúng đắn**

- `PRIMARY KEY (provider, symbol, timeframe, close_time)` là cơ chế de-dup duy nhất. Không tự viết logic "kiểm tra tồn tại rồi insert" (race).
- `candles` là operational cache có thể được refresh; `market_dataset_candles` là artifact bất biến và là **nguồn duy nhất của backtest**.
- `market_datasets` có `revision_no` tăng dần trong cùng identity; `UNIQUE (provider, symbol, timeframe, range_from, range_to, revision_no)` + advisory transaction lock chặn hai worker cùng cấp một revision.
- `market_dataset_candles` có `PRIMARY KEY (market_dataset_id, close_time)` và DB trigger chặn UPDATE/DELETE, kể cả cascade; application path cũng không có đường sửa/xoá.
- `market_datasets` cũng là append-only; provider revise tạo dataset revision mới thay vì sửa artifact cũ.
- Nến `is_closed=false` chỉ đi tới WebSocket, **không** tới `candles`.
- Mọi giá dùng `Decimal`/`NUMERIC(24,8)`, không `float`.
- Mọi timestamp là UTC `TIMESTAMPTZ`.
- `last_closed_at` lưu trong DB, không chỉ trong RAM.

**Hiệu năng**

- `GET /markets/candles` cache hit (dữ liệu có sẵn trong DB): p95 **< 300 ms** cho 1000 nến.
- Độ trễ Binance tick → WS Hub: p95 **< 500 ms** (phần còn lại của ngân sách 1.5 s dành cho overlay + network tới browser).
- Backfill 1000 nến: **< 3 s** (1 REST call + 1 bulk UPSERT).
- Bulk UPSERT dùng `execute_values`/`COPY`-style batch, không loop từng row.

**Khả năng mở rộng**

- Thêm provider = thêm 1 class implement `MarketDataProvider` + 1 row `market_pairs` với `provider` mới. Cặp key là `(provider, symbol)`, nên `binance/BTCUSDT` và `okx/BTCUSDT` cùng tồn tại.
- `MarketService`, API contract, frontend: **0 dòng đổi**.
- `candles.provider` đã là phần của PK và `idx_candles_range` → hai provider cùng symbol không xung đột, không cần migration.

**Bảo mật**

- Chỉ gọi **public market data endpoint** của Binance. Không dùng API key, không có endpoint nào cần signature.
- Không có credential sàn nào tồn tại trong hệ thống (`proposal.md` §4.3).
- Validate schema payload từ WebSocket trước khi dùng (payload từ nguồn ngoài = untrusted).

**Quan sát được**

- `market_stream_stale{symbol,timeframe}` gauge
- `market_reconnects_total{symbol,timeframe}` counter
- `market_last_closed_age_seconds{symbol,timeframe}` gauge
- `market_backfill_candles_total` counter
- `provider_weight_used` gauge (từ header Binance)
- `provider_requests_total{operation,status}` counter

## Tiêu chí chấp nhận

- [ ] AC-01: Ngắt network container Python 60 s rồi nối lại → query `candles` liên tục **không có gap**, `reconnect_count` tăng đúng 1.
- [ ] AC-02: Chạy backfill cùng khoảng **3 lần liên tiếp** → số row trong `candles` không đổi sau lần đầu.
- [ ] AC-03: Kill process Python giữa lúc mất kết nối, restart → backfill vẫn bắt đầu từ `last_closed_at` cũ, không mất nến.
- [ ] AC-04: Nến `x:false` đến 20 lần trong 1 phút → `candles` **không có row nào** cho `close_time` đó; UI vẫn thấy giá cập nhật.
- [ ] AC-05: WebSocket down → `GET /markets/status` trả `is_stale=true` + `last_closed_at`; `GET /markets/candles` vẫn trả nến lịch sử `200`.
- [ ] AC-06: Request `from=2017-01-01&to=2026-01-01&timeframe=1m` → `422 dataset_too_large`, **không** OOM, **không** treo process.
- [ ] AC-07: Giả lập Binance trả `429` → `WeightLimiter` giảm rate, request tiếp theo không bị `418`.
- [ ] AC-08: Inject nến có `high < low` → bị reject ở adapter, log WARN, `candles` không có row đó.
- [ ] AC-09: Thêm `OKXAdapter` fixture (trả nến từ file JSON) → `GET /markets/candles?provider=okx` hoạt động với **0 dòng** thay đổi trong `MarketService`/Go API/frontend.
- [ ] AC-09b: Seed `binance/BTCUSDT` và `okx/BTCUSDT` → cả hai row tồn tại trong `market_pairs`; query/provider và dataset không trộn nến giữa hai nguồn.
- [ ] AC-10: Tạo dataset 2 lần cho cùng range, dữ liệu không đổi → dùng lại cùng `dataset_version`. Provider revise 1 nến → cache `candles` nhận giá trị mới, `content_hash` khác → dataset `-r2` và snapshot mới; revise lần nữa với hash khác → `-r3`; snapshot cũ **không** bị sửa, backtest trỏ dataset cũ vẫn byte-identical.
- [ ] AC-10b: Hai worker đồng thời tạo dataset cho cùng identity → advisory lock serialize transaction; không có duplicate `revision_no`, không có `dataset_version` collision, và cùng một `content_hash` chỉ dùng một snapshot.
- [ ] AC-10c: Thử `UPDATE` hoặc `DELETE` trên `market_datasets`/`market_dataset_candles` → DB trigger reject; INSERT revision mới vẫn thành công và snapshot cũ còn nguyên.
- [ ] AC-11: Test static: `grep -r "\"k\"\|k\.t\|k\.x" app/ --include=*.py` chỉ khớp trong `infrastructure/market/binance_*.py`.
- [ ] AC-12: Độ trễ tick → WS Hub đo trên 20 mẫu: p95 < 500 ms.
