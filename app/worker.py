"""Backtest worker entrypoint.

The worker is the *same image* as the `research` service with a different
entrypoint (design.md §1.3): claim jobs from
`backtest_jobs` via `FOR UPDATE SKIP LOCKED` + lease, execute the immutable
snapshot through the one and only `DeterministicEngine`, persist facts and the
`BacktestCompleted` outbox event in the same transaction, and heart-beat the
lease while a job runs. `EVENT_CONSUMERS=evaluator` (design.md §5.7.2 config B)
lets this process also run the evaluator consumer; production Compose uses the
dedicated event-worker process.

The `fixture` subcommand is the verification harness for
`data/formatted/<symbol>/<date>/`: it builds the exact snapshot the queue path
would use, replays the dataset N times, asserts all canonical result hashes are
identical (AC-01), evaluates the first result, and prints the structural
summary required by the evidence record (signal counts, order statuses, settled
trades, exit reasons, metrics). Same engine, same snapshot semantics — only the
job source differs.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Self
from uuid import NAMESPACE_URL, uuid5

from .domain.backtest import ExperimentSnapshot, MarketSnapshot, Result
from .domain.common import (
    ERR_DATASET_TOO_LARGE,
    ERR_INSUFFICIENT_CANDLES,
    ERR_INVALID_BBO_REPLAY,
    ERR_INVALID_SIGNAL,
    ERR_LOOK_AHEAD,
    ERR_MISSING_FINAL_BBO,
    ERR_MISSING_PRIOR_BBO,
    ERR_STRATEGY_EXCEPTION,
    ERR_UNKNOWN_STRATEGY,
    ERR_VALIDATION,
    DomainError,
)
from .domain.evaluation import EvaluationInput, EvaluationPolicy
from .domain.job import BacktestJob
from .domain.market import BBO, Candle
from .domain.strategy import (
    ChildDefinition,
    CombinationPolicy,
    CompositeDefinition,
    Reference,
)
from .config import Settings
from .infrastructure.dataset import DatasetInfo, load_fixture_dataset
from .services.backtest_engine import DeterministicEngine, canonical_result_hash
from .services.evaluator import DeterministicEvaluator

# deterministic input errors: a retry replays identical bytes and fails identically,
# so they exhaust nothing but CPU — fail the job instead of retrying (design.md §8.3)
_NON_RETRYABLE = {
    ERR_VALIDATION,
    ERR_UNKNOWN_STRATEGY,
    ERR_LOOK_AHEAD,
    ERR_INSUFFICIENT_CANDLES,
    ERR_DATASET_TOO_LARGE,
    ERR_INVALID_BBO_REPLAY,
    ERR_MISSING_PRIOR_BBO,
    ERR_MISSING_FINAL_BBO,
    ERR_INVALID_SIGNAL,
    ERR_STRATEGY_EXCEPTION,
}

_PERIODS_PER_YEAR = {
    "1m": 525_600,
    "5m": 105_120,
    "15m": 35_040,
    "30m": 17_520,
    "1h": 8_760,
    "2h": 4_380,
    "4h": 2_190,
    "1d": 365,
}

EVALUATOR_VERSION = "v1"


def default_evaluation_policy(timeframe: str) -> EvaluationPolicy:
    # unknown timeframe -> periods_per_year 0 -> Sharpe NULL (cannot annualize)
    return EvaluationPolicy(
        evaluator_version=EVALUATOR_VERSION,
        periods_per_year=_PERIODS_PER_YEAR.get(timeframe, 0),
        zero_pnl_counts_as_win=False,
        stddev_ddof=1,
        min_periods_for_sharpe=30,  # design.md: "EvaluationPolicy.min_periods_for_sharpe (v1 = 30)"
        risk_free_rate=0.0,
    )


def execute_job(
    engine: DeterministicEngine,
    snapshot: ExperimentSnapshot,
    candles: list[Candle],
    bbo: list[BBO],
    sentiment_windows: list[Any] | None = None,
) -> Result:
    """The single execution path shared by queue mode and fixture mode."""
    if sentiment_windows is None:
        return engine.run(snapshot, candles, bbo)
    return engine.run(snapshot, candles, bbo, sentiment_windows)


# ----------------------------------------------------------------------------
# queue mode
# ----------------------------------------------------------------------------


@dataclass
class WorkerConfig:
    worker_id: str
    poll_interval_s: float = 0.5  # specs/experiment.md: 500 ms idle poll …
    poll_max_s: float = 2.0  # … backing off to 2 s while the queue stays empty
    lease_s: float = 120.0
    heartbeat_s: float = 30.0
    event_consumers: tuple[str, ...] = ()


def _queue_log(
    level: str,
    event: str,
    worker_id: str,
    job: BacktestJob | None = None,
    **fields: Any,
) -> None:
    payload: dict[str, Any] = {
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "level": level,
        "service": "research-worker",
        "operation": event,
        "worker_id": worker_id,
        **fields,
    }
    if job is not None:
        payload.update(
            {
                "job_id": str(job.id),
                "experiment_id": str(job.experiment_id),
                "run_id": str(job.run_id) if job.run_id else None,
                "correlation_id": job.correlation_id,
                "attempt": job.attempt,
            }
        )
    print(
        json.dumps(payload, sort_keys=True, separators=(",", ":")),
        file=sys.stderr if level in {"warning", "error"} else sys.stdout,
        flush=True,
    )


class _Heartbeat:
    """Extends the lease to its full configured length every `heartbeat_s`."""

    def __init__(
        self, dispatcher: Any, job: BacktestJob, interval_s: float, lease_s: float
    ) -> None:
        self._dispatcher = dispatcher
        self._job = job
        self._interval_s = interval_s
        self._lease_s = lease_s
        self._stop = threading.Event()
        self._lost = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="lease-heartbeat", daemon=True)

    def _loop(self) -> None:
        while not self._stop.wait(self._interval_s):
            try:
                if not self._dispatcher.heartbeat(
                    self._job.id, self._job.lease_token, timedelta_seconds(self._lease_s)
                ):
                    self._lost.set()
                    return
            except Exception:  # noqa: BLE001, S112 — transient DB error: next beat retries
                continue

    def __enter__(self) -> Self:
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        self._thread.join(timeout=self._interval_s * 2)

    @property
    def lost(self) -> bool:
        return self._lost.is_set()


class BacktestWorker:
    def __init__(
        self,
        dispatcher: Any,
        engine: DeterministicEngine | None = None,
        evaluator: DeterministicEvaluator | None = None,
        config: WorkerConfig | None = None,
    ) -> None:
        self._dispatcher = dispatcher
        self._engine = engine if engine is not None else DeterministicEngine()
        self._evaluator = evaluator if evaluator is not None else DeterministicEvaluator()
        self._config = config if config is not None else WorkerConfig(worker_id="worker-v2")
        self._stopped = threading.Event()

    def stop(self, *_: object) -> None:
        self._stopped.set()

    def run_forever(self) -> None:
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:  # signal.signal only works on the main thread (tests run off it)
                signal.signal(sig, self.stop)
            except ValueError:
                pass
        poll_s = self._config.poll_interval_s
        while not self._stopped.is_set():
            try:
                job = self._dispatcher.claim(
                    self._config.worker_id, timedelta_seconds(self._config.lease_s)
                )
            except Exception:  # noqa: BLE001 — a DB hiccup must not kill the worker
                self._stopped.wait(poll_s)
                continue
            if job is None:
                self._stopped.wait(poll_s)
                poll_s = min(poll_s * 2, self._config.poll_max_s)
                continue
            poll_s = self._config.poll_interval_s
            self._process(job)

    def _process(self, job: BacktestJob) -> None:
        assert job.lease_token is not None
        try:
            if job.run_already_completed:
                # AC-05c/AC-05d: the run was completed by an earlier lease;
                # mark the job completed without touching the engine or facts
                completed, _ = self._dispatcher.complete(job.id, job.lease_token)
                if not completed:
                    _queue_log(
                        "warning", "lease_guard_rejected", self._config.worker_id, job
                    )
                return
            with _Heartbeat(
                self._dispatcher, job, self._config.heartbeat_s, self._config.lease_s
            ) as beat:
                candles, quotes = self._dispatcher.load_dataset(job.snapshot)
                sentiment_windows = None
                if hasattr(self._dispatcher, "load_sentiment_windows"):
                    sentiment_windows = self._dispatcher.load_sentiment_windows(
                        job.snapshot, candles
                    )
                engine = self._engine
                load_runtime_spec = getattr(self._dispatcher, "load_runtime_spec", None)
                if load_runtime_spec is not None:
                    runtime_spec = load_runtime_spec(job.snapshot.strategy)
                    if runtime_spec is not None:
                        engine = engine.with_runtime_spec(runtime_spec)
                result = execute_job(
                    engine, job.snapshot, candles, quotes, sentiment_windows
                )
                lost = beat.lost
            if lost:
                _queue_log(
                    "warning", "lease_lost", self._config.worker_id, job,
                    result="discarded",
                )
                return
            completed, run_id = self._dispatcher.complete(job.id, job.lease_token, result)
            if not completed:
                _queue_log(
                    "warning", "lease_guard_rejected", self._config.worker_id, job
                )
                return
            if "evaluator" in self._config.event_consumers:
                try:
                    self._consume_evaluation(job, result, run_id or job.run_id)
                except Exception as err:  # noqa: BLE001 — job is already completed; an
                    # evaluation failure must not fail() the completed job/run
                    _queue_log(
                        "error", "evaluation_failed", self._config.worker_id, job,
                        error_code=type(err).__name__,
                    )
            _queue_log(
                "info", "backtest_completed", self._config.worker_id, job,
                result="success", trade_count=len(result.trades),
                duration_ms=result.duration_ms,
            )
        except DomainError as err:
            retryable = err.code not in _NON_RETRYABLE
            self._dispatcher.fail(job.id, err, retryable, job.lease_token)
            _queue_log(
                "error", "backtest_failed", self._config.worker_id, job,
                result="failure", error_code=err.code, retryable=retryable,
            )
        except Exception as err:  # noqa: BLE001 — worker must survive anything
            self._dispatcher.fail(job.id, err, True, job.lease_token)
            _queue_log(
                "error", "backtest_crashed", self._config.worker_id, job,
                result="failure", error_code=type(err).__name__, retryable=True,
            )

    def _consume_evaluation(self, job: BacktestJob, result: Result, run_id: Any) -> None:
        if run_id is None:
            _queue_log(
                "warning", "evaluation_skipped", self._config.worker_id, job,
                error_code="missing_run_id",
            )
            return
        policy = default_evaluation_policy(job.snapshot.market.timeframe)
        evaluation = self._evaluator.evaluate(
            EvaluationInput(
                run_id=run_id,
                initial_equity=job.snapshot.initial_equity,
                trades=result.trades,
                equity_points=result.equity_points,
            ),
            policy,
        )
        self._dispatcher.persist_evaluation(run_id, evaluation)


def timedelta_seconds(seconds: float):
    from datetime import timedelta

    return timedelta(seconds=seconds)


def run_queue_mode() -> int:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is required for queue mode", file=sys.stderr)
        return 2
    from .infrastructure.postgres.dispatcher import PostgresJobDispatcher

    dispatcher = PostgresJobDispatcher(database_url)
    consumers = tuple(
        c.strip()
        for c in os.environ.get("EVENT_CONSUMERS", "").split(",")
        if c.strip()
    )
    settings = Settings.from_env()
    config = WorkerConfig(
        worker_id=os.environ.get("WORKER_ID", "worker-v2"),
        poll_interval_s=float(os.environ.get("POLL_INTERVAL_S", "1.0")),
        lease_s=settings.worker_lease_s,
        heartbeat_s=settings.worker_heartbeat_s,
        event_consumers=consumers,
    )
    worker = BacktestWorker(dispatcher, config=config)
    _queue_log(
        "info",
        "worker_started",
        config.worker_id,
        consumers=consumers or "none",
        lease_seconds=config.lease_s,
        heartbeat_seconds=config.heartbeat_s,
    )
    try:
        worker.run_forever()
    finally:
        dispatcher.close()
    return 0


# ----------------------------------------------------------------------------
# fixture mode (verification harness)
# ----------------------------------------------------------------------------


def _candidate_fingerprint_params(candidate: Any) -> Any:
    """JSON-serializable view of a candidate for the fixture fingerprint."""
    if isinstance(candidate, CompositeDefinition):
        return {
            "strategy_id": candidate.strategy_id,
            "version": candidate.version,
            "children": [
                {
                    "strategy_id": c.strategy_id,
                    "version": c.version,
                    "parameters": c.parameters,
                    "weight": c.weight,
                }
                for c in candidate.children
            ],
            "policy": {
                "name": candidate.combination.policy,
                "threshold": candidate.combination.threshold,
                "encoding": candidate.combination.encoding,
            },
        }
    return candidate


def build_fixture_snapshot(
    reference: Reference,
    params: dict[str, Any],
    info: DatasetInfo,
    candidate: Any = None,
    *,
    initial_equity: float = 100.0,
    fixed_notional: float = 10.0,
    fee_bps: int = 10,
    slippage_bps: int = 0,
) -> ExperimentSnapshot:
    from .domain.common import (
        FILL_POLICY_BBO_LIMIT,
        OPEN_POSITION_LAST_EXECUTABLE_BBO,
        POSITION_POLICY_ONE_NET,
    )

    candidate = params if candidate is None else candidate
    fingerprint = (
        f"fixture:{info.dataset_version}:{reference.strategy_id}@{reference.version}:"
        f"{json.dumps(_candidate_fingerprint_params(candidate), sort_keys=True)}"
    )
    return ExperimentSnapshot(
        experiment_id=uuid5(NAMESPACE_URL, fingerprint),
        owner_id=None,
        strategy=reference,
        candidate_definition=candidate,
        candidate_hash=uuid5(NAMESPACE_URL, f"candidate:{fingerprint}").hex,
        market=MarketSnapshot(
            dataset_version=info.dataset_version,
            revision_no=1,
            provider=info.provider,
            symbol=info.symbol,
            timeframe=info.timeframe,
            range_from=info.range_from,
            range_to=info.range_to,
            candle_count=info.candle_count,
            content_hash=info.content_hash,
            bbo_content_hash=info.bbo_content_hash,
        ),
        initial_equity=initial_equity,
        fixed_notional=fixed_notional,
        leverage=1.0,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        fill_policy=FILL_POLICY_BBO_LIMIT,
        position_policy=POSITION_POLICY_ONE_NET,
        open_position_at_end=OPEN_POSITION_LAST_EXECUTABLE_BBO,
        risk_policy=None,
        evaluator_version=EVALUATOR_VERSION,
        created_at=datetime(2026, 3, 5, tzinfo=UTC),
    )


def parse_strategy(spec: str) -> tuple[Reference, dict[str, Any]]:
    """`ma_cross@v1`, `ma_cross@v1:fast=10,slow=30` → (Reference, params)."""
    params: dict[str, Any] = {}
    reference_part, _, param_part = spec.partition(":")
    if param_part:
        for pair in param_part.split(","):
            key, _, value = pair.partition("=")
            params[key.strip()] = int(value) if value.strip().isdigit() else value.strip()
    strategy_id, _, version = reference_part.partition("@")
    return Reference(strategy_id.strip(), (version or "v1").strip()), params


def parse_child(spec: str) -> ChildDefinition:
    """`ma_cross@v1:fast=10,slow=30,weight=0.5` → ChildDefinition."""
    reference, params = parse_strategy(spec)
    weight = float(params.pop("weight", 1.0))
    return ChildDefinition(
        strategy_id=reference.strategy_id,
        version=reference.version,
        parameters=params,
        weight=weight,
    )


def build_composite(
    params: dict[str, Any], children: list[ChildDefinition]
) -> CompositeDefinition:
    return CompositeDefinition(
        strategy_id="composite",
        version="v1",
        children=children,
        combination=CombinationPolicy(
            policy=params.get("policy", "weighted_vote"),
            threshold=float(params.get("threshold", 0.5)),
            encoding={"BUY": 1, "HOLD": 0, "SELL": -1},
        ),
    )


def run_fixture_mode(args: argparse.Namespace) -> int:
    candles, quotes, info = load_fixture_dataset(
        args.dataset, provider=args.provider, symbol=args.symbol, timeframe=args.timeframe
    )
    engine = DeterministicEngine()
    evaluator = DeterministicEvaluator()
    policy = default_evaluation_policy(args.timeframe)

    reports: dict[str, Any] = {
        "dataset": {
            "path": str(args.dataset),
            "provider": info.provider,
            "symbol": info.symbol,
            "timeframe": info.timeframe,
            "candles": info.candle_count,
            "bbo_rows": len(quotes),
            "ohlcv_sha256": info.content_hash,
            "bbo_sha256": info.bbo_content_hash,
        },
        "strategies": [],
        "determinism_ok": True,
    }
    all_deterministic = True
    runs = max(1, args.runs)

    for spec in args.strategy:
        reference, params = parse_strategy(spec)
        candidate: Any = params
        child_defs = [parse_child(c) for c in (args.child or [])]
        if reference.strategy_id == "composite":
            if len(child_defs) < 2:
                print("composite strategy requires >= 2 --child entries", file=sys.stderr)
                return 2
            candidate = build_composite(params, child_defs)
        snapshot = build_fixture_snapshot(reference, params, info, candidate)
        hashes: list[str] = []
        result: Result | None = None
        for _ in range(runs):
            result = execute_job(engine, snapshot, candles, quotes)
            hashes.append(canonical_result_hash(result))
        assert result is not None
        deterministic = len(set(hashes)) == 1
        all_deterministic = all_deterministic and deterministic

        evaluation = evaluator.evaluate(
            EvaluationInput(
                run_id=snapshot.experiment_id,
                initial_equity=snapshot.initial_equity,
                trades=result.trades,
                equity_points=result.equity_points,
            ),
            policy,
        )
        exit_reasons: dict[str, int] = {}
        for trade in result.trades:
            reason = trade.exit_reason or "open"
            exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
        order_statuses: dict[str, int] = {}
        for order in result.orders:
            order_statuses[order.status] = order_statuses.get(order.status, 0) + 1
        report = {
            "strategy": f"{reference.strategy_id}@{reference.version}",
            "params": params,
            "snapshot_hash": snapshot.candidate_hash,
            "runs": runs,
            "result_hash": hashes[0],
            "deterministic": deterministic,
            "candles_read": result.candles_read,
            "warm_up_candles": result.warm_up_candles,
            "signals": {
                "total": len(result.signals),
                "buy": sum(1 for s in result.signals if s.action == "BUY"),
                "sell": sum(1 for s in result.signals if s.action == "SELL"),
            },
            "orders": {"total": len(result.orders), "by_status": order_statuses},
            "trades": {
                "total": len(result.trades),
                "settled": sum(1 for t in result.trades if t.exit_time is not None),
                "open": sum(1 for t in result.trades if t.exit_time is None),
                "by_exit_reason": exit_reasons,
            },
            "equity_points": len(result.equity_points),
            "duration_ms_last_run": result.duration_ms,
            "evaluation": {
                "evaluator_version": evaluation.evaluator_version,
                "total_return_pct": round(evaluation.total_return_pct, 6),
                "win_rate_pct": round(evaluation.win_rate_pct, 4),
                "max_drawdown_pct": round(evaluation.max_drawdown_pct, 6),
                "trade_count": evaluation.trade_count,
                "open_trade_count": evaluation.open_trade_count,
                "profit_factor": None if evaluation.profit_factor is None else round(evaluation.profit_factor, 6),
                "sharpe_ratio": None if evaluation.sharpe_ratio is None else round(evaluation.sharpe_ratio, 6),
                "avg_trade_pct": None if evaluation.avg_trade_pct is None else round(evaluation.avg_trade_pct, 6),
            },
        }
        reports["strategies"].append(report)

        if not args.json:
            print(f"\n=== {report['strategy']} params={params} ===")
            print(f"runs={runs} result_hash={hashes[0]} deterministic={deterministic}")
            print(
                f"signals: {report['signals']['total']} "
                f"(BUY {report['signals']['buy']} / SELL {report['signals']['sell']})"
            )
            print(f"orders: {report['orders']['total']} {order_statuses}")
            print(f"trades: {report['trades']['total']} ({report['trades']['by_exit_reason']})")
            ev = report["evaluation"]
            print(
                "evaluation: return={total_return_pct}% win_rate={win_rate_pct}% "
                "mdd={max_drawdown_pct}% pf={profit_factor} sharpe={sharpe_ratio} "
                "avg_trade={avg_trade_pct}%".format(**ev)
            )

    reports["determinism_ok"] = all_deterministic
    if args.json:
        print(json.dumps(reports, indent=2, sort_keys=True))
    else:
        print(f"\ndeterminism across {runs} runs: {'OK' if all_deterministic else 'FAILED'}")
    return 0 if all_deterministic else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.worker", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="mode", required=True)

    sub.add_parser("queue", help="claim backtest_jobs from PostgreSQL (DATABASE_URL)")

    fixture = sub.add_parser("fixture", help="verify a data/formatted dataset replay")
    fixture.add_argument("--dataset", required=True, help="directory with ohlcv.csv + bbo.csv")
    fixture.add_argument(
        "--strategy",
        action="append",
        required=True,
        help=(
            "strategy spec: ma_cross@v1[:fast=20,slow=50] (repeatable); "
            "composite@v1[:policy=weighted_vote,threshold=0.3] plus --child entries"
        ),
    )
    fixture.add_argument(
        "--child",
        action="append",
        help="composite child spec: ma_cross@v1:fast=10,slow=30,weight=0.5 (repeatable)",
    )
    fixture.add_argument("--runs", type=int, default=5, help="replays per strategy (default 5)")
    fixture.add_argument("--json", action="store_true", help="print the machine-readable report")
    fixture.add_argument("--provider", default="binance")
    fixture.add_argument("--symbol", default="SOLUSDT")
    fixture.add_argument("--timeframe", default="1m")

    args = parser.parse_args(argv)
    if args.mode == "queue":
        return run_queue_mode()
    return run_fixture_mode(args)


if __name__ == "__main__":
    sys.exit(main())
