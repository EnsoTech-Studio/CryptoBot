"""Composite strategy + backtest worker queue-path tests.

Covers `specs/composite-strategy.md` AC-01..AC-09 (combiner semantics,
composite snapshot validation, warm-up = max(child), child_signals evidence)
and the worker/dispatcher lifecycle fixes: run_id propagation to the evaluator
consumer, AC-05d completed-run short-circuit, fail-after-complete run guard,
rollback recovery, and heartbeat extension length.
"""

from __future__ import annotations

import math
import threading
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest

from app.domain.backtest import ExperimentSnapshot, MarketSnapshot
from app.domain.common import (
    ACTION_BUY,
    ACTION_HOLD,
    ACTION_SELL,
    ERR_INVALID_SIGNAL,
    ERR_VALIDATION,
    DomainError,
)
from app.domain.job import BacktestJob
from app.domain.market import BBO, Candle
from app.domain.strategy import (
    ChildDefinition,
    CombinationPolicy,
    CompositeDefinition,
    Reference,
    ResolvedSignal,
    Signal,
)
from app.domain.strategy.composite import MajorityVoteCombiner, WeightedVoteCombiner
from app.services.backtest_engine import DeterministicEngine, canonical_result_hash

T0 = datetime(2026, 3, 4, tzinfo=UTC)


# ---------------------------------------------------------------------------
# combiner harness
# ---------------------------------------------------------------------------


def resolved(action: str, weight: float, price: float | None = 100.0, sid: str = "s") -> ResolvedSignal:
    return ResolvedSignal(
        strategy_id=sid, version="v1", signal=Signal(action=action, price=price), weight=weight
    )


def policy(threshold: float = 0.3, name: str = "weighted_vote") -> CombinationPolicy:
    return CombinationPolicy(
        policy=name, threshold=threshold, encoding={"BUY": 1, "HOLD": 0, "SELL": -1}
    )


# ---------------------------------------------------------------------------
# weighted vote (AC-01, AC-03, AC-06)
# ---------------------------------------------------------------------------


def test_weighted_ac01_normalized_score_buy() -> None:
    children = [
        resolved(ACTION_BUY, 0.2, 110.0, "ma"),
        resolved(ACTION_SELL, 0.3, 120.0, "rsi"),
        resolved(ACTION_BUY, 0.5, 130.0, "sr"),
    ]
    signal = WeightedVoteCombiner().combine(children, policy(0.3))
    assert signal.action == ACTION_BUY
    assert signal.confidence == pytest.approx(0.4)
    assert signal.evidence["score"] == pytest.approx(0.4)
    # weighted price over non-HOLD children: (0.2*110 + 0.3*120 + 0.5*130) / 1.0
    assert signal.price == pytest.approx(0.2 * 110 + 0.3 * 120 + 0.5 * 130)


def test_weighted_unnormalized_weights_same_score() -> None:
    children = [
        resolved(ACTION_BUY, 2.0, 110.0, "ma"),
        resolved(ACTION_SELL, 3.0, 120.0, "rsi"),
        resolved(ACTION_BUY, 5.0, 130.0, "sr"),
    ]
    signal = WeightedVoteCombiner().combine(children, policy(0.3))
    assert signal.action == ACTION_BUY
    assert signal.confidence == pytest.approx(0.4)  # (2 - 3 + 5) / 10


def test_weighted_ac03_higher_threshold_holds() -> None:
    children = [
        resolved(ACTION_BUY, 0.2, 110.0, "ma"),
        resolved(ACTION_SELL, 0.3, 120.0, "rsi"),
        resolved(ACTION_BUY, 0.5, 130.0, "sr"),
    ]
    signal = WeightedVoteCombiner().combine(children, policy(0.5))
    assert signal.action == ACTION_HOLD
    assert signal.price is None


def test_weighted_strict_threshold_boundary_is_hold() -> None:
    # score = (0.5 - 0.1) / 0.6 = 0.666..; threshold exactly equal must HOLD:
    children = [resolved(ACTION_BUY, 5.0, 100.0, "ma"), resolved(ACTION_SELL, 1.0, 100.0, "rsi")]
    signal = WeightedVoteCombiner().combine(children, policy(2 / 3))
    assert signal.action == ACTION_HOLD  # score == threshold: strict comparison


def test_weighted_ac06_threshold_zero() -> None:
    hold = WeightedVoteCombiner().combine(
        [resolved(ACTION_BUY, 0.5, 100.0, "ma"), resolved(ACTION_SELL, 0.5, 100.0, "rsi")],
        policy(0.0),
    )
    assert hold.action == ACTION_HOLD  # score 0 stays HOLD at threshold 0
    buy = WeightedVoteCombiner().combine(
        [resolved(ACTION_BUY, 0.5, 100.0, "ma"), resolved(ACTION_HOLD, 0.5, None, "rsi")],
        policy(0.0),
    )
    assert buy.action == ACTION_BUY


def test_weighted_all_hold_returns_hold() -> None:
    children = [resolved(ACTION_HOLD, 0.5, None, "ma"), resolved(ACTION_HOLD, 0.5, None, "rsi")]
    assert WeightedVoteCombiner().combine(children, policy(0.3)).action == ACTION_HOLD


def test_weighted_negative_weight_rejected() -> None:
    children = [resolved(ACTION_BUY, -0.5, 100.0, "ma"), resolved(ACTION_SELL, 1.0, 100.0, "rsi")]
    with pytest.raises(DomainError) as excinfo:
        WeightedVoteCombiner().combine(children, policy(0.3))
    assert excinfo.value.code == ERR_VALIDATION


def test_weighted_zero_total_weight_rejected() -> None:
    children = [resolved(ACTION_HOLD, 0.0, None, "ma"), resolved(ACTION_HOLD, 0.0, None, "rsi")]
    with pytest.raises(DomainError) as excinfo:
        WeightedVoteCombiner().combine(children, policy(0.3))
    assert excinfo.value.code == ERR_VALIDATION


def test_non_hold_child_without_price_is_invalid_signal() -> None:
    children = [resolved(ACTION_BUY, 0.5, None, "ma"), resolved(ACTION_SELL, 0.5, 100.0, "rsi")]
    for combiner in (WeightedVoteCombiner(), MajorityVoteCombiner()):
        with pytest.raises(DomainError) as excinfo:
            combiner.combine(children, policy(0.3))
        assert excinfo.value.code == ERR_INVALID_SIGNAL


# ---------------------------------------------------------------------------
# majority vote (AC-02, plurality, ties)
# ---------------------------------------------------------------------------


def test_majority_ac02_confidence_two_thirds() -> None:
    children = [
        resolved(ACTION_BUY, 0.2, 110.0, "ma"),
        resolved(ACTION_BUY, 0.3, 120.0, "rsi"),
        resolved(ACTION_HOLD, 0.5, None, "sr"),
    ]
    signal = MajorityVoteCombiner().combine(children, policy(0.3, "majority_vote"))
    assert signal.action == ACTION_BUY
    assert signal.confidence == pytest.approx(2 / 3)


def test_majority_is_plurality_not_strict_majority() -> None:
    # {BUY, BUY, SELL, HOLD}: BUY wins with 2/4 even though 2 < 4/2+1
    children = [
        resolved(ACTION_BUY, 1.0, 100.0, "ma"),
        resolved(ACTION_BUY, 1.0, 101.0, "rsi"),
        resolved(ACTION_SELL, 1.0, 102.0, "sr"),
        resolved(ACTION_HOLD, 1.0, None, "bb"),
    ]
    signal = MajorityVoteCombiner().combine(children, policy(0.3, "majority_vote"))
    assert signal.action == ACTION_BUY
    assert signal.confidence == pytest.approx(0.5)


def test_majority_tie_returns_hold() -> None:
    children = [
        resolved(ACTION_BUY, 1.0, 100.0, "ma"),
        resolved(ACTION_SELL, 1.0, 100.0, "rsi"),
    ]
    signal = MajorityVoteCombiner().combine(children, policy(0.3, "majority_vote"))
    assert signal.action == ACTION_HOLD


# ---------------------------------------------------------------------------
# engine composite path (validation, warm-up, evidence)
# ---------------------------------------------------------------------------


def composite_snapshot(children: list[ChildDefinition], threshold: float = 0.3,
                       policy_name: str = "weighted_vote", **overrides) -> ExperimentSnapshot:
    values: dict[str, Any] = {
        "experiment_id": uuid4(),
        "owner_id": None,
        "strategy": Reference("composite", "v1"),
        "candidate_definition": CompositeDefinition(
            strategy_id="composite",
            version="v1",
            children=children,
            combination=CombinationPolicy(
                policy=policy_name, threshold=threshold,
                encoding={"BUY": 1, "HOLD": 0, "SELL": -1},
            ),
        ),
        "candidate_hash": "c" * 64,
        "market": MarketSnapshot("test", 1, "binance", "SOLUSDT", "1m", T0, T0, 0, "h1", "h2"),
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


def child(strategy_id: str, params: dict[str, Any], weight: float) -> ChildDefinition:
    return ChildDefinition(
        strategy_id=strategy_id, version="v1", parameters=params, weight=weight
    )


def candle(i: int, close: float) -> Candle:
    return Candle(
        provider="binance", symbol="SOLUSDT", timeframe="1m",
        open_time=T0 + timedelta(minutes=i),
        close_time=T0 + timedelta(minutes=i, seconds=59, milliseconds=999),
        open=close, high=close + 0.5, low=close - 0.5, close=close, volume=1.0,
    )


def flat_quotes(minutes: int, bid: float, ask: float) -> list[BBO]:
    return [
        BBO(
            provider="binance", symbol="SOLUSDT",
            event_time=T0 + timedelta(milliseconds=i * 60_000 + 1),
            bid=bid, bid_qty=1.0, ask=ask, ask_qty=1.0, update_id=None,
            source_sequence=i + 1,
        )
        for i in range(minutes)
    ]


def zigzag(n: int, period: int = 8, base: float = 100.0, amp: float = 5.0) -> list[float]:
    return [base + amp * math.sin(2 * math.pi * i / period) for i in range(n)]


COMPOSITE_CHILDREN = [
    child("ma_cross", {"fast": 2, "slow": 3}, 0.5),
    child("ma_cross", {"fast": 3, "slow": 5}, 0.5),
]


def test_composite_engine_runs_with_max_child_warm_up_and_score_evidence() -> None:
    closes = zigzag(120)
    candles = [candle(i, c) for i, c in enumerate(closes)]
    engine = DeterministicEngine()
    snap = composite_snapshot(COMPOSITE_CHILDREN)
    first = engine.run(snap, candles, flat_quotes(len(candles), 99.0, 100.0))
    second = engine.run(snap, candles, flat_quotes(len(candles), 99.0, 100.0))
    assert canonical_result_hash(first) == canonical_result_hash(second)
    # AC-08: composite warm-up = max(child warm-up) = slow=5
    assert first.warm_up_candles == 5
    # AC-09: every recorded signal carries the composite score + child evidence
    assert first.signals, "expected at least one non-HOLD composite signal"
    for record in first.signals:
        payload = record.child_signals
        assert payload is not None
        assert payload["action"] == record.action
        assert isinstance(payload["score"], float)
        assert len(payload["children"]) == 2
        for entry in payload["children"]:
            if entry["action"] != ACTION_HOLD:
                assert entry["price"] > 0  # non-HOLD children must carry prices
        # recorded only when the combination is actionable
        assert record.action in (ACTION_BUY, ACTION_SELL)


@pytest.mark.parametrize(
    "children,threshold",
    [
        (COMPOSITE_CHILDREN[:1], 0.3),  # 1 child: invalid cardinality
        ([child("ma_cross", {"fast": i, "slow": i + 1}, 0.2) for i in range(1, 7)], 0.3),  # 6
        ([child("ma_cross", {"fast": 2, "slow": 3}, 0.5),
          child("ma_cross", {"fast": 2, "slow": 3}, 0.5)], 0.3),  # duplicate exact child
        (COMPOSITE_CHILDREN, 1.5),  # threshold outside [0,1]
    ],
)
def test_composite_snapshot_validation(children, threshold) -> None:
    candles = [candle(i, 100.0) for i in range(10)]
    snap = composite_snapshot(children, threshold=threshold)
    with pytest.raises(DomainError) as excinfo:
        DeterministicEngine().run(snap, candles, flat_quotes(10, 99.0, 100.0))
    assert excinfo.value.code == ERR_VALIDATION


def test_negative_child_weight_rejected_before_run() -> None:
    children = [child("ma_cross", {"fast": 2, "slow": 3}, -0.5),
                child("ma_cross", {"fast": 3, "slow": 5}, 1.0)]
    snap = composite_snapshot(children)
    with pytest.raises(DomainError) as excinfo:
        DeterministicEngine().run(snap, [candle(i, 100.0) for i in range(10)],
                                  flat_quotes(10, 99.0, 100.0))
    assert excinfo.value.code == ERR_VALIDATION


def test_same_strategy_different_parameters_is_valid() -> None:
    candles = [candle(i, c) for i, c in enumerate(zigzag(40))]
    snap = composite_snapshot(COMPOSITE_CHILDREN)
    result = DeterministicEngine().run(snap, candles, flat_quotes(40, 99.0, 100.0))
    assert result.warm_up_candles == 5


def test_plugin_param_error_is_validation_not_crash() -> None:
    candles = [candle(i, 100.0) for i in range(10)]
    values = {
        "experiment_id": uuid4(),
        "owner_id": None,
        "strategy": Reference("ma_cross", "v1"),
        "candidate_definition": {"fast": 0, "slow": 3},
        "candidate_hash": "x" * 64,
        "market": MarketSnapshot("test", 1, "binance", "SOLUSDT", "1m", T0, T0, 0, "h1", "h2"),
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
    with pytest.raises(DomainError) as excinfo:
        DeterministicEngine().run(ExperimentSnapshot(**values), candles,
                                  flat_quotes(10, 99.0, 100.0))
    assert excinfo.value.code == ERR_VALIDATION


# ---------------------------------------------------------------------------
# worker lifecycle: run_id propagation, AC-05d short-circuit, run guard
# ---------------------------------------------------------------------------


def _fake_job(snap: ExperimentSnapshot, **kwargs) -> BacktestJob:
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
        **kwargs,
    )


class _RecordingDispatcher:
    def __init__(self, candles=None, quotes=None, complete_run_id=None) -> None:
        self._candles, self._quotes = candles or [], quotes or []
        self._lock = threading.Lock()
        self.calls: list[tuple] = []
        self.complete_run_id = complete_run_id or uuid4()
        self.complete_ok = True

    def _record(self, call: tuple) -> None:
        with self._lock:
            self.calls.append(call)

    def load_dataset(self, snapshot):
        self._record(("load_dataset",))
        return self._candles, self._quotes

    def heartbeat(self, job_id, lease_token, lease):
        return True

    def complete(self, job_id, lease_token, result=None):
        self._record(("complete", result is not None))
        return self.complete_ok, self.complete_run_id

    def fail(self, job_id, err, retryable, lease_token):
        self._record(("fail", getattr(err, "code", type(err).__name__)))
        return True

    def persist_evaluation(self, run_id, evaluation):
        self._record(("persist_evaluation", run_id))


class _SpyEngine:
    def __init__(self) -> None:
        self.runs = 0

    def run(self, snapshot, candles, bbo):
        self.runs += 1
        return DeterministicEngine().run(snapshot, candles, bbo)


def _ma_snapshot() -> ExperimentSnapshot:
    values = {
        "experiment_id": uuid4(),
        "owner_id": None,
        "strategy": Reference("ma_cross", "v1"),
        "candidate_definition": {"fast": 2, "slow": 3},
        "candidate_hash": "x" * 64,
        "market": MarketSnapshot("test", 1, "binance", "SOLUSDT", "1m", T0, T0, 0, "h1", "h2"),
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
    return ExperimentSnapshot(**values)


def test_worker_skips_engine_when_run_already_completed() -> None:
    from app.worker import BacktestWorker, WorkerConfig

    candles = [candle(i, c) for i, c in enumerate(zigzag(20))]
    fake = _RecordingDispatcher(candles, flat_quotes(20, 99.0, 100.0))
    spy = _SpyEngine()
    worker = BacktestWorker(
        fake, engine=spy, config=WorkerConfig(worker_id="w", event_consumers=("evaluator",))
    )
    worker._process(_fake_job(_ma_snapshot(), run_id=uuid4(), run_already_completed=True))
    # AC-05c/AC-05d: job completed without a result, engine never invoked,
    # no dataset load and no evaluation over the stale run
    assert spy.runs == 0
    assert fake.calls == [("complete", False)]


def test_worker_evaluation_uses_run_id_returned_by_complete() -> None:
    from app.worker import BacktestWorker, WorkerConfig

    candles = [candle(i, c) for i, c in enumerate(zigzag(20))]
    run_id = uuid4()
    fake = _RecordingDispatcher(candles, flat_quotes(20, 99.0, 100.0), complete_run_id=run_id)
    worker = BacktestWorker(
        fake, config=WorkerConfig(worker_id="w", heartbeat_s=0.005, event_consumers=("evaluator",))
    )
    worker._process(_fake_job(_ma_snapshot()))
    persisted = next(call for call in fake.calls if call[0] == "persist_evaluation")
    assert persisted[1] == run_id


# ---------------------------------------------------------------------------
# dispatcher SQL behavior against a scripted fake connection
# ---------------------------------------------------------------------------


class _ScriptedCursor:
    """Executes SQL statements in order; each script entry is
    (fetchone_result, rowcount) or an exception to raise."""

    def __init__(self, script: list[Any]) -> None:
        self._script = script  # shared: steps are consumed across cursors
        self.statements: list[str] = []

    def execute(self, sql: str, params: Any = None) -> None:
        self.statements.append(sql)
        step = self._script.pop(0) if self._script else (None, 0)
        if isinstance(step, Exception):
            raise step
        result, rowcount = step
        self.fetchone_result, self.rowcount = result, rowcount

    def executemany(self, sql: str, rows: Any) -> None:
        self.statements.append(sql)

    def fetchone(self) -> Any:
        return getattr(self, "fetchone_result", None)


class _FakeConn:
    def __init__(self, script: list[Any]) -> None:
        self.script = script
        self.commits = 0
        self.rollbacks = 0
        self.statements: list[str] = []

    def cursor(self) -> _ScriptedCursor:
        cursor = _ScriptedCursor(self.script)
        outer = self

        class _Recording:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def __getattr__(self, name):
                return getattr(cursor, name)

            def execute(self, sql: str, params: Any = None) -> None:
                outer.statements.append(sql)
                cursor.execute(sql, params)

            def executemany(self, sql: str, rows: Any) -> None:
                outer.statements.append(sql)
                cursor.executemany(sql, rows)

        return _Recording()  # type: ignore[return-value]

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def _dispatcher_with(script: list[Any]):
    from app.infrastructure.postgres.dispatcher import PostgresJobDispatcher

    dispatcher = PostgresJobDispatcher.__new__(PostgresJobDispatcher)
    dispatcher._conninfo = "fake"
    dispatcher._heartbeat = timedelta(seconds=30)
    dispatcher._lock = threading.RLock()
    dispatcher._conn = _FakeConn(script)
    return dispatcher


def test_dispatcher_rolls_back_on_sql_error_and_recovers() -> None:
    dispatcher = _dispatcher_with([RuntimeError("connection reset"), (None, 0)])
    with pytest.raises(RuntimeError):
        dispatcher.claim("worker-1", timedelta(seconds=120))
    assert dispatcher._conn.rollbacks == 1
    assert dispatcher._conn.commits == 0
    # the next call starts clean (no aborted-transaction poisoning)
    dispatcher.complete(uuid4(), uuid4())
    assert dispatcher._conn.commits == 1


def test_dispatcher_fail_after_lost_lease_never_touches_run_row() -> None:
    job_id, token = uuid4(), uuid4()
    dispatcher = _dispatcher_with([(None, 0)])  # jobs UPDATE matches 0 rows
    updated = dispatcher.fail(job_id, DomainError(ERR_VALIDATION, "boom"), False, token)
    assert updated is False
    # only the guarded jobs UPDATE ran — the completed run row was never flipped
    # and no BacktestFailed outbox event was written for a lost lease
    assert len(dispatcher._conn.statements) == 1
    assert "backtest_runs" not in dispatcher._conn.statements[0]
    assert dispatcher._conn.commits == 1


def test_dispatcher_fail_writes_backtest_failed_outbox() -> None:
    job_id, token = uuid4(), uuid4()
    dispatcher = _dispatcher_with([(None, 1), ((uuid4(),), 1), (None, 1)])
    updated = dispatcher.fail(job_id, DomainError(ERR_VALIDATION, "boom"), False, token)
    assert updated is True
    assert dispatcher._conn.commits == 1
    assert dispatcher._conn.rollbacks == 0
    assert any("BacktestFailed" in sql for sql in dispatcher._conn.statements)


def test_dispatcher_heartbeat_extends_by_configured_lease(monkeypatch) -> None:
    import app.infrastructure.postgres.dispatcher as dispatcher_module

    captured: dict[str, Any] = {}

    class _Cursor:
        rowcount = 1

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def execute(self, sql, params):
            captured.update(params)

    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def cursor(self):
            return _Cursor()

    class _FakePsycopg:
        @staticmethod
        def connect(conninfo, autocommit):
            captured["autocommit"] = autocommit
            return _Conn()

    monkeypatch.setattr(dispatcher_module, "psycopg", _FakePsycopg)
    dispatcher = _dispatcher_with([])
    job_id, token = uuid4(), uuid4()
    assert dispatcher.heartbeat(job_id, token, timedelta(seconds=300)) is True
    assert captured["extend"] == timedelta(seconds=300)  # never shrinks the lease
    assert captured["autocommit"] is True


# ---------------------------------------------------------------------------
# round-2 fixes: sl/tp trade facts, equity PK uniqueness, consumer isolation,
# outbox aggregate columns
# ---------------------------------------------------------------------------


def _risk_snapshot() -> ExperimentSnapshot:
    from app.domain.backtest import RiskPolicy

    snap = _ma_snapshot()
    snap.risk_policy = RiskPolicy(stop_loss_pct=5.0, take_profit_pct=20.0,
                                  intrabar_priority="stop_loss_first")
    return snap


def test_stop_loss_exit_carries_frozen_sl_price() -> None:
    closes = [100.0] * 4 + [110.0] * 5  # BUY cross at candle 3, limit 100
    candles = [candle(i, c) for i, c in enumerate(closes)]
    quotes = [
        BBO(provider="binance", symbol="SOLUSDT",
            event_time=T0 + timedelta(milliseconds=0),
            bid=90.0, bid_qty=1.0, ask=95.0, ask_qty=1.0, update_id=None, source_sequence=1),
        # entry fills at ask 99 <= 110, after the signal candle's close
        BBO(provider="binance", symbol="SOLUSDT",
            event_time=T0 + timedelta(milliseconds=4 * 60_000 + 60_100),
            bid=98.0, bid_qty=1.0, ask=99.0, ask_qty=1.0, update_id=None, source_sequence=2),
        # bid crashes through the 5% SL level (~94.05): stop-loss exit
        BBO(provider="binance", symbol="SOLUSDT",
            event_time=T0 + timedelta(milliseconds=5 * 60_000 + 60_200),
            bid=90.0, bid_qty=1.0, ask=91.0, ask_qty=1.0, update_id=None, source_sequence=3),
    ]
    result = DeterministicEngine().run(_risk_snapshot(), candles, quotes)
    trade = result.trades[0]
    assert trade.exit_reason == "stop_loss"
    # frozen at entry: 99 * (1 - 0.05) — design.md trades CHECK requires sl_price
    assert trade.sl_price == pytest.approx(99.0 * 0.95)
    assert trade.tp_price == pytest.approx(99.0 * 1.20)
    assert trade.exit_price == 90.0


def test_equity_point_times_unique_despite_same_ms_boundaries() -> None:
    closes = zigzag(30)
    candles = [candle(i, c) for i, c in enumerate(closes)]
    quotes = [
        # a BBO at exactly each candle-close ms plus one at open+1ms: the merge
        # rule (BBO priority 0 first) makes same-timestamp marks deliberate
        BBO(provider="binance", symbol="SOLUSDT",
            event_time=T0 + timedelta(milliseconds=i * 60_000 + 59_999),
            bid=c - 0.05, bid_qty=1.0, ask=c + 0.05, ask_qty=1.0,
            update_id=None, source_sequence=2 * i + 1)
        for i, c in enumerate(closes)
    ] + [
        BBO(provider="binance", symbol="SOLUSDT",
            event_time=T0 + timedelta(milliseconds=i * 60_000 + 1),
            bid=c - 0.1, bid_qty=1.0, ask=c + 0.1, ask_qty=1.0,
            update_id=None, source_sequence=2 * i + 2)
        for i, c in enumerate(closes)
    ]
    quotes.sort(key=lambda q: (q.event_time, q.source_sequence))
    result = DeterministicEngine().run(_ma_snapshot(), candles, quotes)
    times = [p.point_time for p in result.equity_points]
    assert len(times) == len(set(times))  # equity_points PK (run, point_time) holds


def test_outbox_rows_carry_aggregate_columns() -> None:
    # fail() happy path: jobs UPDATE -> runs UPDATE RETURNING -> BacktestFailed
    dispatcher = _dispatcher_with([(None, 1), ((uuid4(),), 1), (None, 1)])
    dispatcher.fail(uuid4(), DomainError(ERR_VALIDATION, "boom"), False, uuid4())
    outbox = [sql for sql in dispatcher._conn.statements if "domain_events" in sql]
    assert outbox, "expected a BacktestFailed outbox insert"
    assert all("aggregate_type" in sql and "aggregate_id" in sql for sql in outbox)


class _EvalCrashDispatcher(_RecordingDispatcher):
    def persist_evaluation(self, run_id, evaluation):
        self._record(("persist_evaluation", run_id))
        raise RuntimeError("evaluator store down")


def test_evaluation_consumer_failure_never_fails_completed_job() -> None:
    from app.worker import BacktestWorker, WorkerConfig

    candles = [candle(i, c) for i, c in enumerate(zigzag(20))]
    fake = _EvalCrashDispatcher(candles, flat_quotes(20, 99.0, 100.0))
    worker = BacktestWorker(
        fake, config=WorkerConfig(worker_id="w", heartbeat_s=0.005, event_consumers=("evaluator",))
    )
    worker._process(_fake_job(_ma_snapshot()))
    kinds = [call[0] for call in fake.calls]
    # completed normally; the consumer crash was contained — no fail() call
    assert any(call[0] == "complete" and call[1] is True for call in fake.calls)
    assert "persist_evaluation" in kinds
    assert not any(call[0] == "fail" for call in fake.calls)
