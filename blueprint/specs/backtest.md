# Đặc tả: Python Backtest Engine

Trạng thái: Python canonical  
Owner: Python `research` API/Worker  
Runtime seam hiện có: `app/services/backtest_engine.py`

## Mô tả

Backtest Engine chạy StrategyVersion theo chronological causal event loop trên immutable
market dataset. Nó tạo trade/signal/equity facts; Evaluator tính metrics ở bước sau. Engine
không chạy trong Go. Go chỉ nhận public request, proxy signed command/query và fan-out progress.

Realtime và backtest resolve cùng Python Strategy Runtime, cùng StrategyVersion, parameters,
indicator semantics và signal validator. Execution khác nhau chỉ ở adapter: realtime nhận
normalized current event từ Go; backtest replay immutable Candle/BBO dataset.

## Input contract

```json
{
  "experiment_id": "01J_EXP",
  "symbol": "BTCUSDT",
  "quote_currency": "USDT",
  "from": "2026-01-01T00:00:00Z",
  "to": "2026-02-01T00:00:00Z",
  "initial_capital": 1000.0,
  "position_policy": {
    "kind": "fixed_notional",
    "entry_notional": 100.0,
    "leverage": 1.0
  },
  "strategy": {
    "strategy_id": "ma_cross",
    "version": "v1",
    "parameters": {"fast": 20, "slow": 50},
    "spec_hash": "sha256:...",
    "artifact_hash": "sha256:..."
  },
  "dataset": {
    "dataset_id": "01J_DATASET",
    "content_hash": "sha256:..."
  },
  "execution": {
    "fill_policy": "bbo_limit_cross_v1",
    "fee_bps": 10.0,
    "spread_policy": "observed_bbo",
    "slippage_bps": 2.0,
    "open_position_at_end": "close_at_last_executable_quote",
    "intrabar_priority": "stop_loss_first"
  },
  "risk_policy": {
    "stop_loss_pct": 2.0,
    "take_profit_pct": 4.0
  }
}
```

`strategy` có thể là single hoặc composite immutable definition. API materialize mọi default
trước khi persist snapshot; worker không đọc current/latest config.

## Event contract

Canonical replay event:

```python
@dataclass(frozen=True)
class MarketEvent:
    event_time: datetime
    source_sequence: int
    kind: Literal["BBO", "CANDLE_CLOSED"]
    payload: BBO | Candle
```

Order key là `(event_time, kind_priority, source_sequence)` với BBO được apply trước
`CANDLE_CLOSED` tại cùng timestamp. Dataset không chứa provisional candle.

## Strategy execution

Tại mỗi closed candle index `i`:

1. Apply mọi BBO event đã đến trước/equal event order.
2. Append causal closed Candle.
3. Update/precompute declared indicators đến `i`.
4. Build `AnalysisContext(index=i)` không expose future.
5. Resolve fresh Python strategy instance theo exact `(strategy_id,version)`.
6. Gọi `analyze(context)` và validate finite/action/price/size/evidence.
7. Chuyển signal thành position intent theo deterministic position policy.
8. Apply fill/risk/cost policy, persist/accumulate immutable facts.

Strategy không tự tính fee, position accounting, evaluation hoặc rank.

## Fill policy

### BBO LIMIT crossing

- BUY/LONG entry executable khi limit price `>= ask`; fill base price = ask.
- SELL/SHORT entry executable khi limit price `<= bid`; fill base price = bid.
- LONG exit bán ở bid; SHORT exit mua lại ở ask.
- Quote phải đã đến theo event order; không dùng future BBO.
- Nếu không crossing, intent chờ/expire theo snapshot policy; không giả fill.

### Explicit fallback

Nếu dataset không có BBO và snapshot cho phép candle fallback:

- Policy ID/version phải explicit.
- Spread/slippage assumption phải persist.
- Result/provenance đánh dấu `fill_source = candle_fallback`.
- Không được âm thầm dùng candle close như live executable quote.

## Position state machine

MVP dùng one-net position:

```text
FLAT
  -> LONG on LONG entry fill
  -> SHORT on SHORT entry fill

LONG
  -> FLAT on exit/risk/end fill
  -> SHORT only through deterministic close-then-open reversal

SHORT
  -> FLAT on exit/risk/end fill
  -> LONG only through deterministic close-then-open reversal
```

Không hedged concurrent long/short trong MVP. Reversal tạo hai fills/facts có order rõ ràng.

## Risk policy

`risk_policy = null` nghĩa SL/TP disabled; trade fields `sl_price` và `tp_price` là `null` và
UI hiển thị `N/A`.

Fixed-percent policy materialize tại entry:

```text
LONG:  sl = entry_price * (1 - sl_pct), tp = entry_price * (1 + tp_pct)
SHORT: sl = entry_price * (1 + sl_pct), tp = entry_price * (1 - tp_pct)
```

Nếu một candle chạm cả SL và TP mà không có intrabar ticks, dùng snapshot
`intrabar_priority`; default `stop_loss_first` là conservative. Risk trigger price và
executable fill price là hai field khác; cost được tính trên actual fill.

## Cost và PnL

Mọi trade persist breakdown bằng quote currency:

```text
entry_notional = abs(entry_price * quantity)
exit_notional  = abs(exit_price * quantity)

gross_pnl_long  = (exit_price - entry_price) * quantity
gross_pnl_short = (entry_price - exit_price) * quantity

fee_paid     = entry_fee + exit_fee
spread_cost  = deterministic observed/reference spread attribution
slippage_cost = deterministic difference from reference to execution
net_pnl      = gross_pnl - fee_paid - spread_cost - slippage_cost
```

Không double-count spread: fill base/execution/reference definitions phải versioned và fixture
chứng minh attribution. Currency/rounding rule được materialize; internal runtime giữ float64.

## Trade result contract

```json
{
  "trade_id": "01J_TRADE",
  "experiment_id": "01J_EXP",
  "backtest_run_id": "01J_RUN",
  "symbol": "BTCUSDT",
  "quote_currency": "USDT",
  "side": "LONG",
  "entry_time": "2026-01-10T10:00:00Z",
  "exit_time": "2026-01-10T13:00:00Z",
  "entry_price": 42000.0,
  "exit_price": 42500.0,
  "quantity": 0.002380952381,
  "entry_notional": 100.0,
  "exit_notional": 101.19047619,
  "sl_price": 41160.0,
  "tp_price": 43680.0,
  "fee_paid": 0.201190476,
  "spread_cost": 0.02,
  "slippage_cost": 0.04,
  "gross_pnl": 1.19047619,
  "net_pnl": 0.929285714,
  "entry_fill_source": "bbo",
  "exit_fill_source": "bbo",
  "strategy_version_ref": "ma_cross@v1",
  "provenance_ref": "provenance:01J_RUN"
}
```

Không dùng một field `profit` mơ hồ. Public view có thể alias `profit = net_pnl` nhưng schema
phải định nghĩa rõ và không bỏ gross/cost breakdown.

## Persistence boundary

Python Worker ghi trong transaction/fenced lease:

- Backtest run status/version.
- Signal/fill/trade facts.
- Equity points hoặc content-addressed series.
- Completion/failure reason.
- Outbox `backtest.completed` hoặc `backtest.failed`.

Evaluator consume persisted facts sau completion. Worker cũ mất lease token không được ghi.
Go không ghi các bảng này.

## Equity và end-of-sample

- Equity mark-to-market theo explicit reference price trong snapshot.
- Curve order deterministic và bắt đầu tại `initial_capital`.
- Open position at end xử lý đúng `open_position_at_end`; default target đóng tại last
  executable quote, không bỏ PnL ẩn.
- Không có executable price thì run fail/partial theo policy explicit; không bịa fill.

## Kịch bản lỗi

| Tình huống | Phản ứng |
|---|---|
| Dataset hash mismatch | Fail trước replay |
| Unknown StrategyVersion | Fail candidate, không fallback latest |
| Look-ahead access | Candidate fail có evidence |
| Missing required indicator | Fail trước event loop |
| Signal NaN/Inf/invalid action | Candidate fail isolated |
| No BBO crossing | Intent không fill theo expiry policy |
| Missing BBO và fallback disabled | Fail rõ, không candle-fill ngầm |
| Candle chạm SL và TP | Dùng persisted `intrabar_priority` |
| Strategy timeout/exception | Candidate fail; worker/run tiếp tục theo isolation |
| Worker mất lease | Fenced writes match 0; worker dừng |
| Persist result fail | Không emit completed event |
| Cancellation | Persist cancelled at safe boundary; không rank partial result |

## Ràng buộc

- Chỉ closed candles trong backtest.
- Chronological deterministic replay, no look-ahead.
- Exact immutable strategy/dataset/execution/evaluator fingerprints.
- One-net LONG/SHORT, fixed-notional MVP.
- Fee/spread/slippage/gross/net PnL explicit.
- SL/TP nullable contract explicit.
- Engine không tính evaluation/rank.
- Go không có Backtest Engine/Worker/domain-table write.

## Tiêu chí chấp nhận

- [ ] AC-01: Same snapshot chạy hai lần cho byte-equivalent facts/metrics đến precision contract.
- [ ] AC-02: Future candle/BBO/indicator access bị chặn.
- [ ] AC-03: BBO BUY=ask, SELL=bid và event ordering pass hand-calculated fixtures.
- [ ] AC-04: LONG/SHORT open/close/reverse pass fixtures.
- [ ] AC-05: Missing crossing không tạo phantom fill.
- [ ] AC-06: Candle fallback chỉ chạy khi snapshot cho phép và provenance ghi rõ.
- [ ] AC-07: SL/TP both-hit obey `intrabar_priority` fixture.
- [ ] AC-08: Risk disabled trả `sl_price=null`, `tp_price=null`; UI hiển thị `N/A`.
- [ ] AC-09: Trade có đủ symbol/currency/time/side/notional/price/SL/TP/cost/gross/net fields.
- [ ] AC-10: Cost breakdown không double-count spread/slippage.
- [ ] AC-11: Worker crash/takeover không duplicate/overwrite result.
- [ ] AC-12: Completion state và outbox commit atomic.
- [ ] AC-13: Realtime/backtest parity pass cùng StrategyVersion/context fixture.
- [ ] AC-14: Architecture test chứng minh Go không implement/call Backtest Engine.
