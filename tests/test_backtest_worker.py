"""Backtest worker/engine/evaluator acceptance tests.

Covers `specs/python-research.md` AC-01..AC-07 with fast synthetic replays, the
evaluator edge matrix from `specs/evaluation.md`, and the structural acceptance
for the `sol/2026-03-04` fixture (29 strict MA20/50 signals, 15 BUY / 14 SELL,
settled trades after final-BBO settlement). Synthetic fixtures use tiny MA
periods so every fill/cross condition is hand-controlled.
"""

from __future__ import annotations

import math
import threading
import time
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from uuid import uuid4

import pytest

from app.domain.backtest import ExperimentSnapshot, MarketSnapshot
from app.domain.common import (
    ACTION_BUY,
    ACTION_HOLD,
    ACTION_SELL,
    ERR_INSUFFICIENT_CANDLES,
    ERR_INVALID_SIGNAL,
    ERR_LOOK_AHEAD,
    ERR_MISSING_PRIOR_BBO,
    ERR_STRATEGY_EXCEPTION,
    ERR_UNKNOWN_STRATEGY,
    ERR_VALIDATION,
    EXIT_END_OF_SAMPLE,
    EXIT_SIGNAL,
    DomainError,
    LookAheadError,
)
from app.domain.evaluation import EvaluationInput, EvaluationPolicy
from app.domain.indicator import IndicatorView
from app.domain.job import BacktestJob
from app.domain.market import BBO, Candle, CausalCandles
from app.domain.strategy import AnalysisContext, Definition, Reference, Registry, Signal
from app.services.backtest_engine import DeterministicEngine, canonical_result_hash
from app.services.evaluator import DeterministicEvaluator

T0 = datetime(2026, 3, 4, tzinfo=UTC)


# ---------------------------------------------------------------------------
# synthetic harness
# ---------------------------------------------------------------------------


def candle(i: int, close: float) -> Candle:
    return Candle(
        provider="binance",
        symbol="SOLUSDT",
        timeframe="1m",
        open_time=T0 + timedelta(minutes=i),
        close_time=T0 + timedelta(minutes=i, seconds=59, milliseconds=999),
        open=close,
        high=close + 0.5,
        low=close - 0.5,
        close=close,
        volume=1.0,
    )


def quote(i: int, offset_ms: int, bid: float, ask: float, seq: int) -> BBO:
    return BBO(
        provider="binance",
        symbol="SOLUSDT",
        event_time=T0 + timedelta(milliseconds=i * 60_000 + offset_ms),
        bid=bid,
        bid_qty=1.0,
        ask=ask,
        ask_qty=1.0,
        update_id=None,
        source_sequence=seq,
    )


def snapshot(fast: int = 2, slow: int = 3, **overrides) -> ExperimentSnapshot:
    values = {
        "experiment_id": uuid4(),
        "owner_id": None,
        "strategy": Reference("ma_cross", "v1"),
        "candidate_definition": {"fast": fast, "slow": slow},
        "candidate_hash": "x" * 64,
        "market": MarketSnapshot(
            "test", 1, "binance", "SOLUSDT", "1m", T0, T0, 0, "h1", "h2"
        ),
        "initial_equity": 100.0,
        "fixed_notional": 10.0,
        "leverage": 1.0,
        "fee_bps": 10,
        "slippage_bps": 0,
        "fill_policy": "bbo_limit",
        "position_policy": "one_net_position",
        "open_position_at_end": "last_executable_bbo",
        "risk_policy": None,
    }
    values.update(overrides)
    return ExperimentSnapshot(**values)


def flat_quotes(minutes: int, bid: float, ask: float) -> list[BBO]:
    """One BBO per minute boundary (at open+1ms), constant prices."""
    return [quote(i, 1, bid, ask, i + 1) for i in range(minutes)]


def run(candles, quotes, snap=None):
    return DeterministicEngine().run(snap if snap is not None else snapshot(), candles, quotes)


def zigzag(n: int, period: int = 8, base: float = 100.0, amp: float = 5.0) -> list[float]:
    return [base + amp * math.sin(2 * math.pi * i / period) for i in range(n)]


# ---------------------------------------------------------------------------
# causal guards (R2 / AC-06 python spec)
# ---------------------------------------------------------------------------


def test_causal_candles_reject_future_read() -> None:
    candles = [candle(i, 100.0) for i in range(5)]
    window = CausalCandles(candles, 2)
    assert len(window) == 3
    assert window.index == 2
    with pytest.raises(LookAheadError):
        window.at(3)


def test_indicator_view_rejects_future_read() -> None:
    view = IndicatorView({"sma:2": [1.0, 2.0, 3.0]}, cursor=1)
    assert view.current("sma:2") == 2.0
    with pytest.raises(LookAheadError):
        view.at("sma:2", 2)
    with pytest.raises(DomainError):
        view.at("sma:999", 0)


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------


def test_registry_resolve_and_unknown() -> None:
    from app.domain.strategy.plugins.catalog import default_registry

    registry = default_registry()
    strategy = registry.resolve("ma_cross", "v1")
    assert strategy.definition().strategy_id == "ma_cross"
    with pytest.raises(DomainError) as excinfo:
        registry.resolve("nope", "v1")
    assert excinfo.value.code == ERR_UNKNOWN_STRATEGY


# ---------------------------------------------------------------------------
# event merge + crossing (AC-02, AC-03)
# ---------------------------------------------------------------------------


def _cross_closes() -> list[float]:
    # flat 100 (indices 0..3), jump to 110 (4..8), drop to 100 (9..13).
    # With fast=2/slow=3 the strict cross fires at candle 3 (SMA2 first sees
    # the jump): BUY limit = close[3] = 100; SELL at candle 9, limit 100.
    return [100.0] * 4 + [110.0] * 5 + [100.0] * 5


def test_buy_fills_on_next_bbo_after_candle_not_same_timestamp() -> None:
    closes = _cross_closes()
    candles = [candle(i, c) for i, c in enumerate(closes)]
    # BUY fires at candle 4 close (limit 110). The BBO at exactly the close
    # event time is applied BEFORE the intent exists (priority 0); if the
    # engine wrongly checked it after the candle, it would fill at 00:04:59.999.
    quotes = [
        quote(0, 0, 90.0, 95.0, 0),  # seed: prior BBO for the first marks
        quote(4, 59_999, 109.0, 110.0, 1),  # same ms as close event: NOT a fill source
        quote(4, 60_099, 98.0, 99.0, 2),  # first BBO after the signal: fills here
        quote(13, 59_999, 98.0, 99.0, 3),
    ]
    result = run(candles, quotes)
    entry = result.trades[0]
    assert entry.side == "LONG"
    assert entry.entry_price == 99.0
    assert entry.entry_time == T0 + timedelta(milliseconds=4 * 60_000 + 60_099)
    assert entry.exit_reason == EXIT_END_OF_SAMPLE


def test_sell_limit_requires_bid_ge_limit() -> None:
    closes = _cross_closes()
    candles = [candle(i, c) for i, c in enumerate(closes)]
    # BUY at candle 4 (limit 110) fills at ask 99; SELL at candle 9 (limit 100)
    # must wait for bid >= 100. Bids stay at 90 -> exit never crosses; the open
    # LONG settles at the final bid instead.
    quotes = [
        quote(0, 0, 90.0, 95.0, 0),
        quote(4, 60_000, 90.0, 99.0, 1),  # entry: ask 99 <= 110 -> fill
        quote(9, 60_000, 90.0, 91.0, 2),  # bid 90 < 100 -> exit pending
        quote(13, 59_999, 90.0, 91.0, 3),  # never crosses -> settle at final bid
    ]
    result = run(candles, quotes)
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.entry_price == 99.0
    assert trade.exit_price == 90.0  # final bid settlement
    assert trade.exit_reason == EXIT_END_OF_SAMPLE
    statuses = [o.status for o in result.orders]
    assert statuses == ["FILLED", "CANCELLED"]  # exit superseded by settlement


def test_short_round_trip_fills_on_executable_sides() -> None:
    # flat 110 (0..4), drop to 100 (5..9), back to 110 (10..13):
    # SELL at candle 5 (limit 100), exit BUY at candle 10 (limit 110).
    closes = [110.0] * 5 + [100.0] * 5 + [110.0] * 4
    candles = [candle(i, c) for i, c in enumerate(closes)]
    quotes = [
        quote(0, 0, 100.0, 101.0, 0),
        quote(5, 60_000, 100.5, 101.0, 1),  # SELL limit 100: bid 100.5 >= 100 -> SHORT @ 100.5
        quote(10, 60_000, 100.5, 101.0, 2),  # exit BUY limit 110: ask 101 <= 110 -> fill @ 101
    ]
    result = run(candles, quotes)
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.side == "SHORT"
    assert trade.entry_price == 100.5
    assert trade.exit_price == 101.0
    assert trade.exit_reason == EXIT_SIGNAL
    # SHORT loses (101 - 100.5) * qty plus fees on both fills
    qty = 10.0 / 100.0  # quantity from LIMIT price (100), not the fill price
    fees = 100.5 * qty * 0.001 + 101.0 * qty * 0.001
    assert trade.pnl_absolute == pytest.approx((100.5 - 101.0) * qty - fees)


# ---------------------------------------------------------------------------
# one-net position policy (AC-05)
# ---------------------------------------------------------------------------


def test_same_side_signals_never_add_position() -> None:
    # repeated cross up/down waves; every BUY while LONG is ignored
    closes = [100.0] * 3 + [110.0] * 5 + [100.0] * 5 + [110.0] * 5 + [100.0] * 5
    candles = [candle(i, c) for i, c in enumerate(closes)]
    quotes = flat_quotes(len(candles), 99.0, 100.0)
    result = run(candles, quotes)
    buys = [s for s in result.signals if s.action == ACTION_BUY]
    sells = [s for s in result.signals if s.action == ACTION_SELL]
    assert buys, "expected BUY signals"
    # at most one net position at any time -> every LONG entry except the first
    # was preceded by an exit; no stacked entries
    entry_fills = [o for o in result.orders if o.status == "FILLED" and o.action == ACTION_BUY]
    exits = [o for o in result.orders if o.status == "FILLED" and o.action == ACTION_SELL]
    assert len(entry_fills) >= 1
    assert len(sells) >= 1
    for trade in result.trades:
        assert trade.exit_time is not None  # settled
    # net exposure never stacked: sum of simultaneous trades is impossible by
    # construction; assert sequence alternation of sides per trade
    for first, second in zip(result.trades, result.trades[1:]):
        assert second.entry_time >= (first.exit_time or second.entry_time)
    _ = exits


def test_flat_sell_opens_short() -> None:
    closes = [110.0] * 5 + [100.0] * 5  # SELL cross at candle 5, limit 100
    candles = [candle(i, c) for i, c in enumerate(closes)]
    result = run(candles, flat_quotes(10, 100.5, 101.0))
    assert result.trades[0].side == "SHORT"


# ---------------------------------------------------------------------------
# sizing, fees, settlement (AC-04, AC-06, AC-10)
# ---------------------------------------------------------------------------


def test_quantity_is_notional_over_limit_and_fee_both_sides() -> None:
    closes = _cross_closes()
    candles = [candle(i, c) for i, c in enumerate(closes)]
    quotes = [
        quote(0, 0, 90.0, 95.0, 0),
        quote(4, 60_000, 99.0, 100.0, 1),  # BUY limit 110 fills at ask 100
        quote(9, 60_000, 100.5, 101.0, 2),  # SELL limit 100 fills at bid 100.5
    ]
    result = run(candles, quotes)
    trade = result.trades[0]
    assert trade.quantity == pytest.approx(10.0 / 110.0)  # limit price, not fill price
    fee_in = 100.0 * trade.quantity * 10 / 10_000
    fee_out = 100.5 * trade.quantity * 10 / 10_000
    assert trade.fee_paid == pytest.approx(fee_in + fee_out)
    assert trade.pnl_absolute == pytest.approx((100.5 - 100.0) * trade.quantity - fee_in - fee_out)
    assert trade.slippage_cost == 0.0  # fixture slippage_bps = 0
    assert trade.entry_notional == pytest.approx(100.0 * trade.quantity)
    assert trade.exit_notional == pytest.approx(100.5 * trade.quantity)
    assert trade.spread_cost == pytest.approx((0.5 + 0.25) * trade.quantity)
    assert trade.gross_pnl == pytest.approx((100.75 - 99.5) * trade.quantity)
    assert trade.net_pnl == pytest.approx(
        trade.gross_pnl - trade.fee_paid - trade.spread_cost - trade.slippage_cost
    )
    assert trade.net_pnl == pytest.approx(trade.pnl_absolute)
    # conservation: equity change equals summed trade PnL once flat
    final_equity = result.equity_points[-1].equity
    assert final_equity - 100.0 == pytest.approx(trade.pnl_absolute)


def test_end_of_sample_settles_long_at_final_bid() -> None:
    closes = _cross_closes()[:9]  # only the BUY cross (candle 4), never the SELL
    candles = [candle(i, c) for i, c in enumerate(closes)]
    quotes = [
        quote(0, 0, 90.0, 95.0, 0),
        quote(4, 60_000, 99.0, 100.0, 1),  # BUY limit 110 fills at ask 100
        quote(8, 10_000, 107.0, 108.0, 2),  # final executable quote
    ]
    result = run(candles, quotes)
    trade = result.trades[0]
    assert trade.exit_reason == EXIT_END_OF_SAMPLE
    assert trade.exit_price == 107.0  # final bid, not candle close
    qty = 10.0 / 110.0
    fee_in = 100.0 * qty * 0.001
    fee_out = 107.0 * qty * 0.001
    assert trade.pnl_absolute == pytest.approx((107.0 - 100.0) * qty - fee_in - fee_out)


def test_pending_entry_expires_without_trade() -> None:
    closes = _cross_closes()
    candles = [candle(i, c) for i, c in enumerate(closes)]
    # ask always above the BUY limit 110 -> the intent never crosses
    quotes = [quote(i, 1, 1.0, 200.0, i) for i in range(14)]
    result = run(candles, quotes)
    assert result.trades == []
    assert [o.status for o in result.orders] == ["EXPIRED"]


# ---------------------------------------------------------------------------
# input errors
# ---------------------------------------------------------------------------


def test_missing_prior_bbo_is_deterministic_error() -> None:
    candles = [candle(i, 100.0) for i in range(6)]
    with pytest.raises(DomainError) as excinfo:
        run(candles, [])
    assert excinfo.value.code == ERR_MISSING_PRIOR_BBO


def test_insufficient_candles_rejected() -> None:
    candles = [candle(i, 100.0) for i in range(2)]
    with pytest.raises(DomainError) as excinfo:
        run(candles, flat_quotes(2, 99.0, 100.0))
    assert excinfo.value.code == ERR_INSUFFICIENT_CANDLES


def test_invalid_bbo_replay_rejected() -> None:
    candles = [candle(i, 100.0) for i in range(6)]
    crossed = [quote(0, 1, 101.0, 100.0, 1)]  # bid > ask
    with pytest.raises(DomainError):
        run(candles, crossed)
    out_of_order = [quote(1, 1, 99.0, 100.0, 1), quote(0, 1, 99.0, 100.0, 2)]
    with pytest.raises(DomainError):
        run(candles, out_of_order)


def test_snapshot_validation_rejects_bad_policy() -> None:
    candles = [candle(i, 100.0) for i in range(6)]
    with pytest.raises(DomainError) as excinfo:
        run(candles, flat_quotes(6, 99.0, 100.0), snapshot(fixed_notional=0.0))
    assert excinfo.value.code == ERR_VALIDATION


def test_dataset_too_large_rejected() -> None:
    candles = [candle(i, 100.0) for i in range(20_001)]
    with pytest.raises(DomainError) as excinfo:
        run(candles, [])
    assert excinfo.value.code == "dataset_too_large"


# ---------------------------------------------------------------------------
# plugin failures (exception isolation)
# ---------------------------------------------------------------------------


class _ExplodingStrategy:
    def definition(self) -> Definition:
        return Definition(strategy_id="boom", version="v1", warm_up_candles=1)

    def analyze(self, context: AnalysisContext) -> Signal:
        raise ValueError("plugin bug")


class _BadPriceStrategy:
    def definition(self) -> Definition:
        return Definition(strategy_id="badprice", version="v1", warm_up_candles=1)

    def analyze(self, context: AnalysisContext) -> Signal:
        return Signal(action=ACTION_BUY, price=None)


class _PeekingStrategy:
    def definition(self) -> Definition:
        return Definition(strategy_id="peek", version="v1", warm_up_candles=1)

    def analyze(self, context: AnalysisContext) -> Signal:
        context.candles.at(context.index + 1)  # look-ahead
        return Signal(action=ACTION_HOLD)


def _engine_with(strategy) -> DeterministicEngine:
    registry = Registry()
    registry.register(lambda: strategy)
    return DeterministicEngine(registry=registry)


def test_strategy_exception_wrapped_not_raised_raw() -> None:
    candles = [candle(i, 100.0) for i in range(4)]
    snap = snapshot()
    snap.strategy = Reference("boom", "v1")
    snap.candidate_definition = {}
    with pytest.raises(DomainError) as excinfo:
        _engine_with(_ExplodingStrategy()).run(snap, candles, flat_quotes(4, 99.0, 100.0))
    assert excinfo.value.code == ERR_STRATEGY_EXCEPTION


def test_invalid_signal_missing_price() -> None:
    candles = [candle(i, 100.0) for i in range(4)]
    snap = snapshot()
    snap.strategy = Reference("badprice", "v1")
    snap.candidate_definition = {}
    with pytest.raises(DomainError) as excinfo:
        _engine_with(_BadPriceStrategy()).run(snap, candles, flat_quotes(4, 99.0, 100.0))
    assert excinfo.value.code == ERR_INVALID_SIGNAL


def test_look_ahead_strategy_rejected() -> None:
    candles = [candle(i, 100.0) for i in range(4)]
    snap = snapshot()
    snap.strategy = Reference("peek", "v1")
    snap.candidate_definition = {}
    with pytest.raises(DomainError) as excinfo:
        _engine_with(_PeekingStrategy()).run(snap, candles, flat_quotes(4, 99.0, 100.0))
    assert excinfo.value.code == ERR_LOOK_AHEAD


# ---------------------------------------------------------------------------
# determinism (AC-01)
# ---------------------------------------------------------------------------


def test_five_runs_same_canonical_hash() -> None:
    closes = zigzag(120)
    candles = [candle(i, c) for i, c in enumerate(closes)]
    quotes = []
    seq = 0
    for i, close in enumerate(closes):
        for offset in (10_000, 30_000, 50_000):
            seq += 1
            quotes.append(quote(i, offset, close - 0.05, close + 0.05, seq))
    snap = snapshot(fast=3, slow=5)
    engine = DeterministicEngine()
    hashes = {
        canonical_result_hash(engine.run(snap, candles, quotes)) for _ in range(5)
    }
    assert len(hashes) == 1


# ---------------------------------------------------------------------------
# event ordering: (eventTime, priority, sourceSequence), BBO first at ties
# ---------------------------------------------------------------------------


def _event_key(event) -> tuple[int, int, int]:
    event_ms, _, kind, payload = event
    if kind == "bbo":
        return (event_ms, 0, payload.source_sequence)
    index, _ = payload
    return (event_ms, 1, index + 1)


def test_merged_events_strictly_ordered_and_bbo_first_at_same_time() -> None:
    from app.services.backtest_engine import merged_events

    closes = zigzag(10)
    candles = [candle(i, c) for i, c in enumerate(closes)]
    # BBOs deliberately landing exactly on candle-close timestamps, plus
    # duplicate-timestamp BBOs (ordering falls back to sourceSequence).
    # candle i closes at i*60_000 + 59_999 ms.
    quotes = [
        quote(0, 0, 99.0, 100.0, 1),
        quote(0, 0, 99.0, 100.0, 2),  # same event_time as above
        quote(0, 59_999, 99.0, 100.0, 3),  # exact candle-0 close time
        quote(3, 59_999, 99.0, 100.0, 4),  # exact candle-3 close time
        quote(3, 59_999, 99.0, 100.0, 5),  # same again, higher sequence
        quote(9, 59_999, 99.0, 100.0, 6),  # exact candle-9 close time
        quote(9, 60_500, 99.0, 100.0, 7),  # after everything
    ]
    events = list(merged_events(candles, quotes))
    keys = [_event_key(e) for e in events]
    # strictly increasing causal keys — no unordered iteration anywhere
    assert all(a < b for a, b in pairwise(keys))
    # event times never decrease
    times = [e[0] for e in events]
    assert times == sorted(times)
    # all inputs replayed exactly once
    assert sum(1 for e in events if e[2] == "bbo") == len(quotes)
    assert sum(1 for e in events if e[2] == "candle") == len(candles)
    # at a shared timestamp the BBO (priority 0) precedes the candle (priority 1)
    candle3 = next(i for i, e in enumerate(events) if e[2] == "candle" and e[3][0] == 3)
    bbo4 = next(i for i, e in enumerate(events) if e[2] == "bbo" and e[3].source_sequence == 4)
    bbo5 = next(i for i, e in enumerate(events) if e[2] == "bbo" and e[3].source_sequence == 5)
    assert events[bbo4][0] == events[candle3][0]
    assert bbo4 < bbo5 < candle3  # duplicate BBOs by sequence, all before the candle


def test_merged_events_full_fixture_strictly_ordered() -> None:
    from app.services.backtest_engine import merged_events

    candles, quotes, _ = _load_fixture()
    previous_key: tuple[int, int, int] | None = None
    count = 0
    for event in merged_events(candles, quotes):
        key = _event_key(event)
        assert previous_key is None or previous_key < key, "causal key ordering violated"
        previous_key = key
        count += 1
    assert count == len(candles) + len(quotes)  # 1,443 + 800,692 events, all replayed


# ---------------------------------------------------------------------------
# concurrency: engine purity + worker lifecycle ordering
# ---------------------------------------------------------------------------


def test_concurrent_engine_runs_are_pure() -> None:
    """The engine holds no per-run mutable state: concurrent replays of the
    same inputs from several threads must produce identical canonical hashes."""
    closes = zigzag(200)
    candles = [candle(i, c) for i, c in enumerate(closes)]
    quotes = []
    seq = 0
    for i, close in enumerate(closes):
        for offset in (10_000, 40_000):
            seq += 1
            quotes.append(quote(i, offset, close - 0.05, close + 0.05, seq))
    snap = snapshot(fast=3, slow=5)
    engine = DeterministicEngine()  # one shared instance across threads
    threads, results = [], []

    def target():
        results.append(canonical_result_hash(engine.run(snap, candles, quotes)))

    for _ in range(4):
        thread = threading.Thread(target=target)
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join()
    assert len(results) == 4
    assert len(set(results)) == 1


class _FakeDispatcher:
    """Records the call order the worker makes; thread-safe via a lock."""

    def __init__(self, candles, quotes, load_delay_s: float = 0.0) -> None:
        self._candles, self._quotes = candles, quotes
        self._load_delay_s = load_delay_s
        self._lock = threading.Lock()
        self.calls: list[tuple] = []
        self.complete_returns = True
        self.run_id = uuid4()

    def _record(self, call: tuple) -> None:
        with self._lock:
            self.calls.append(call)

    def load_dataset(self, snapshot):
        if self._load_delay_s:  # hold the "dataset read" long enough for beats
            time.sleep(self._load_delay_s)
        self._record(("load_dataset",))
        return self._candles, self._quotes

    def heartbeat(self, job_id, lease_token, lease):
        self._record(("heartbeat", lease))
        return True

    def complete(self, job_id, lease_token, result=None):
        self._record(("complete", result is not None))
        return self.complete_returns, self.run_id

    def fail(self, job_id, err, retryable, lease_token):
        code = getattr(err, "code", type(err).__name__)
        self._record(("fail", code, retryable))
        return True

    def persist_evaluation(self, run_id, evaluation):
        self._record(("persist_evaluation", evaluation.evaluator_version))


def _fake_job(snap) -> BacktestJob:
    from datetime import datetime

    return BacktestJob(
        id=uuid4(),
        experiment_id=snap.experiment_id,
        snapshot=snap,
        status="leased",
        priority=100,
        attempt=1,
        max_attempts=3,
        leased_by="worker-test",
        lease_token=uuid4(),
        lease_expires_at=datetime.now(tz=UTC),
    )


def test_worker_process_completes_after_heartbeat_with_evaluation() -> None:
    closes = _cross_closes()
    candles = [candle(i, c) for i, c in enumerate(closes)]
    quotes = [
        quote(0, 0, 90.0, 95.0, 0),
        quote(4, 60_000, 99.0, 100.0, 1),
        quote(9, 60_000, 100.5, 101.0, 2),
    ]
    fake = _FakeDispatcher(candles, quotes, load_delay_s=0.05)
    from app.worker import BacktestWorker, WorkerConfig

    worker = BacktestWorker(
        fake,
        config=WorkerConfig(
            worker_id="worker-test",
            heartbeat_s=0.005,  # force beats during the run
            event_consumers=("evaluator",),
        ),
    )
    worker._process(_fake_job(snapshot()))
    kinds = [call[0] for call in fake.calls]
    # heartbeat beats happen during the run; completion only after;
    # the evaluator consumer persists the evaluation last
    assert "load_dataset" in kinds
    assert "heartbeat" in kinds
    assert kinds.index("heartbeat") < kinds.index("complete")
    assert kinds[-1] == "persist_evaluation"
    assert any(call[0] == "complete" and call[1] is True for call in fake.calls)


def test_worker_process_routes_domain_error_to_non_retryable_fail() -> None:
    candles = [candle(i, 100.0) for i in range(4)]
    quotes = flat_quotes(4, 99.0, 100.0)
    fake = _FakeDispatcher(candles, quotes)
    from app.worker import BacktestWorker, WorkerConfig

    worker = BacktestWorker(fake, config=WorkerConfig(worker_id="worker-test", heartbeat_s=0.005))
    bad = snapshot(fixed_notional=0.0)  # deterministic input error
    worker._process(_fake_job(bad))
    failure = next(call for call in fake.calls if call[0] == "fail")
    assert failure[1] == ERR_VALIDATION
    assert failure[2] is False  # deterministic error: never retried
    assert not any(call[0] == "complete" for call in fake.calls)


def test_worker_discards_result_when_lease_guard_rejects() -> None:
    closes = _cross_closes()
    candles = [candle(i, c) for i, c in enumerate(closes)]
    quotes = [
        quote(0, 0, 90.0, 95.0, 0),
        quote(4, 60_000, 99.0, 100.0, 1),
        quote(9, 60_000, 100.5, 101.0, 2),
    ]
    fake = _FakeDispatcher(candles, quotes)
    fake.complete_returns = False  # lease lost to a takeover worker
    from app.worker import BacktestWorker, WorkerConfig

    worker = BacktestWorker(
        fake,
        config=WorkerConfig(worker_id="worker-test", heartbeat_s=0.005, event_consumers=("evaluator",)),
    )
    worker._process(_fake_job(snapshot()))
    # result computed but discarded: no evaluation persisted over the takeover
    assert not any(call[0] == "persist_evaluation" for call in fake.calls)


# ---------------------------------------------------------------------------
# evaluator (specs/evaluation.md)
# ---------------------------------------------------------------------------


def _policy(**overrides) -> EvaluationPolicy:
    values = {
        "evaluator_version": "v1",
        "periods_per_year": 8_760,
        "zero_pnl_counts_as_win": False,
        "stddev_ddof": 1,
        "min_periods_for_sharpe": 2,
        "risk_free_rate": 0.0,
    }
    values.update(overrides)
    return EvaluationPolicy(**values)


def _equity(values: list[float]):
    from app.domain.backtest import EquityPoint

    peak = values[0]
    points = []
    for index, value in enumerate(values):
        peak = max(peak, value)
        points.append(
            EquityPoint(
                point_time=T0 + timedelta(minutes=index),
                equity=value,
                drawdown_pct=(value - peak) / peak * 100,
            )
        )
    return points


def _trade(pnl: float, settled: bool = True, pnl_pct: float | None = None):
    from app.domain.backtest import TradeFact

    return TradeFact(
        sequence_no=1,
        side="LONG",
        entry_time=T0,
        entry_price=100.0,
        quantity=0.1,
        fee_paid=0.02,
        slippage_cost=0.0,
        exit_time=T0 + timedelta(hours=1) if settled else None,
        exit_price=100.0 + pnl if settled else None,
        pnl_absolute=pnl if settled else None,
        pnl_percent=pnl_pct if settled else None,
        exit_reason=EXIT_SIGNAL if settled else None,
    )


def test_evaluator_zero_trades_no_division_error() -> None:
    evaluation = DeterministicEvaluator().evaluate(
        EvaluationInput(
            run_id=uuid4(), initial_equity=100.0, trades=[], equity_points=_equity([100.0, 101.0])
        ),
        _policy(),
    )
    assert evaluation.trade_count == 0
    assert evaluation.win_rate_pct == 0.0
    assert evaluation.profit_factor is None
    assert evaluation.avg_trade_pct is None
    assert evaluation.total_return_pct == pytest.approx(1.0)


def test_evaluator_all_loss_profit_factor_zero() -> None:
    trades = [_trade(-1.0, pnl_pct=-1.0), _trade(-2.0, pnl_pct=-2.0)]
    evaluation = DeterministicEvaluator().evaluate(
        EvaluationInput(uuid4(), 100.0, trades, _equity([100.0, 97.0])), _policy()
    )
    assert evaluation.win_rate_pct == 0.0
    assert evaluation.profit_factor == 0.0
    assert evaluation.avg_trade_pct == pytest.approx(-1.5)


def test_evaluator_no_loss_profit_factor_null() -> None:
    trades = [_trade(1.0, pnl_pct=1.0), _trade(2.0, pnl_pct=2.0)]
    evaluation = DeterministicEvaluator().evaluate(
        EvaluationInput(uuid4(), 100.0, trades, _equity([100.0, 103.0])), _policy()
    )
    assert evaluation.profit_factor is None
    assert evaluation.win_rate_pct == 100.0


def test_evaluator_mdd_from_equity_curve() -> None:
    # peak 120, trough 90 -> mdd = -25%
    points = _equity([100.0, 120.0, 90.0, 110.0])
    evaluation = DeterministicEvaluator().evaluate(
        EvaluationInput(uuid4(), 100.0, [], points), _policy()
    )
    assert evaluation.max_drawdown_pct == pytest.approx(-25.0)


def test_evaluator_open_trades_counted_separately() -> None:
    trades = [_trade(1.0, pnl_pct=1.0), _trade(0.0, settled=False)]
    evaluation = DeterministicEvaluator().evaluate(
        EvaluationInput(uuid4(), 100.0, trades, _equity([100.0, 101.0])), _policy()
    )
    assert evaluation.trade_count == 1
    assert evaluation.open_trade_count == 1


def test_evaluator_requires_equity_points() -> None:
    with pytest.raises(DomainError):
        DeterministicEvaluator().evaluate(
            EvaluationInput(uuid4(), 100.0, [], equity_points=[]), _policy()
        )


def test_evaluator_flat_equity_sharpe_null() -> None:
    evaluation = DeterministicEvaluator().evaluate(
        EvaluationInput(uuid4(), 100.0, [], _equity([100.0] * 10)), _policy()
    )
    assert evaluation.sharpe_ratio is None


# ---------------------------------------------------------------------------
# worker CLI end-to-end on a tiny fixture directory
# ---------------------------------------------------------------------------


def test_worker_fixture_cli_end_to_end(tmp_path) -> None:
    import csv

    from app.worker import main

    dataset = tmp_path / "sol-test"
    dataset.mkdir()
    closes = zigzag(60)
    with (dataset / "ohlcv.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["T", "O", "H", "L", "C", "V"])
        base_ms = int(datetime(2026, 3, 4, tzinfo=UTC).timestamp() * 1000)
        for i, close in enumerate(closes):
            writer.writerow(
                [base_ms + i * 60_000, close, close + 0.1, close - 0.1, close, 10.0]
            )
    with (dataset / "bbo.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["b", "B", "a", "A", "T"])
        seq = 0
        for i, close in enumerate(closes):
            for offset in (10_000, 40_000):
                seq += 1
                writer.writerow([close - 0.02, 100.0, close + 0.02, 100.0, base_ms + i * 60_000 + offset])

    exit_code = main(
        [
            "fixture",
            "--dataset",
            str(dataset),
            "--strategy",
            "ma_cross@v1:fast=3,slow=5",
            "--runs",
            "3",
        ]
    )
    assert exit_code == 0


# ---------------------------------------------------------------------------
# real fixture structural acceptance (AC-07 python spec) — the heavy test
# ---------------------------------------------------------------------------

FIXTURE_DIR = "data/formatted/sol/2026-03-04"


def _load_fixture():
    from app.infrastructure.dataset import load_fixture_dataset

    return load_fixture_dataset(FIXTURE_DIR, provider="binance", symbol="SOLUSDT", timeframe="1m")


def test_fixture_structure_and_determinism() -> None:
    candles, quotes, info = _load_fixture()
    assert info.candle_count == 1_443
    assert len(quotes) == 800_692
    assert len(info.content_hash) == 64 and len(info.bbo_content_hash) == 64

    from app.worker import build_fixture_snapshot, default_evaluation_policy

    snap = build_fixture_snapshot(Reference("ma_cross", "v1"), {"fast": 20, "slow": 50}, info)
    engine = DeterministicEngine()
    first = engine.run(snap, candles, quotes)
    second = engine.run(snap, candles, quotes)
    assert canonical_result_hash(first) == canonical_result_hash(second)

    # structural acceptance: 29 strict MA20/50 signals, 15 BUY, 14 SELL
    assert len(first.signals) == 29
    assert sum(1 for s in first.signals if s.action == ACTION_BUY) == 15
    assert sum(1 for s in first.signals if s.action == ACTION_SELL) == 14

    # settled trades: 13 signal exits + 1 end_of_sample. The 15th BUY signal is
    # same-side while the last LONG is still open (its exit limit never crossed:
    # max later bid 92.02 < limit 92.08), so the position settles at final bid.
    settled = [t for t in first.trades if t.exit_time is not None]
    assert len(settled) == 14
    assert sum(1 for t in settled if t.exit_reason == EXIT_SIGNAL) == 13
    assert sum(1 for t in settled if t.exit_reason == EXIT_END_OF_SAMPLE) == 1
    assert all(t.exit_time is not None for t in first.trades)

    evaluation = DeterministicEvaluator().evaluate(
        EvaluationInput(
            uuid4(), snap.initial_equity, first.trades, first.equity_points
        ),
        default_evaluation_policy("1m"),
    )
    assert evaluation.trade_count == 14
    assert evaluation.open_trade_count == 0
    assert 0.0 <= evaluation.win_rate_pct <= 100.0
    assert evaluation.max_drawdown_pct <= 0.0
