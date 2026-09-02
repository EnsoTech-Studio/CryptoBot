# Đặc tả: Python Strategy Registry và Runtime

Trạng thái: Python canonical  
Owner: Python `research`  
Code seam hiện có: `app/domain/strategy/contract.py`, `registry.py`, `plugins/`

## Mô tả

Strategy Registry là extension seam duy nhất cho strategy execution. Registry resolve
immutable `(strategy_id, version)` thành một instance mới, stateless cho mỗi run. Python
Strategy Runtime này được dùng chung bởi realtime signal/overlay và backtest, vì vậy không
có Go strategy runtime hoặc một bản port thứ hai.

Go chỉ:

- Expose/proxy public catalog/query qua authenticated edge.
- Cung cấp normalized Candle/BBO qua internal Market contract.
- Fan-out persisted result/progress event tới browser.

Go không resolve strategy, tính indicator/signal, load plugin hoặc ghi strategy table.

## Contract

Canonical Python protocol:

```python
from dataclasses import dataclass, field
from typing import Any, Protocol

@dataclass
class Definition:
    strategy_id: str
    version: str
    family: str | None = None
    parameters_schema: Any | None = None
    input_requirements: list[str] = field(default_factory=list)
    overlay_types: list[str] = field(default_factory=list)
    warm_up_candles: Any | None = None
    is_composite: bool = False
    display_name: str = ""
    description: str = ""
    code_fingerprint: str | None = None

@dataclass
class AnalysisContext:
    provider: str
    symbol: str
    timeframe: str
    candles: "CausalCandles"
    index: int
    indicators: "IndicatorView"
    news_sentiment: "NewsSentimentWindow | None" = None
    params: dict[str, Any] = field(default_factory=dict)

@dataclass
class Signal:
    action: str
    confidence: float | None = None
    price: float | None = None
    signed_size: float | None = None
    evidence: Any | None = None

class Strategy(Protocol):
    def definition(self) -> Definition: ...
    def analyze(self, context: AnalysisContext) -> Signal: ...
```

Runtime numeric type là Python `float`/float64 theo `python-research.md`. Serialization,
rounding và display rules không được thay đổi semantics bên trong runtime.

Registry contract:

```python
Factory = Callable[[], Strategy]


class Registry:
    def register(self, factory: Factory) -> None: ...
    def resolve(self, strategy_id: str, version: str) -> Strategy: ...
    def list(self) -> list[Definition]: ...
```

Invariants:

- Key duy nhất là `(strategy_id, version)`.
- Duplicate registration fail startup; không last-write-wins.
- `resolve()` trả fresh instance để không rò mutable state giữa run.
- `list()` có order deterministic.
- Parameter/input/overlay metadata do plugin khai báo; UI/search không hard-code ID.
- Strategy chỉ thấy causal `AnalysisContext`, không DB/network/filesystem/service locator.

`Strategy` protocol không bắt buộc `requirements(params)`, nhưng các plugin có tham số
động đều cung cấp method này. `DeterministicEngine` gọi method nếu có; nếu không thì
dùng `Definition.input_requirements`. `warm_up_candles` cũng là callable theo params,
không phải field số cố định.

## Ba admission mode

### A. Built-in trusted Python plugin

Code-reviewed plugin trong `app/domain/strategy/plugins/`, register qua package catalog và
load khi process start. Đây là đường dành cho MA, EMA, RSI, Bollinger, Support/Resistance,
News Sentiment, MACD và composite root hiện có.

### B. Approved DSL-backed strategy

Declarative `StrategySpec` đã validate, compile/policy/sandbox test và human approve có thể
được safe runtime resolve bằng versioned compiler/interpreter semantics. Runtime không eval
raw source hoặc user text. Fingerprint gồm spec hash + compiler version + policy version.

### C. Advanced custom Python plugin

Generated/repaired source chỉ là draft cho PR/build/deploy. Sau review và CI, trusted artifact
được đóng vào image, register ở startup. Không hot-load arbitrary source vào process production.

| Mode | Dynamic sau approval | Cần deploy | Trust boundary |
|---|---:|---:|---|
| Built-in plugin | no | yes | Code review + CI + image |
| DSL-backed | yes, qua safe compiler/interpreter | no | Schema/policy/sandbox/approval |
| Custom Python | no | yes | Policy/sandbox + human PR/CI/image |

## Plugin catalog

`app/domain/strategy/plugins/catalog.py::register_all()` là bootstrap seam. Registry hiện
đăng ký các implementation:

- `ma_cross@v1`, `ema_cross@v1`: `MovingAverageCross`.
- `macd@v1`: `MACDStrategy`.
- `rsi@v1`: `RSIStrategy`.
- `bollinger@v1`: `BollingerStrategy`.
- `support_resistance@v1`: `SupportResistanceStrategy`.
- `smc@v1`: `SMCMarketStructureStrategy`, BOS-only causal implementation.
- `news_sentiment@v1`: `NewsSentimentStrategy`.
- `composite@v1`: `CompositeRoot` registry marker; engine owns child combination.

SMC đầy đủ (order block/liquidity modules) vẫn là target gap; `smc@v1` hiện có code
nhưng chỉ biểu diễn causal break-of-structure, không phải full SMC.

## Thêm MACD

Scenario modifiability canonical:

```text
app/domain/strategy/plugins/macd.py
tests/test_indicators_plugins.py
```

Plugin implement `definition()` + `analyze()`, sau đó được package catalog đăng ký. Không sửa
Backtest Engine, Evaluator, Ranking, Go API schema hoặc frontend strategy switch. Nếu catalog
vẫn cần một dòng import/register trong implementation hiện tại, đó là package bootstrap change,
không phải core-engine branching; target có thể chuyển sang entry-point/manifest discovery khi
chi phí vận hành hợp lý.

## Luồng chính

1. Python API/worker startup xây `default_registry()`.
2. Catalog register từng factory; duplicate key fail-fast. Metadata validation của request/run nằm ở các boundary khác.
3. Public catalog request đi Browser -> Go -> signed Python query.
4. Python trả normalized metadata; Go chỉ map envelope/error.
5. Experiment snapshot lưu exact strategy ID/version/params/spec/artifact fingerprint.
6. Worker resolve exact version thành fresh instance.
7. Indicator service precompute declared requirements bằng causal views.
8. Runtime gọi `analyze(context)` theo chronological event loop.
9. Backtest engine giữ BUY/SELL có price dương; HOLD không tạo signal/order. Confidence/evidence
được lưu nếu plugin trả về, chưa có một validator class riêng.
10. Realtime overlay và backtest dùng cùng steps 6-9.

## Parameter và compatibility rules

- Parameter schema versioned, reject unknown field mặc định.
- Default được materialize vào snapshot; runtime không đọc "latest default".
- Version không được đổi semantics sau khi đã có experiment reference.
- Sửa semantics tạo version mới và code/spec fingerprint mới.
- Plugin chỉ dùng indicator key đã khai báo.
- Warmup là deterministic function của materialized params.
- Một StrategyVersion chỉ published khi exact authoring review fingerprint đã approved.

## Causality và purity

`AnalysisContext` không expose raw list có thể index tương lai. `CausalCandles` và
`IndicatorView` chỉ cho truy cập tại hoặc trước `index`; reject negative index, slice, `len()`
hoặc `t+1` semantics có thể leak future.

Strategy không được:

- Query DB/network hoặc đọc system clock/random global.
- Ghi global mutable state.
- Tự chạy backtest/evaluation/ranking.
- Gọi Go/public API.
- Import AI/model adapter.
- Emit exchange order.

## Kịch bản lỗi

| Tình huống | Phản ứng |
|---|---|
| Duplicate `(id,version)` | Fail startup/readiness với clear conflict |
| Unknown strategy/version | `UNKNOWN_STRATEGY`, không fallback latest |
| Invalid metadata/schema | Fail registration trước serve traffic |
| Invalid parameter | Reject experiment/draft trước enqueue |
| Missing indicator requirement | Candidate/run fail có evidence; không tính on-the-fly sai lệch |
| Look-ahead access | `LookAheadError`, candidate fail isolated |
| NaN/Inf/invalid action | Signal validation fail |
| Plugin exception/timeout | Candidate fail; worker lease/retry policy giữ run |
| Artifact fingerprint mismatch | Fail-fast, không chạy version không tái lập được |
| Custom draft chưa deploy | Không xuất hiện trong production Registry |

## Ràng buộc

- Python Registry là canonical duy nhất.
- Realtime/backtest parity test là bắt buộc.
- Strategy execution no-network/no-DB/pure theo injected context.
- Registry list/resolve deterministic.
- Built-in/custom plugin chạy như trusted code chỉ sau review/build/deploy.
- DSL strategy không thực thi raw arbitrary Python.
- Version/fingerprint/provenance immutable sau first experiment reference.

## Tiêu chí chấp nhận

- [ ] AC-01: `default_registry().list()` deterministic và không duplicate key.
- [ ] AC-02: Resolve unknown exact version fail, không fallback latest.
- [ ] AC-03: Mỗi resolve trả fresh instance, không leak state giữa replay.
- [ ] AC-04: Plugin không có DB/network/filesystem dependency trong purity test.
- [ ] AC-05: Look-ahead attempts bị chặn ở causal view.
- [ ] AC-06: Invalid action/NaN/Inf bị signal validator từ chối.
- [ ] AC-07: MA, RSI, Bollinger, Support/Resistance có metadata và fixture test.
- [ ] AC-08: Thêm MACD không sửa Backtest/Evaluator/Ranking/Go/UI core branching.
- [ ] AC-09: Public catalog đi qua Go nhưng source of truth là Python.
- [ ] AC-10: Realtime/backtest tạo cùng signal với cùng context/version.
- [ ] AC-11: Approved DSL fingerprint resolve được mà không eval raw source.
- [ ] AC-12: Custom Python draft không visible trước PR/build/deploy.

## Implementation status

Python Registry/Strategy protocol và plugin catalog đã có dưới `app/domain/strategy/`.
DSL authoring admission, immutable publish repository và custom-code deployment workflow vẫn
là target gap, được kiểm soát bởi `strategy-authoring.md` và `agent-architecture.md`.
