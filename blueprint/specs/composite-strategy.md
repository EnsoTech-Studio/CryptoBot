# Đặc tả: Composite Strategy (Signal Combination)

## Mô tả

Composite Strategy là strategy virtual root kết hợp 2–5 child strategies thành
một `Signal`. Nó không biết cách child tính indicator; child không biết
combiner. Snapshot lưu toàn bộ child definitions, parameters, weights và policy
để candidate hash/provenance bất biến.

MVP có `weighted_vote` và `majority_vote`. Root `composite@1.0.0` không vào search
space và không được nested làm child của composite khác.

Đặc biệt phải đảm bảo:

- Weighted score deterministic, Decimal, threshold đối xứng.
- Child HOLD không tạo direction.
- Child lỗi không bị biến thành HOLD âm thầm.
- Composite không tự sizing/fill/position; Backtest Engine xử lý fixed notional.
- Sizing phải được chọn bởi `SizePolicy` tường minh trước khi tạo
  `OrderIntent`; combiner không được suy diễn quantity từ weighted score hoặc
  weighted price.
- Thêm combiner mới = file Go mới, không sửa Backtest/Evaluation/API/UI.

## Contract

```go
type ChildDefinition struct {
	StrategyID string
	Version    string
	Parameters Params
	Weight     decimal.Decimal
}

type CombinationPolicy struct {
	Policy    string // weighted_vote | majority_vote
	Threshold decimal.Decimal
	Encoding  string // versioned action encoding
}

type CompositeDefinition struct {
	StrategyID  string
	Version     string
	Children    []ChildDefinition
	Combination CombinationPolicy
}

type SignalCombiner interface {
	Combine(children []ResolvedSignal, policy CombinationPolicy) (strategy.Signal, error)
}
```

`CombinationPolicy` chỉ quyết định direction/price/evidence. Nó không thay thế
`SizePolicy`: MVP dùng `fixed_notional` từ immutable snapshot (`10 USDT` trong
fixture), còn policy khác phải được encode và validate trước khi BacktestEngine
tạo order. Vì vậy cùng một composite signal không thể âm thầm tạo quantity khác
giữa realtime paper và deterministic replay.

The Go skeleton owns these types in
`internal/domain/strategy/composite/contract.go`; it aliases the shared
strategy value objects and keeps combination algorithms deferred.

`ResolvedSignal` giữ child definition + signal để evidence tái tạo được:

```go
type ResolvedSignal struct {
	StrategyID string
	Version    string
	Weight     decimal.Decimal
	Signal     strategy.Signal
}
```

## Snapshot schema

```json
{
  "strategy_id": "composite",
  "version": "1.0.0",
  "children": [
    {"strategy_id":"ma_cross","version":"1.0.0","parameters":{"fast":20,"slow":50},"weight":"0.2"},
    {"strategy_id":"rsi","version":"1.0.0","parameters":{"period":14},"weight":"0.3"},
    {"strategy_id":"support_resistance","version":"1.0.0","parameters":{"lookback":80},"weight":"0.5"}
  ],
  "policy": {
    "name":"weighted_vote",
    "threshold":"0.3",
    "encoding":{"BUY":1,"HOLD":0,"SELL":-1}
  }
}
```

Canonical JSON sort key, normalize Decimal encoding, NFC-normalize strings.
Definition hash includes child order after canonical sort by `(strategy_id,
version, parameters, weight)` and full policy. Same semantic definition gives
same hash.

Validation:

- child count 2–5;
- no nested composite;
- each child resolves immutable registry version;
- weights `>= 0`, total weight `> 0`;
- threshold `[0,1]`;
- encoding contains exactly BUY/HOLD/SELL with `+1/0/-1`;
- duplicate exact child rejected; same strategy with different parameters valid;
- child BUY/SELL signal price and signed size validated before combination.

## Luồng chính

```mermaid
sequenceDiagram
    autonumber
    participant ENG as BacktestEngine
    participant REG as StrategyRegistry
    participant MA as MA Strategy
    participant RSI as RSI Strategy
    participant SR as Support/Resistance Strategy
    participant CMB as WeightedVoteCombiner
    participant SIG as run_signals

    Note over ENG,REG: resolve child versions once per run
    ENG->>REG: Resolve(children)
    REG-->>ENG: factories + immutable definitions
    ENG->>MA: Analyze(causal context)
    MA-->>ENG: Signal(BUY)
    ENG->>RSI: Analyze(causal context)
    RSI-->>ENG: Signal(SELL)
    ENG->>SR: Analyze(causal context)
    SR-->>ENG: Signal(BUY)
    ENG->>CMB: Combine(weighted children, policy)
    CMB->>CMB: score = (0.2 - 0.3 + 0.5) / 1.0 = 0.4
    CMB-->>ENG: Signal(BUY, confidence=0.4)
    ENG->>SIG: child signals + score + evidence
```

Warm-up bắt đầu tại `max(child warm_up_candles)`, không phải nến 0. Với
MA(50), RSI(14), SR(80), engine bắt đầu index 80.

## Weighted vote

```text
score = Σ(weight × encoding[action]) / Σ(weight)
BUY  nếu score > threshold
SELL nếu score < -threshold
HOLD còn lại
confidence = abs(score)
```

So sánh strict. `score == threshold` là HOLD. `threshold=0` hợp lệ: score
khác 0 quyết định, score 0 vẫn HOLD. Tie hoặc mọi child HOLD trả HOLD.

Weighted signal price chỉ lấy child non-HOLD có price:

```text
weighted_price = Σ(weight × child_price) / Σ(weight của child có price)
```

Child non-HOLD thiếu price là validation error, không silently drop. Composite
không tự resolve quantity; Backtest dùng `fixed_notional / limit_price` theo
execution snapshot.

Go-shaped implementation:

```go
func (WeightedVoteCombiner) Combine(children []ResolvedSignal, p CombinationPolicy) (strategy.Signal, error) {
	var totalWeight, score decimal.Decimal
	for _, child := range children {
		if child.Weight.IsNegative() { return strategy.Signal{}, ErrInvalidWeight }
		value := decimal.NewFromInt(int64(p.Encoding[child.Signal.Action]))
		totalWeight = totalWeight.Add(child.Weight)
		score = score.Add(child.Weight.Mul(value))
	}
	if totalWeight.IsZero() { return strategy.Signal{}, ErrZeroTotalWeight }
	score = score.Div(totalWeight)
	return signalFromScore(score, p.Threshold), nil
}
```

## Majority vote

Đếm action, chọn action có số vote cao nhất. Tie trả HOLD deterministic. Weight,
threshold không ảnh hưởng majority result nhưng vẫn nằm snapshot để provenance
đầy đủ.

## Evidence và storage

`run_signals.child_signals` ghi child action, confidence, price, evidence,
weight và composite score. Ghi cả HOLD để trả lời được cả “vì sao mua” và “vì
sao không mua”; bulk insert theo batch.

```json
{
  "children": {
    "ma_cross@1.0.0": {"action":"BUY","price":"118050"},
    "rsi@1.0.0": {"action":"SELL","price":"118050"},
    "support_resistance@1.0.0": {"action":"BUY","price":"118050"}
  },
  "score":"0.4",
  "action":"BUY"
}
```

## Kịch bản lỗi

| Tình huống | Phản ứng |
|---|---|
| 1 hoặc >5 child | `422 invalid_cardinality` |
| Child là composite | `422 nesting_too_deep` |
| Strategy/version không tồn tại | `422 unknown_strategy_version` |
| Duplicate exact child | `422 duplicate_child` |
| Weight âm/tổng zero | `422 invalid_weight` / `422 zero_total_weight` |
| Threshold ngoài `[0,1]` | `422 invalid_threshold` |
| Encoding thiếu action | `422 invalid_encoding` |
| Child non-HOLD thiếu price | `422 invalid_signal` |
| Child lỗi/timeout/look-ahead | Candidate failed; không coi child là HOLD |
| Mọi child HOLD | Composite HOLD, không tạo order |
| Majority tie | HOLD, không random |
| Same key order khác nhau | Cùng canonical hash |

## Ràng buộc

**Tính đúng đắn**

- `Combine` pure, không I/O/network/clock/random.
- Score/weight/threshold/price dùng Decimal.
- Strict threshold, đối xứng BUY/SELL.
- `warm_up_candles(composite) = max(child warm-up)`.
- Snapshot bất biến; đổi composite tạo experiment mới.
- Không branch theo strategy name trong core.

**Hiệu năng**

- Resolve child một lần/run, không một lần/candle.
- Indicator precompute theo union requirements.
- Combine 5 child mục tiêu < 50 µs, bulk-write evidence.

**Khả năng mở rộng**

- Combiner mới = một Go file đăng ký policy.
- Strategy mới = một plugin file theo `strategy-registry.md`.
- Nested composite là extension validator, không đổi Backtest/Evaluation contract.

## Tiêu chí chấp nhận

- [ ] AC-01: `{BUY, SELL, BUY}` với weights `{0.2,0.3,0.5}`, threshold `0.3` → score `0.4`, BUY.
- [ ] AC-02: Majority `{BUY, BUY, HOLD}` → BUY, confidence `2/3`.
- [ ] AC-03: Threshold `0.5` với cùng signals → HOLD, hash khác.
- [ ] AC-04: Canonical JSON key order khác nhau → cùng candidate hash.
- [ ] AC-05: Combiner mới chỉ thêm một Go file + test.
- [ ] AC-06: Threshold 0, score 0 → HOLD; score dương/âm khác 0 → direction tương ứng.
- [ ] AC-07: Child lỗi không bị biến thành HOLD; worker/search tiếp tục candidate kế tiếp.
- [ ] AC-08: Warm-up composite đúng max child requirement.
- [ ] AC-09: `run_signals.child_signals` tái tạo đúng score/action.
- [ ] AC-10: Composite không tự tạo fill/position; Backtest chịu trách nhiệm fixed notional.

---

Cross-reference: `design.md` §5.3–§5.4, §6.2, §8.1, ADR-002, ADR-003,
`specs/strategy-registry.md`, `specs/backtest.md`, `specs/search-loop.md`,
`specs/evaluation.md`.
