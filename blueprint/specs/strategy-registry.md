# Đặc tả: Strategy Registry & Plugin Architecture

## Mô tả

Đây là **lõi khả năng mở rộng** của toàn hệ thống. Đề bài §12 và §41 kiểm tra trực tiếp phần này: giảng viên có thể yêu cầu thêm `MACDStrategy` tại chỗ, và chất lượng kiến trúc được đo bằng **số component phải sửa**.

Module gồm 3 phần:

- **`Strategy` contract** — interface mọi strategy phải implement: `definition()` trả metadata, `analyze(ctx)` trả `Signal`.
- **`StrategyRegistry`** — map `(strategy_id, version) → class`, tự đăng ký qua decorator `@register_strategy`, auto-discovery mọi module trong package `plugins/`.
- **`AnalysisContext`** — cấu trúc dữ liệu duy nhất strategy được phép thấy. Nó là cơ chế thực thi ranh giới "Strategy không truy cập Database" ở tầng kiểu dữ liệu, không phải ở tầng nhắc nhở trong code review.

MVP có 5 plugin: `ma_cross`, `rsi`, `bollinger`, `support_resistance`, `news_sentiment`. Plugin thứ 6 (`macd`) được thêm **trong lúc demo** để chứng minh scenario §41.

Đặc biệt phải đảm bảo:

- Thêm strategy mới = **1 file mới, 0 dòng sửa** ở Registry, Combiner, BacktestEngine, Evaluator, RankingService, Go API, DB schema, UI, CandidateGenerator.
- **Không tồn tại** `if strategy_id == "ma"` ở bất kỳ đâu ngoài chính plugin đó.
- Strategy chạy được trong môi trường **không có PostgreSQL, không có network**.
- Strategy lỗi (exception, vòng lặp vô hạn) **không** giết worker và **không** giết search run.
- Sửa code strategy mà quên bump version → **fail fast lúc startup**, không chạy với provenance sai.

## Contract

```python
# app/domain/strategy/contract.py
class Strategy(Protocol):
    def definition(self) -> StrategyDefinition: ...
    def analyze(self, ctx: AnalysisContext) -> Signal: ...


@dataclass(frozen=True)
class StrategyDefinition:
    strategy_id: str                       # 'rsi' — ổn định, không đổi
    version: str                           # '1.0.0' — semver, append-only
    family: Literal["trend", "momentum", "volatility", "structure", "information"]
    parameters_schema: Mapping[str, Any]   # JSON Schema → validate + sinh form UI
    input_requirements: Sequence[str]      # ['candles.close', 'indicator.rsi']
    overlay_types: Sequence[str]           # ['rsi', 'buy_signal', 'sell_signal']
    warm_up_candles: Callable[[Mapping[str, Any]], int]
    display_name: str = ""
    description: str = ""


@dataclass(frozen=True)
class AnalysisContext:
    symbol: str
    timeframe: Timeframe
    candles: Sequence[Candle]                          # CHỈ tới index — không có nến tương lai
    index: int                                         # candles[index] là "bây giờ"
    indicators: IndicatorView                          # causal view — chặn đọc > index
    news_sentiment: NewsSentimentWindow | None
    params: Mapping[str, Any]                          # đã validate theo parameters_schema


@dataclass(frozen=True)
class Signal:
    action: Literal["BUY", "SELL", "HOLD"]
    confidence: float | None = None                    # 0..1
    evidence: Mapping[str, Any] | None = None          # {'rsi': 72.4} → ghi vào run_signals
```

**Năm thứ `AnalysisContext` cố ý KHÔNG có:**

| Không có                | Nếu có thì sao                                                                        |
| ----------------------- | ------------------------------------------------------------------------------------- |
| DB session / repository | Strategy query SQL trực tiếp → anti-pattern §44; và không test được offline           |
| HTTP client             | Strategy gọi Binance → mỗi strategy tự fetch, rate limit vỡ, backtest không determinism |
| Nến sau `index`         | Look-ahead bias (R3) — kết quả đẹp giả tạo, toàn bộ Leaderboard vô nghĩa               |
| **Giá trị indicator sau `index`** | Cùng một look-ahead nhưng **không gây lỗi**: `rsi_14[t+1]` tính từ `close[t+1]`, nên đọc nó tương đương đọc giá tương lai. Đây là lý do `indicators` là `IndicatorView`, không phải `Mapping[str, Sequence[float]]` — xem `design.md` §5.2.1 |
| Thời gian hệ thống      | `datetime.now()` trong strategy làm backtest không tái lập được                        |

> **Đây là điểm thiết kế quan trọng nhất của file này.** Ranh giới được thực thi bằng **cái mà kiểu dữ liệu không cho phép**, không bằng quy ước. Một dev mới không cần đọc tài liệu để biết không được query DB trong strategy — họ đơn giản là không có session để query.

> **`IndicatorView` chặn bốn đường, không chỉ một.** `ctx.indicators["rsi_14"]` trả về một `CausalSeries`: `[t+1]` → `LookAheadError`; `[-1]` quy về giá trị **tại `index`** chứ không phải cuối dataset; `len()` trả `index + 1` nên `[len(s)-1]` cũng an toàn; `slice` bị clamp về `[0, index]`. Bốn đường này là bốn cách viết tự nhiên mà một plugin vô tình dùng — và cả bốn đều trả về dữ liệu thật nếu view không chặn.

## Luồng chính

### A. Đăng ký strategy lúc startup

```mermaid
sequenceDiagram
    autonumber
    participant BOOT as App startup
    participant PKG as plugins/__init__.py
    participant MOD as ma_cross.py · rsi.py · ...
    participant REG as StrategyRegistry
    participant DB as strategy_definitions<br/>strategy_versions

    BOOT->>PKG: import app.domain.strategy.plugins
    PKG->>PKG: pkgutil.iter_modules(__path__)
    loop mỗi module tìm thấy
        PKG->>MOD: import_module(name)
        MOD->>REG: @register_strategy áp dụng lúc định nghĩa class
        REG->>REG: d = cls().definition()
        REG->>REG: validate metadata (schema hợp lệ? warm_up khai báo?)
        alt (strategy_id, version) đã tồn tại
            REG-->>BOOT: DuplicateStrategyError → FAIL STARTUP
        end
        REG->>REG: _REGISTRY[(id, version)] = cls
    end

    BOOT->>REG: all_definitions()
    REG-->>BOOT: 5 definition
    BOOT->>BOOT: tính code_fingerprint cho từng plugin
    BOOT->>DB: SELECT code_fingerprint WHERE (strategy_id, version)
    alt fingerprint trong DB KHÁC fingerprint thực tế
        BOOT-->>BOOT: FAIL STARTUP<br/>"strategy rsi@1.0.0 changed, bump version"
    else version mới (chưa có trong DB)
        BOOT->>DB: INSERT strategy_definitions (nếu chưa có) + strategy_versions
    else khớp
        BOOT->>BOOT: OK
    end
```

`register_strategy` (đầy đủ):

```python
# app/domain/strategy/registry.py
_REGISTRY: dict[tuple[str, str], type[Strategy]] = {}

def register_strategy(cls: type[Strategy]) -> type[Strategy]:
    d = cls().definition()
    _validate_definition(d)                # schema hợp lệ, warm_up khai báo, family ∈ enum
    key = (d.strategy_id, d.version)
    if key in _REGISTRY:
        raise DuplicateStrategyError(f"{key} đã được đăng ký bởi {_REGISTRY[key].__name__}")
    _REGISTRY[key] = cls
    return cls

def resolve(strategy_id: str, version: str) -> type[Strategy]:
    try:
        return _REGISTRY[(strategy_id, version)]
    except KeyError:
        raise UnknownStrategyError(strategy_id, version)   # lỗi TƯỜNG MINH, không nhánh else âm thầm

def all_definitions() -> list[StrategyDefinition]:
    return [cls().definition() for cls in _REGISTRY.values()]
```

`plugins/__init__.py` (đây là chỗ "tự xuất hiện" xảy ra):

```python
import pkgutil, importlib
for _, name, _ in pkgutil.iter_modules(__path__):
    importlib.import_module(f"{__name__}.{name}")
```

> **Vì sao auto-discovery, không danh sách tường minh.** Một `STRATEGIES = [MAStrategy, RSIStrategy, ...]` sẽ hoạt động, nhưng nó là **một chỗ phải cập nhật** khi thêm plugin — và vì thế là một chỗ để quên. Với `iter_modules`, không có danh sách nào tồn tại nên không có gì để quên. Đánh đổi: thứ tự import không xác định (chấp nhận được vì registry là dict, không phụ thuộc thứ tự) và một module lỗi syntax sẽ fail startup (đó là hành vi mong muốn — fail fast).

### B. Precompute indicator theo `input_requirements`

```mermaid
sequenceDiagram
    autonumber
    participant EXS as ExperimentService
    participant REG as StrategyRegistry
    participant IND as IndicatorLibrary

    EXS->>REG: resolve từng child trong candidate_definition
    REG-->>EXS: [MAStrategy@1.0.0, RSIStrategy@1.0.0, SupportResistanceStrategy@1.0.0]
    EXS->>EXS: union input_requirements của tất cả child
    Note over EXS: {'candles.close', 'indicator.sma', 'indicator.rsi', 'indicator.sr_zone'}
    EXS->>EXS: gom tham số · sma cần 20 và 50 · rsi cần 14 · sr cần lookback 80
    EXS->>IND: precompute(candles, spec)
    IND-->>EXS: {'sma_20': [...], 'sma_50': [...], 'rsi_14': [...], 'sr_zone_80': [...]}
    Note over IND: Tính MỘT LẦN cho cả run.<br/>Nếu mỗi strategy tự tính trong analyze():<br/>20.000 nến × 3 strategy = 60.000 lần tính SMA
    EXS->>EXS: warm_up_end = max(child.warm_up_candles(params))
```

Ba lý do `input_requirements` tồn tại trong metadata thay vì để engine tự suy ra:

1. **Precompute cần biết trước.** Engine phải biết tính gì **trước khi** vào vòng lặp. Suy ra từ thân hàm `analyze()` là không khả thi.
2. **Validate được.** Strategy khai báo cần `indicator.rsi` nhưng `IndicatorLibrary` không có → phát hiện lúc startup, không phải lúc chạy candidate thứ 300.
3. **`news_sentiment` là dependency có điều kiện.** `NewsSentimentStrategy` khai báo `input_requirements=['news.sentiment_1h']`; engine biết phải nạp `NewsSentimentWindow`. Strategy technical-only không khai báo → engine không truy vấn news → backtest technical chạy được khi news pipeline chết.

### C. Chạy strategy trong sandbox

Trước khi nói cơ chế, phải nói rõ **mô hình tin cậy**, vì nó quyết định cơ chế nào là đủ:

> **Plugin là trusted code, không phải untrusted input.** Strategy được thêm bằng cách commit file vào `plugins/` rồi deploy — không có đường nào để người dùng upload code qua UI/API (ADR-002; `exec()` trên code do user gửi là RCE). Vì vậy mục tiêu của sandbox **không** phải chống code cố tình phá hoại (điều đó cần seccomp/container per-call, và vô nghĩa khi kẻ tấn công đã có quyền commit). Mục tiêu là: **một plugin có bug không được làm chết cả search run**. Bug thực tế cần chặn là vòng lặp `while` sai điều kiện, đệ quy không đáy, `IndexError`, chia cho 0 — không phải `os.fork()` bomb.

Với mục tiêu đó, có 3 tầng phòng thủ, mỗi tầng chặn một loại bug mà tầng dưới không chặn được:

| Tầng | Cơ chế | Chặn được | **Không** chặn được |
| ---- | ------ | --------- | ------------------- |
| 1 | `SIGALRM` soft deadline 1 s / call | Vòng lặp Python thuần, đệ quy sâu, `time.sleep` dài | Vòng lặp bên trong C extension đang giữ GIL |
| 2 | Supervisor `SIGKILL` child process | **Mọi** thứ tầng 1 bỏ sót, kể cả C loop và deadlock | — |
| 3 | `backtest_jobs.lease_expires_at` 120 s | Cả worker process biến mất (OOM-kill, container restart) | — |

**Tầng 1 — `SIGALRM` trong process chạy backtest**

```python
# app/domain/backtest/sandbox.py
import signal
from contextlib import contextmanager

class StrategyTimeout(Exception): ...

def _on_alarm(signum, frame):
    # Python kiểm tra signal giữa các bytecode → exception này CẮT được
    # `while True: pass`. Nó KHÔNG cắt được C call đang giữ GIL.
    raise StrategyTimeout()

@contextmanager
def soft_deadline(seconds: float):
    prev_handler = signal.signal(signal.SIGALRM, _on_alarm)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)      # luôn tắt, kể cả khi raise
        signal.signal(signal.SIGALRM, prev_handler)
```

Ba giới hạn của tầng này, ghi rõ để không ai tưởng nó là bảo đảm tuyệt đối:

1. **Chỉ hoạt động trên main thread của process** (`signal.signal` raise `ValueError` ở thread khác). Vì vậy backtest **phải** chạy trên main thread của process con — đây là một ràng buộc thiết kế, không phải chi tiết cài đặt.
2. **Chỉ hoạt động trên Unix.** Container là `python:3.12-slim` (Linux) nên production ổn. Trên Windows dev, `soft_deadline` degrade thành no-op và log WARN một lần lúc startup — tầng 2 vẫn hoạt động, chỉ là timeout thô hơn.
3. **Không cắt được C extension đang giữ GIL.** `numpy.sort` trên mảng khổng lồ, hay regex catastrophic backtracking, sẽ chạy tới khi xong. Đây chính xác là lý do tầng 2 tồn tại.

**Tầng 2 — worker là supervisor, backtest chạy trong process con**

```python
# app/worker.py (trích)
import multiprocessing as mp

HARD_LIMIT_SEC = 90          # < lease 120 s, để supervisor kịp ghi trạng thái

def run_job(job) -> None:
    ctx = mp.get_context("spawn")             # spawn, không fork: state sạch, deterministic
    q = ctx.Queue(maxsize=1)
    child = ctx.Process(target=_child_entry, args=(job.experiment_id, q), daemon=True)
    child.start()
    child.join(timeout=HARD_LIMIT_SEC)

    if child.is_alive():
        child.kill()                          # SIGKILL — không thể bị bắt hay bỏ qua
        child.join(timeout=5)
        metrics.strategy_hard_killed()
        fail_job(job, error_code="backtest_hard_timeout", retryable=False)
        return

    if child.exitcode != 0:                   # OOM-kill (-9), segfault, exception chưa bắt
        fail_job(job, error_code=f"worker_child_exit_{child.exitcode}", retryable=True)
        return

    commit_result(job, q.get_nowait())        # chỉ commit khi child kết thúc sạch
```

Bốn quyết định trong đoạn này đáng giải thích:

- **`spawn`, không `fork`.** `fork` copy toàn bộ state của supervisor gồm connection pool PostgreSQL — hai process dùng chung socket sẽ làm hỏng protocol theo cách rất khó debug. `spawn` tốn ~200 ms khởi động interpreter, nhưng một backtest mất 2–40 s nên chi phí đó là 0.5–10%.
- **`HARD_LIMIT_SEC = 90 < lease 120 s.** Thứ tự này là bắt buộc: supervisor phải kịp giết child, ghi `error_code` và `fail_job` **trước khi** lease hết hạn. Nếu ngược lại (`hard_limit > lease`), một worker khác sẽ nhận cùng job trong khi child cũ vẫn đang chạy → hai backtest song song cho một experiment.
- **`retryable=False` cho `backtest_hard_timeout`.** Timeout do plugin bug thì retry 3 lần chỉ đốt thêm 270 s. Ngược lại `worker_child_exit` (OOM, container bị siết memory) **là** retryable vì lần sau có thể có RAM.
- **Chỉ commit khi `exitcode == 0`.** Trùng với ràng buộc "không partial commit" ở `specs/backtest.md` — child bị `SIGKILL` không commit được gì, và đó là hành vi đúng.

**Trong process con**, `_safe_analyze` bọc từng lời gọi plugin:

```python
def _safe_analyze(self, strategy, ctx, sid: str, ver: str) -> Signal:
    started = monotonic()
    try:
        with soft_deadline(self.per_call_timeout):        # 1.0 s
            sig = strategy.analyze(ctx)
    except StrategyTimeout:
        self.metrics.strategy_timeout(sid)
        raise StrategyFailure(sid, ver, "strategy_timeout")
    except LookAheadError as exc:                        # §5.2.1 — bug nghiêm trọng của plugin
        self.metrics.strategy_lookahead(sid, ver)
        log.error("strategy_lookahead", strategy=f"{sid}@{ver}", detail=str(exc))
        raise StrategyFailure(sid, ver, "strategy_lookahead") from exc
    except Exception as exc:                              # ZeroDivisionError, IndexError, ...
        self.metrics.strategy_error(sid, ver)
        log.warning("strategy_raised", strategy=f"{sid}@{ver}",
                    error_type=type(exc).__name__, candle_index=ctx.index)
        raise StrategyFailure(sid, ver, "strategy_exception") from exc

    if sig.action not in ("BUY", "SELL", "HOLD"):         # plugin trả rác
        raise StrategyFailure(sid, ver, "invalid_signal")
    self.metrics.observe_analyze(sid, monotonic() - started)
    return sig
```

`StrategyFailure` được bắt ở biên vòng lặp backtest: `backtest_runs.status='failed'` + `error_code`, `search_candidates.status='failed'` + `failure_reason`. **Search run tiếp tục** với candidate kế tiếp.

> **Vì sao `per_call_timeout` là 1 giây, không 30 giây.** `analyze()` được gọi một lần **mỗi nến**. Với 20.000 nến, timeout 30 s/call nghĩa là một plugin xấu có thể chạy 166 giờ trước khi bị dừng — và tầng 2 sẽ giết nó ở giây thứ 90 mà không ai biết candidate nào có vấn đề. 1 giây/call vẫn rất rộng cho một hàm chỉ đọc vài phần tử mảng, và nó cho `error_code='strategy_timeout'` **kèm `strategy_id`** thay vì một cái `backtest_hard_timeout` mù.

> **Chi phí của `setitimer`.** Đặt và tắt itimer là 2 syscall mỗi lời gọi `analyze()`. Với 20.000 nến × 3 child = 120.000 syscall ≈ **60–120 ms cho cả run** (2–40 s). Chấp nhận được. Nếu về sau đo được đây là bottleneck: đặt deadline **một lần cho cả nến** (bao cả 3 child) thay vì mỗi child — mất khả năng chỉ ra child nào timeout, nên chỉ làm khi có số đo.

**Tầng 3** là `lease_expires_at` đã có ở `specs/experiment.md`: nếu cả worker process biến mất (OOM-kill toàn container, node restart) thì không ai ghi được `fail_job`, và lease hết hạn sau ≤ 120 s đưa job về `queued` với `attempt += 1`.

### D. Thêm strategy mới — toàn bộ diff (demo S3)

```python
# app/domain/strategy/plugins/macd.py   ← FILE MỚI DUY NHẤT
@register_strategy
class MACDStrategy:
    def definition(self) -> StrategyDefinition:
        return StrategyDefinition(
            strategy_id="macd",
            version="1.0.0",
            family="trend",
            display_name="MACD Crossover",
            parameters_schema={
                "fast_period":   {"type": "integer", "minimum": 2, "maximum": 100, "default": 12},
                "slow_period":   {"type": "integer", "minimum": 3, "maximum": 400, "default": 26},
                "signal_period": {"type": "integer", "minimum": 2, "maximum": 100, "default": 9},
            },
            input_requirements=["candles.close", "indicator.macd"],
            overlay_types=["macd_line", "macd_signal", "buy_signal", "sell_signal"],
            warm_up_candles=lambda p: p["slow_period"] + p["signal_period"],
        )

    def analyze(self, ctx: AnalysisContext) -> Signal:
        i = ctx.index
        if i < 1:
            return Signal("HOLD")
        macd, sig = ctx.indicators["macd_line"], ctx.indicators["macd_signal"]
        if None in (macd[i], sig[i], macd[i - 1], sig[i - 1]):
            return Signal("HOLD")
        if macd[i - 1] <= sig[i - 1] and macd[i] > sig[i]:
            return Signal("BUY", evidence={"macd": macd[i], "signal": sig[i]})
        if macd[i - 1] >= sig[i - 1] and macd[i] < sig[i]:
            return Signal("SELL", evidence={"macd": macd[i], "signal": sig[i]})
        return Signal("HOLD")
```

Sau khi restart, **8 thứ xảy ra tự động**:

| # | Kết quả                                             | Cơ chế                                              |
| - | --------------------------------------------------- | --------------------------------------------------- |
| 1 | MACD có trong registry                              | `iter_modules` + decorator                          |
| 2 | `strategy_definitions` + `strategy_versions` có row | Startup upsert từ `all_definitions()`               |
| 3 | `GET /api/v1/strategies` trả MACD                   | Handler trả `all_definitions()`                     |
| 4 | UI có form nhập 3 param với min/max/default đúng    | Form sinh từ `parameters_schema` (JSON Schema)      |
| 5 | MACD vào search space của Random Search             | `RandomSearchGenerator` đọc registry                |
| 6 | MACD vào nhóm `trend` của Domain-Guided Search      | `family="trend"`                                    |
| 7 | Engine precompute `macd_line`/`macd_signal`         | `input_requirements`                                |
| 8 | Chart vẽ được overlay MACD                          | `overlay_types` → `chart-overlays` endpoint         |

Điều kiện: `IndicatorLibrary` phải có `macd`. Nếu chưa có thì thêm 1 file `domain/indicator/macd.py` nữa — vẫn là 0 dòng sửa ở component hiện có, vì `IndicatorLibrary` cũng dùng registry pattern.

## Kịch bản lỗi

| Tình huống                                                          | Phản ứng                                                                                                |
| ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| Hai plugin cùng `(strategy_id, version)`                            | `DuplicateStrategyError` → **fail startup**. Không im lặng ghi đè (nếu ghi đè thì strategy nào thắng phụ thuộc thứ tự import — không xác định) |
| Sửa logic `rsi.py` mà giữ `version="1.0.0"`                         | `code_fingerprint` lệch → **fail startup** với thông báo "bump version". Đây là ADR-009                   |
| Refactor cosmetic (đổi tên biến, thêm comment)                      | Fingerprint tính trên source đã normalise (strip comment/docstring, chuẩn whitespace) → **không** fail   |
| `parameters_schema` không phải JSON Schema hợp lệ                   | `_validate_definition` reject → fail startup                                                            |
| Không khai báo `warm_up_candles`                                    | Fail startup. Không mặc định 0 (mặc định 0 tạo trade giả ở đầu dataset một cách âm thầm)                 |
| `family` không thuộc 5 giá trị enum                                 | Fail startup — vì Domain-Guided Search phân nhóm theo `family`                                            |
| `input_requirements` yêu cầu indicator không tồn tại                | Fail startup, liệt kê indicator khả dụng                                                                 |
| Client gửi `strategy_id` không có trong registry                    | `422 unknown_strategy` kèm danh sách khả dụng (lỗi ở tầng validate, không tới domain)                     |
| Client gửi `version` không tồn tại cho strategy có tồn tại          | `422 unknown_strategy_version` kèm các version khả dụng                                                   |
| Param sai kiểu / ngoài min-max                                      | `422` với `field` chỉ đúng param sai (validate bằng `parameters_schema`)                                  |
| `analyze()` raise `ZeroDivisionError`                               | Catch tại `_safe_analyze` → candidate `failed`, `failure_reason='strategy_exception'`. **Search run tiếp tục** |
| `analyze()` có `while True: pass` (Python thuần)                    | Tầng 1: `SIGALRM` sau 1 s → `StrategyTimeout` → candidate `failed`, `failure_reason='strategy_timeout'`. Worker **không** chết |
| `analyze()` treo trong C extension giữ GIL (numpy khổng lồ, regex backtracking) | Tầng 1 **không** cắt được. Tầng 2: supervisor `SIGKILL` child sau 90 s → `error_code='backtest_hard_timeout'`, `retryable=False`. Worker supervisor vẫn sống |
| Child process bị OOM-kill (`exitcode = -9`)                          | `error_code='worker_child_exit_-9'`, `retryable=True` — lần sau có thể có RAM. Khác với `hard_timeout` (không retry) |
| Cả worker process biến mất (container restart, node down)             | Tầng 3: `lease_expires_at` hết sau ≤ 120 s → job về `queued`, `attempt += 1` (`specs/experiment.md`) |
| Backtest chạy trên thread không phải main thread                      | `signal.signal` raise `ValueError` → fail fast lúc khởi tạo sandbox. Đây là ràng buộc thiết kế: backtest **phải** ở main thread của process con |
| Chạy trên Windows (dev)                                              | `soft_deadline` degrade thành no-op + log WARN **một lần** lúc startup. Tầng 2 vẫn hoạt động → timeout thô hơn (90 s) nhưng không mất bảo đảm |
| `analyze()` trả `"buy"` (chữ thường) hoặc `None`                    | `invalid_signal` → candidate `failed`. Không tự sửa thành `BUY` (che lỗi của plugin)                     |
| `analyze()` cố `ctx.candles[ctx.index + 5]`                         | `IndexError` — vì slice chỉ tới `index`. Look-ahead bị chặn ở tầng dữ liệu                                |
| `analyze()` cố `ctx.indicators["rsi_14"][ctx.index + 1]`            | `LookAheadError` → `failure_reason='strategy_lookahead'` + log **ERROR** (không WARN). Đây là bug làm sai kết quả, không chỉ làm fail một candidate (`design.md` §5.2.1) |
| `analyze()` cố gán `ctx.params["period"] = 99`                      | `FrozenInstanceError`/`TypeError` — `AnalysisContext` là frozen, `params` là Mapping read-only            |
| Plugin import `sqlalchemy` hoặc `httpx`                             | `tests/architecture/test_module_boundaries.py` **fail CI**                                                |
| Plugin file có syntax error                                         | Fail startup ở `import_module` — fail fast, không chạy với 4/5 strategy                                    |
| `NewsSentimentStrategy` chạy khi `ctx.news_sentiment is None`        | Trả `Signal("HOLD")`. **Không** raise, **không** coi `None` là `avg_score=0` (ADR-013: không fake dữ liệu) |

## Ràng buộc

**Tính đúng đắn**

- `analyze()` phải là **pure function**: cùng `AnalysisContext` → cùng `Signal`. Không I/O, không random không seed, không `datetime.now()`. Đây là điều kiện để backtest chạy 2 lần cho kết quả byte-identical.
- `AnalysisContext` là `frozen=True`; `candles` là read-only sequence; `indicators` là `IndicatorView` (chặn đọc > `index`).
- `candles` được slice `[:index+1]` và `indicators` được bọc `IndicatorView(raw, index)` ở tầng gọi — bảo đảm bằng code, không bằng quy ước.
- `strategy_versions` là **append-only**. Row đã được experiment tham chiếu không bao giờ UPDATE.
- `code_fingerprint = sha256(normalise(source_of_class))`. `normalise` strip comment/docstring và chuẩn hoá whitespace.
- **Thứ tự bắt buộc giữa các timeout**: `per_call_timeout` (1 s) < `HARD_LIMIT_SEC` (90 s) < `lease_expires_at` (120 s). Đảo thứ tự bất kỳ cặp nào sẽ tạo cửa sổ hai worker chạy cùng một experiment.

**Hiệu năng**

- `resolve()` là dict lookup: **O(1)**, < 1 µs.
- Indicator precompute **một lần** cho cả run, không tính trong `analyze()`.
- `analyze()` một nến: **< 100 µs** cho strategy đơn (mục tiêu; đo bằng `strategy_analyze_seconds`).
- Soft deadline mỗi call (`SIGALRM`): **1.0 s** (cấu hình được). Overhead 2 syscall/call ≈ 60–120 ms cho cả run 20.000 nến × 3 child.
- Hard limit của child process: **90 s** — phải nhỏ hơn `lease_expires_at` 120 s.
- `spawn` một child: ~**200 ms** khởi động interpreter, tức 0.5–10% của một backtest 2–40 s.
- Startup registry (5 plugin): **< 200 ms**.

**Khả năng mở rộng**

- Thêm strategy = **1 file** trong `plugins/`. Kiểm chứng bằng `git diff --stat` (demo S3).
- Thêm strategy family mới = mở rộng enum `family` (Python `Literal` + DB `CHECK`) + cập nhật rule của `DomainGuidedGenerator`. Không đụng registry. Trước khi thêm, kiểm tra 5 family hiện có đã đủ chưa — `news_sentiment` thuộc `information`, không cần family riêng (`specs/sentiment.md` §D).
- `parameters_schema` là JSON Schema → UI sinh form tự động, không cần code UI cho từng strategy.
- SMC/Wyckoff cắm được vào `family="structure"` mà không cần contract mới (đề bài §11).

**Bảo mật**

- **Mô hình tin cậy: plugin là trusted code.** Không có cơ chế upload code strategy qua UI/API (`exec()` trên code do user gửi là RCE). Strategy thêm bằng code + deploy — lý do `Strategy Developer` nối nét đứt ở C4 Level 1 (`design.md` §2.1). Sandbox ở §C vì thế nhắm vào **bug**, không nhắm vào code cố tình phá hoại; chống code thù địch cần seccomp/container per-call và vô nghĩa khi kẻ tấn công đã có quyền commit.
- Plugin không có network/DB access trong `AnalysisContext` → một plugin lỗi không exfiltrate được dữ liệu qua context. (Nó vẫn `import` được thư viện bất kỳ — chặn việc đó là việc của `test_module_boundaries.py` ở CI, không của runtime.)
- `evidence` trong `Signal` được serialize vào `run_signals.child_signals` — validate là JSON-serializable, giới hạn kích thước 4 KB/signal để plugin không làm phình DB.

**Quan sát được**

- `strategy_analyze_errors_total{strategy_id,version}` counter
- `strategy_timeout_total{strategy_id}` counter — tầng 1 (`SIGALRM`)
- `strategy_hard_killed_total` counter — tầng 2 (`SIGKILL` child); tăng nghĩa là có plugin mà tầng 1 không chặn được
- `strategy_lookahead_total{strategy_id,version}` counter — **phải luôn bằng 0**; khác 0 là bug làm sai kết quả, cần alert
- `strategy_analyze_seconds{strategy_id}` histogram
- Log khi plugin lỗi có: `strategy_id@version`, `error_type`, `candle_index`, `correlation_id`

## Tiêu chí chấp nhận

- [ ] AC-01: Thêm `plugins/macd.py`, restart → `GET /api/v1/strategies` trả 6 strategy; `git diff --stat` cho thấy **1 file mới, 0 file core sửa**.
- [ ] AC-02: Sau AC-01, `strategy_definitions` và `strategy_versions` có row `macd@1.0.0` mà **không** chạy migration nào.
- [ ] AC-03: Sau AC-01, MACD xuất hiện trong search space của `RandomSearchGenerator` (chạy search 20 candidate, có ít nhất 1 candidate chứa `macd`).
- [ ] AC-04: Sau AC-01, UI render form MACD với 3 field đúng `min`/`max`/`default` từ `parameters_schema`, **không** có code UI riêng cho MACD.
- [ ] AC-05: `grep -rE '(strategy_id|strategy)\s*==\s*["'"'"']' app/ --include=*.py` chỉ khớp trong `plugins/` và `tests/`.
- [ ] AC-06: `test_strategy_purity.py` — patch `socket.socket` để raise, unset `DATABASE_URL` → cả 5 strategy vẫn `analyze()` thành công.
- [ ] AC-07: Tạo plugin `_evil_pyloop.py` với `while True: pass` trong `analyze()` → tầng 1 bắt: candidate `failed` với `failure_reason='strategy_timeout'` trong **≤ 2 s**; `strategy_timeout_total{strategy_id="_evil_pyloop"}` tăng 1; worker vẫn sống; search run chạy tiếp candidate sau.
- [ ] AC-07b: Tạo plugin `_evil_cloop.py` treo trong C extension giữ GIL (ví dụ `re.match` catastrophic backtracking, hoặc `numpy.sort` mảng 10⁹ phần tử) → tầng 1 **không** bắt được; tầng 2 `SIGKILL` child trong **≤ 95 s**; job `failed` với `error_code='backtest_hard_timeout'`, `retryable=False`, `attempt` **không** tăng lên 3; `strategy_hard_killed_total` tăng 1; **worker supervisor vẫn sống** và nhận job tiếp theo.
- [ ] AC-07c: Kiểm thứ tự timeout bằng config: `per_call_timeout < HARD_LIMIT_SEC < lease_ttl`. Đặt `HARD_LIMIT_SEC=150` (> lease 120) → app **fail startup** với thông báo nêu rõ cả 3 giá trị. (Không có kiểm tra này thì đảo thứ tự sẽ tạo cửa sổ hai worker chạy cùng một experiment mà không có triệu chứng.)
- [ ] AC-07d: `kill -9` child process từ bên ngoài giữa lúc backtest → supervisor thấy `exitcode = -9`, job `failed` với `retryable=True`, và bảng `trades` có **0 row** cho run đó (không partial commit).
- [ ] AC-08: Tạo plugin raise `ZeroDivisionError` → candidate `failed` với `strategy_exception`; log có `strategy_id@version` và `candle_index`.
- [ ] AC-09: Sửa 1 dòng logic trong `rsi.py` giữ nguyên version → startup **fail** với message chứa `rsi@1.0.0` và chữ "bump version".
- [ ] AC-10: Thêm comment vào `rsi.py` (không đổi logic) → startup **thành công**.
- [ ] AC-11: Hai plugin cùng khai báo `strategy_id="rsi", version="1.0.0"` → startup fail với `DuplicateStrategyError` nêu tên cả 2 class.
- [ ] AC-12: `POST /experiments` với `strategy_id="nonexistent"` → `422 unknown_strategy`, response có danh sách strategy khả dụng, **không** có stack trace.
- [ ] AC-13: `POST /experiments` với `rsi` và `period=1` (dưới `minimum: 2`) → `422` với `field="parameters.period"`.
- [ ] AC-14: Plugin thử `ctx.candles[ctx.index + 1]` → `IndexError` (chứng minh không có nến tương lai trong context).
- [ ] AC-14b: Plugin thử `ctx.indicators["rsi_14"][ctx.index + 1]` → `LookAheadError`; `[-1]` trả giá trị tại `index`; `len(series) == index + 1`; `series[:]` có đúng `index + 1` phần tử (bốn đường lách ở `design.md` §5.2.1 đều bị chặn).
- [ ] AC-14c: Plugin đọc indicator chưa khai báo trong `input_requirements` → `UnknownIndicatorError` liệt kê các indicator đang có, **không** phải `KeyError` trần.
- [ ] AC-15: `test_module_boundaries.py` — thêm `import httpx` vào một plugin → CI **fail**.
