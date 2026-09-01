"""Queue-mode integration tests against a real PostgreSQL (blueprint DDL).

Run:
    docker compose -f docker-compose.test.yml up -d --wait
    TEST_DATABASE_URL=postgres://cryptobot:cryptobot@127.0.0.1:55433/cryptobot?sslmode=disable \
        uv run pytest tests/integration -q

The schema is the design.md §8 DDL subset (tests/integration/schema.sql, loaded
by the compose init script). These tests verify the SQL the dispatcher issues —
claim/UPSERT/complete/fail/outbox — against real constraints, which the
scripted-fake unit tests cannot.
"""

from __future__ import annotations

import math
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

psycopg = pytest.importorskip("psycopg")

DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgres://cryptobot:cryptobot@127.0.0.1:55433/cryptobot?sslmode=disable",
)

try:
    psycopg.connect(DATABASE_URL, connect_timeout=3).close()
    _DB_UP = True
except Exception:  # noqa: BLE001
    _DB_UP = False

pytestmark = pytest.mark.skipif(not _DB_UP, reason="test PostgreSQL not running (docker compose -f docker-compose.test.yml up -d)")

T0 = datetime(2026, 3, 4, tzinfo=UTC)
TABLES = (
    "domain_events, evaluations, equity_points, run_signals, trades, backtest_runs,"
    " backtest_jobs, experiments, strategy_versions, strategy_definitions,"
    " market_dataset_bbo, market_dataset_candles, market_datasets, market_pairs, users"
)


@pytest.fixture()
def dispatcher():
    from app.infrastructure.postgres.dispatcher import PostgresJobDispatcher

    d = PostgresJobDispatcher(DATABASE_URL)
    with d._conn.cursor() as cur:  # clean slate per test
        cur.execute(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE")
    d._conn.commit()
    yield d
    d._conn.rollback()
    with d._conn.cursor() as cur:
        cur.execute(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE")
    d._conn.commit()
    d.close()


def _rows(d, sql, params=()):
    with d._conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def zigzag(n: int, period: int = 8, base: float = 100.0, amp: float = 5.0):
    return [base + amp * math.sin(2 * math.pi * i / period) for i in range(n)]


def seed_experiment(d, candidate: dict, strategy_id: str = "composite") -> tuple:
    """Seed users → pair → dataset (candles+BBO) → strategies → experiment → job."""
    closes = zigzag(60)
    candles = [
        (T0 + timedelta(minutes=i), T0 + timedelta(minutes=i, seconds=59, milliseconds=999),
         c, c + 0.1, c - 0.1, c, 10.0, 5)
        for i, c in enumerate(closes)
    ]
    quotes = []
    seq = 0
    for i, c in enumerate(closes):
        for offset in (10_000, 40_000):
            seq += 1
            quotes.append(
                (T0 + timedelta(milliseconds=i * 60_000 + offset), seq,
                 c - 0.05, 100.0, c + 0.05, 100.0, None)
            )
    dataset_version = f"itest-{uuid4().hex[:8]}"
    with d._conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (email, password_hash, display_name, role) "
            "VALUES (%s, %s, %s, 'RESEARCHER') RETURNING id",
            (f"u-{uuid4().hex[:8]}@test.local", "x", "Integration Tester"),
        )
        user_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO market_pairs (symbol, base, quote, provider) "
            "VALUES ('SOLUSDT', 'SOL', 'USDT', 'binance')"
        )
        cur.execute(
            """
            INSERT INTO market_datasets (dataset_version, provider, symbol, timeframe,
                                         range_from, range_to, revision_no, candle_count, content_hash)
            VALUES (%s, 'binance', 'SOLUSDT', '1m', %s, %s, 1, %s, %s) RETURNING id
            """,
            (dataset_version, T0, candles[-1][1], len(candles), "h" * 64),
        )
        dataset_id = cur.fetchone()[0]
        cur.executemany(
            "INSERT INTO market_dataset_candles (market_dataset_id, open_time, close_time, open,"
            " high, low, close, volume, trade_count) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            [(dataset_id, *row) for row in candles],
        )
        cur.executemany(
            "INSERT INTO market_dataset_bbo (market_dataset_id, event_time, source_sequence,"
            " bid, bid_qty, ask, ask_qty, update_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            [(dataset_id, *row) for row in quotes],
        )
        versions = {}
        for sid, family in (("ma_cross", "trend"), ("ema_cross", "trend"), ("composite", None)):
            cur.execute(
                "INSERT INTO strategy_definitions (strategy_id, display_name, family, is_composite)"
                " VALUES (%s, %s, %s, %s)",
                (sid, sid, family, family is None),
            )
            cur.execute(
                "INSERT INTO strategy_versions (strategy_id, version, parameters_schema,"
                " default_params, input_requirements, overlay_types, code_fingerprint)"
                " VALUES (%s, 'v1', '{}', '{}', '[]', '[]', %s) RETURNING id",
                (sid, "f" * 64),
            )
            versions[sid] = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO experiments (owner_id, strategy_version_id, candidate_definition,
                                     candidate_hash, market_dataset_id, bbo_dataset_hash,
                                     evaluator_version, replay_range_from, replay_range_to)
            VALUES (%s, %s, %s, %s, %s, %s, 'v1', %s, %s) RETURNING id
            """,
            (user_id, versions[strategy_id], psycopg.types.json.Jsonb(candidate),
             "c" * 64, dataset_id, "b" * 64, candles[0][0], candles[-1][1]),
        )
        experiment_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO backtest_jobs (id, experiment_id, status, priority)"
            " VALUES (%s, %s, 'queued', 100)",
            (job_id := uuid4(), experiment_id),
        )
    d._conn.commit()
    return job_id, experiment_id


COMPOSITE_CANDIDATE = {
    "strategy_id": "composite",
    "version": "v1",
    "children": [
        {"strategy_id": "ma_cross", "version": "v1",
         "parameters": {"fast": 3, "slow": 5}, "weight": 0.6},
        {"strategy_id": "ema_cross", "version": "v1",
         "parameters": {"fast": 3, "slow": 5}, "weight": 0.4},
    ],
    "policy": {"name": "weighted_vote", "threshold": 0.3,
               "encoding": {"BUY": 1, "HOLD": 0, "SELL": -1}},
}


def _process_job(d, job_id):
    from app.worker import BacktestWorker, WorkerConfig

    worker = BacktestWorker(
        d,
        config=WorkerConfig(
            worker_id="itest-worker",
            heartbeat_s=0.05,
            lease_s=120.0,
            event_consumers=("evaluator",),
        ),
    )
    job = d.claim("itest-worker", timedelta(seconds=120))
    assert job is not None and job.id == job_id
    worker._process(job)
    return job


def test_end_to_end_composite_claim_run_complete_evaluate(dispatcher) -> None:
    from app.infrastructure.postgres.store import Store

    job_id, experiment_id = seed_experiment(dispatcher, COMPOSITE_CANDIDATE)
    _process_job(dispatcher, job_id)

    # job + run lifecycle
    assert _rows(dispatcher, "SELECT status FROM backtest_jobs WHERE id = %s", (job_id,))[0][0] == "completed"
    run = _rows(
        dispatcher,
        "SELECT id, status, candles_read, signals_count, worker_id, started_at, finished_at"
        " FROM backtest_runs WHERE experiment_id = %s",
        (experiment_id,),
    )
    assert len(run) == 1
    run_id, status, candles_read, signals_count, worker_id, started_at, finished_at = run[0]
    assert status == "completed"
    assert candles_read == 60
    assert signals_count > 0
    assert worker_id == "itest-worker"
    assert started_at is not None and finished_at is not None

    # facts: counts match, no duplicates
    trades = _rows(dispatcher, "SELECT count(*) FROM trades WHERE backtest_run_id = %s", (run_id,))
    signals = _rows(dispatcher, "SELECT count(*) FROM run_signals WHERE backtest_run_id = %s", (run_id,))
    equity = _rows(dispatcher, "SELECT count(*) FROM equity_points WHERE backtest_run_id = %s", (run_id,))
    assert trades[0][0] > 0
    assert signals[0][0] == signals_count
    assert equity[0][0] > 0
    trade_costs = _rows(
        dispatcher,
        """
        SELECT entry_notional,exit_notional,fee_paid,spread_cost,slippage_cost,
               gross_pnl,net_pnl,pnl_absolute
        FROM trades WHERE backtest_run_id=%s AND exit_time IS NOT NULL LIMIT 1
        """,
        (run_id,),
    )[0]
    assert all(value is not None for value in trade_costs)
    assert float(trade_costs[6]) == pytest.approx(float(trade_costs[7]))
    assert float(trade_costs[6]) == pytest.approx(
        float(trade_costs[5]) - float(trade_costs[2])
        - float(trade_costs[3]) - float(trade_costs[4])
    )
    projected_trade = Store(DATABASE_URL).list_experiment_trades(experiment_id)[0]
    assert {
        "symbol", "quote_currency", "entry_notional", "exit_notional", "spread_cost",
        "gross_pnl", "net_pnl", "pnl_absolute",
    } <= set(projected_trade)
    first_page = Store(DATABASE_URL).list_experiment_trade_page(experiment_id, after_sequence=None, limit=1)
    assert len(first_page["trades"]) == 1
    assert first_page["next_cursor"] == first_page["trades"][0]["sequence_no"]
    second_page = Store(DATABASE_URL).list_experiment_trade_page(
        experiment_id, after_sequence=first_page["next_cursor"], limit=1
    )
    assert second_page["trades"] == [] or second_page["trades"][0]["sequence_no"] > first_page["next_cursor"]
    execution_markers = Store(DATABASE_URL).list_experiment_execution_markers(experiment_id)
    assert execution_markers and execution_markers[0]["entry_time"] is not None
    assert execution_markers[0]["entry_price"] is not None
    # equity PK holds (collapse verified by insert succeeding)

    # composite evidence: child_signals carries score + children (AC-09)
    child = _rows(
        dispatcher,
        "SELECT child_signals FROM run_signals WHERE backtest_run_id = %s LIMIT 1",
        (run_id,),
    )[0][0]
    assert child["score"] is not None and child["action"] in ("BUY", "SELL")
    assert len(child["children"]) == 2

    # evaluation references the REAL run id (FK satisfied) — config B works
    evaluation = _rows(
        dispatcher,
        "SELECT evaluator_version, trade_count, win_rate_pct FROM evaluations"
        " WHERE backtest_run_id = %s",
        (run_id,),
    )
    assert len(evaluation) == 1
    assert evaluation[0][0] == "v1"
    metrics = Store(DATABASE_URL).get_experiment(experiment_id)["metrics"]
    assert metrics is not None
    assert metrics["wins"] + metrics["losses"] <= metrics["trade_count"]
    assert isinstance(metrics["net_profit"], float)

    # outbox: BacktestStarted + BacktestCompleted + StrategyEvaluated, aggregate columns set
    events = dict(
        _rows(
            dispatcher,
            "SELECT event_type, count(*) FROM domain_events"
            " WHERE aggregate_type IN ('backtest_run','evaluation') GROUP BY event_type",
        )
    )
    assert events.get("BacktestStarted") == 1
    assert events.get("BacktestCompleted") == 1
    assert events.get("StrategyEvaluated") == 1
    orphans = _rows(
        dispatcher,
        "SELECT count(*) FROM domain_events e WHERE aggregate_type = 'backtest_run'"
        " AND NOT EXISTS (SELECT 1 FROM backtest_runs r WHERE r.id = e.aggregate_id)",
    )
    assert orphans[0][0] == 0


def test_fail_after_complete_never_flips_completed_run(dispatcher) -> None:
    from app.domain.common import DomainError, ERR_VALIDATION

    job_id, experiment_id = seed_experiment(dispatcher, COMPOSITE_CANDIDATE)
    job = _process_job(dispatcher, job_id)
    run_id = _rows(
        dispatcher, "SELECT id FROM backtest_runs WHERE experiment_id = %s", (experiment_id,)
    )[0][0]
    # stale-token fail (e.g. consumer crash long after complete): lease guard rejects
    updated = dispatcher.fail(job.id, DomainError(ERR_VALIDATION, "late crash"), False, job.lease_token)
    assert updated is False
    assert _rows(dispatcher, "SELECT status FROM backtest_runs WHERE id = %s", (run_id,))[0][0] == "completed"
    assert _rows(dispatcher, "SELECT status FROM backtest_jobs WHERE id = %s", (job_id,))[0][0] == "completed"


def test_fail_marks_run_failed_with_outbox_event(dispatcher) -> None:
    from app.domain.common import DomainError, ERR_VALIDATION

    job_id, experiment_id = seed_experiment(dispatcher, COMPOSITE_CANDIDATE)
    job = dispatcher.claim("itest-worker", timedelta(seconds=120))
    assert job.id == job_id
    assert dispatcher.fail(job.id, DomainError(ERR_VALIDATION, "bad snapshot"), False, job.lease_token)
    assert _rows(dispatcher, "SELECT status FROM backtest_jobs WHERE id = %s", (job_id,))[0][0] == "failed"
    run = _rows(
        dispatcher,
        "SELECT status, error_code FROM backtest_runs WHERE experiment_id = %s",
        (experiment_id,),
    )
    assert run[0][0] == "failed"
    assert run[0][1] == ERR_VALIDATION
    failed_events = _rows(
        dispatcher,
        "SELECT count(*) FROM domain_events WHERE event_type = 'BacktestFailed'"
        " AND aggregate_id = (SELECT id FROM backtest_runs WHERE experiment_id = %s)",
        (experiment_id,),
    )
    assert failed_events[0][0] == 1


def test_reclaim_after_completion_short_circuits_engine(dispatcher) -> None:
    job_id, experiment_id = seed_experiment(dispatcher, COMPOSITE_CANDIDATE)
    _process_job(dispatcher, job_id)
    run = _rows(
        dispatcher,
        "SELECT id, signals_count, candles_read FROM backtest_runs WHERE experiment_id = %s",
        (experiment_id,),
    )[0]
    # simulate an expired-lease requeue of the same job (attempt a takeover)
    with dispatcher._conn.cursor() as cur:
        cur.execute(
            "UPDATE backtest_jobs SET status = 'queued', lease_token = NULL,"
            " lease_expires_at = NULL, leased_by = NULL WHERE id = %s",
            (job_id,),
        )
    dispatcher._conn.commit()
    job = dispatcher.claim("itest-worker-2", timedelta(seconds=120))
    assert job.id == job_id
    assert job.run_already_completed is True  # AC-05d
    from app.worker import BacktestWorker, WorkerConfig

    worker = BacktestWorker(dispatcher, config=WorkerConfig(worker_id="itest-worker-2"))
    worker._process(job)
    # job completed again without re-running the engine: facts untouched
    assert _rows(dispatcher, "SELECT status FROM backtest_jobs WHERE id = %s", (job_id,))[0][0] == "completed"
    run_after = _rows(
        dispatcher,
        "SELECT id, signals_count, candles_read FROM backtest_runs WHERE experiment_id = %s",
        (experiment_id,),
    )[0]
    assert run_after == run
    # no second BacktestStarted/Completed pair for the takeover
    assert _rows(dispatcher, "SELECT count(*) FROM domain_events WHERE event_type = 'BacktestStarted'")[0][0] == 1


def test_heartbeat_extends_lease_by_configured_length(dispatcher) -> None:
    job_id, _ = seed_experiment(dispatcher, COMPOSITE_CANDIDATE)
    job = dispatcher.claim("itest-worker", timedelta(seconds=120))
    assert dispatcher.heartbeat(job.id, job.lease_token, timedelta(seconds=300))
    after = _rows(dispatcher, "SELECT lease_expires_at FROM backtest_jobs WHERE id = %s", (job_id,))[0][0]
    now = datetime.now(tz=UTC)
    remaining = (after - now).total_seconds()
    assert 290 <= remaining <= 300  # lease now expires at now+300s, never shrinks
    # stale token beat: rejected
    assert dispatcher.heartbeat(job.id, uuid4(), timedelta(seconds=300)) is False


def test_claim_enforces_per_user_concurrency_quota(dispatcher) -> None:
    first_job_id, first_experiment_id = seed_experiment(dispatcher, COMPOSITE_CANDIDATE)
    with dispatcher._conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO user_quotas(user_id,max_concurrent_runs)
            SELECT owner_id,1 FROM experiments WHERE id=%s
            """,
            (first_experiment_id,),
        )
        cur.execute(
            """
            INSERT INTO experiments(
                owner_id,strategy_version_id,candidate_definition,candidate_hash,
                market_dataset_id,bbo_dataset_hash,evaluator_version,correlation_id,
                replay_range_from,replay_range_to
            )
            SELECT owner_id,strategy_version_id,candidate_definition,%s,
                   market_dataset_id,bbo_dataset_hash,evaluator_version,%s,
                   replay_range_from,replay_range_to
            FROM experiments WHERE id=%s RETURNING id
            """,
            ("d" * 64, "quota-correlation", first_experiment_id),
        )
        second_experiment_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO backtest_jobs(experiment_id) VALUES (%s) RETURNING id",
            (second_experiment_id,),
        )
        second_job_id = cur.fetchone()[0]
    dispatcher._conn.commit()

    first = dispatcher.claim("quota-worker-1", timedelta(seconds=120))
    assert first is not None and first.id in {first_job_id, second_job_id}
    assert dispatcher.claim("quota-worker-2", timedelta(seconds=120)) is None


def test_database_rejects_invalid_search_stop_contract(dispatcher) -> None:
    _, experiment_id = seed_experiment(dispatcher, COMPOSITE_CANDIDATE)
    owner_id, dataset_id = _rows(
        dispatcher,
        "SELECT owner_id,market_dataset_id FROM experiments WHERE id=%s",
        (experiment_id,),
    )[0]
    with dispatcher._conn.cursor() as cur:
        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute(
                """
                INSERT INTO search_runs(
                    owner_id,generator_id,search_space,stop_conditions,
                    market_dataset_id,seed
                ) VALUES (%s,'grid','{}','{"max_candidates":1.5}',%s,0)
                """,
                (owner_id, dataset_id),
            )
    dispatcher._conn.rollback()


def test_search_run_uses_its_immutable_dataset_range(dispatcher) -> None:
    from app.infrastructure.postgres.store import Store
    from app.schemas import SearchRunCreateIn

    _, experiment_id = seed_experiment(dispatcher, COMPOSITE_CANDIDATE)
    owner_id, dataset_version = _rows(
        dispatcher,
        "SELECT owner_id,dataset_version FROM experiments e JOIN market_datasets d ON d.id=e.market_dataset_id WHERE e.id=%s",
        (experiment_id,),
    )[0]
    request = SearchRunCreateIn.model_validate({
        "owner_id": owner_id,
        "generator_id": "random_search",
        "search_space": {
            "strategy_ids": ["ma_cross"],
            "cardinality": [1],
            "policies": ["weighted_vote"],
            "parameter_grid": {},
        },
        "stop_conditions": {"max_candidates": 1},
        "dataset_version": dataset_version,
        "seed": 7,
    })

    created = Store(DATABASE_URL).create_search_run(request)

    assert created["generated"] == 1
    assert _rows(
        dispatcher,
        """
        SELECT e.replay_range_from,e.replay_range_to,d.range_from,d.range_to
        FROM experiments e
        JOIN search_candidates c ON c.experiment_id=e.id
        JOIN market_datasets d ON d.id=e.market_dataset_id
        WHERE c.search_run_id=%s
        """,
        (created["search_run_id"],),
    ) == [(T0, T0 + timedelta(minutes=59, seconds=59, milliseconds=999), T0, T0 + timedelta(minutes=59, seconds=59, milliseconds=999))]


def test_lost_lease_mid_persist_rolls_back_completely(dispatcher) -> None:
    job_id, _ = seed_experiment(dispatcher, COMPOSITE_CANDIDATE)
    job = dispatcher.claim("itest-worker", timedelta(seconds=120))
    candles, quotes = dispatcher.load_dataset(job.snapshot)
    from app.services.backtest_engine import DeterministicEngine

    result = DeterministicEngine().run(job.snapshot, candles, quotes)
    # a takeover worker stole the run between claim and complete: the run-row
    # lease guard must abort the whole completion transaction
    with dispatcher._conn.cursor() as cur:
        cur.execute(
            "UPDATE backtest_runs SET lease_token = gen_random_uuid()"
            " WHERE experiment_id = (SELECT experiment_id FROM backtest_jobs WHERE id = %s)",
            (job_id,),
        )
    dispatcher._conn.commit()
    with pytest.raises(Exception):
        dispatcher.complete(job.id, job.lease_token, result)
    # nothing landed: job still leased, no facts, no outbox — all or nothing
    assert _rows(dispatcher, "SELECT status FROM backtest_jobs WHERE id = %s", (job_id,))[0][0] == "leased"
    assert _rows(dispatcher, "SELECT count(*) FROM run_signals") == [(0,)]
    # BacktestStarted from claim is legitimately committed; completion's
    # BacktestCompleted must NOT be
    assert _rows(
        dispatcher, "SELECT count(*) FROM domain_events WHERE event_type = 'BacktestCompleted'"
    ) == [(0,)]
    # the connection is usable again (no aborted-transaction poisoning)
    assert dispatcher.complete(job.id, job.lease_token) == (True, None)


def test_outbox_consumer_evaluates_once_and_delivers_idempotently(dispatcher) -> None:
    from app.event_worker import EventWorker
    from app.infrastructure.postgres.outbox import PostgresOutbox
    from app.worker import BacktestWorker, WorkerConfig

    job_id, experiment_id = seed_experiment(dispatcher, COMPOSITE_CANDIDATE)
    job = dispatcher.claim("itest-worker", timedelta(seconds=120))
    worker = BacktestWorker(
        dispatcher,
        config=WorkerConfig(worker_id="itest-worker", event_consumers=()),
    )
    worker._process(job)
    run_id = _rows(
        dispatcher,
        "SELECT id FROM backtest_runs WHERE experiment_id=%s",
        (experiment_id,),
    )[0][0]
    assert _rows(
        dispatcher, "SELECT count(*) FROM evaluations WHERE backtest_run_id=%s", (run_id,)
    ) == [(0,)]

    event_worker = EventWorker(DATABASE_URL, "itest-events")
    try:
        completed_event = None
        while event := event_worker._outbox.claim():
            event_worker._handle(event)
            event_worker._outbox.complete(event.event_id)
            if event.event_type == "BacktestCompleted":
                completed_event = event
        assert completed_event is not None
        assert _rows(
            dispatcher, "SELECT count(*) FROM evaluations WHERE backtest_run_id=%s", (run_id,)
        ) == [(1,)]

        # Re-delivery is safe at both layers: evaluation has a unique immutable
        # identity and outbox completion recognizes the prior consumption.
        event_worker._handle(completed_event)
        event_worker._outbox.complete(completed_event.event_id)
        assert _rows(
            dispatcher, "SELECT count(*) FROM evaluations WHERE backtest_run_id=%s", (run_id,)
        ) == [(1,)]
        assert _rows(
            dispatcher,
            "SELECT count(*) FROM event_consumptions WHERE event_id=%s AND consumer_id=%s",
            (completed_event.event_id, "itest-events"),
        ) == [(1,)]
        assert _rows(
            dispatcher, "SELECT dispatch_status FROM domain_events WHERE event_id=%s",
            (completed_event.event_id,),
        ) == [("delivered",)]
    finally:
        event_worker.close()

    # A different consumer cannot falsely record delivery without owning a claim.
    stale = PostgresOutbox(DATABASE_URL, "stale-consumer")
    try:
        with pytest.raises(RuntimeError, match="lease lost"):
            stale.complete(completed_event.event_id)
    finally:
        stale.close()


def test_database_roles_enforce_service_ownership(dispatcher) -> None:
    connection = dispatcher._conn
    try:
        connection.execute("SET LOCAL ROLE api_runtime")
        connection.execute(
            """
            INSERT INTO candles(provider,symbol,timeframe,open_time,close_time,
                                open,high,low,close,volume)
            VALUES ('binance_usdm','ETHUSDT','1m',%s,%s,100,101,99,100,1)
            """,
            (T0, T0 + timedelta(minutes=1)),
        )
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute(
                "INSERT INTO strategy_definitions(strategy_id,display_name,family)"
                " VALUES ('forbidden-api-write','forbidden','trend')"
            )
    finally:
        connection.rollback()

    try:
        connection.execute("SET LOCAL ROLE research_runtime")
        connection.execute(
            "INSERT INTO strategy_definitions(strategy_id,display_name,family)"
            " VALUES ('allowed-research-write','allowed','trend')"
        )
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute(
                "UPDATE users SET display_name='forbidden' WHERE false"
            )
    finally:
        connection.rollback()


def test_immutable_dataset_rejects_update_and_delete(dispatcher) -> None:
    seed_experiment(dispatcher, COMPOSITE_CANDIDATE)
    with dispatcher._conn.cursor() as cursor:
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
            cursor.execute("UPDATE market_datasets SET content_hash=%s", ("a" * 64,))
    dispatcher._conn.rollback()
    with dispatcher._conn.cursor() as cursor:
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
            cursor.execute("DELETE FROM market_datasets")
    dispatcher._conn.rollback()


def test_research_http_create_is_async_idempotent_and_queryable(dispatcher) -> None:
    from fastapi.testclient import TestClient

    from app.infrastructure.postgres.store import Store
    from app.main import app

    seed_experiment(dispatcher, COMPOSITE_CANDIDATE)
    owner_id, dataset_version = _rows(
        dispatcher,
        """
        SELECT u.id,d.dataset_version FROM users u CROSS JOIN market_datasets d LIMIT 1
        """,
    )[0]
    store = Store(DATABASE_URL)
    previous_store = getattr(app.state, "store", None)
    app.state.store = store
    headers = {
        "Authorization": "Bearer development-internal-token",
        "X-User-ID": str(owner_id),
        "X-Request-ID": "itest-http-create",
        "Idempotency-Key": "itest-http-create",
    }
    body = {
        "owner_id": str(owner_id),
        "strategy_id": "composite",
        "strategy_version": "v1",
        "candidate_definition": COMPOSITE_CANDIDATE,
        "dataset_version": dataset_version,
        "idempotency_key": "itest-http-create",
    }
    try:
        # Avoid running the application lifespan here: this test injects an
        # isolated integration Store explicitly and startup would resolve the
        # developer/default DATABASE_URL instead.
        client = TestClient(app)
        created = client.post("/api/v1/experiments", headers=headers, json=body)
        assert created.status_code == 202
        accepted = created.json()
        assert accepted["status"] == "queued"

        repeated = client.post("/api/v1/experiments", headers=headers, json=body)
        assert repeated.status_code == 200
        assert repeated.json()["experiment_id"] == accepted["experiment_id"]
        assert repeated.json()["run_id"] == accepted["run_id"]
        assert repeated.json()["reused"] is True

        summary = client.get(
            f"/api/v1/experiments/{accepted['experiment_id']}", headers=headers
        )
        assert summary.status_code == 200
        payload = summary.json()
        assert payload["id"] == accepted["experiment_id"]
        assert payload["status"] == "queued"
        assert payload["candidate_definition"] == COMPOSITE_CANDIDATE
        assert payload["metrics"] is None
        assert payload["execution"]["fill_policy"] == "bbo_limit"
        correlation = _rows(
            dispatcher,
            """
            SELECT e.correlation_id,event.correlation_id
            FROM experiments e JOIN domain_events event
              ON event.aggregate_type='experiment' AND event.aggregate_id=e.id
            WHERE e.id=%s
            """,
            (accepted["experiment_id"],),
        )
        assert correlation == [("itest-http-create", "itest-http-create")]
    finally:
        app.state.store = previous_store


def test_identical_dsl_drafts_are_reviewable_by_different_owners() -> None:
    """Identical safe artifacts are evidence per draft, not a global singleton."""
    from app.infrastructure.postgres.store import Store
    from app.schemas import StrategyDraftCreateIn, StrategySourceIn, StrategySpecResponse
    from app.services.authoring import StrategyAuthoringService

    owner_ids = []
    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cur:
            for index in range(2):
                cur.execute(
                    "INSERT INTO users (email, password_hash, display_name, role) "
                    "VALUES (%s, %s, %s, 'RESEARCHER') RETURNING id",
                    (f"same-dsl-{uuid4().hex[:12]}-{index}@test.local", "x", "Same DSL Tester"),
                )
                owner_ids.append(cur.fetchone()[0])

    strategy_suffix = uuid4().hex[:8]

    class Designer:
        def design(self, _text, _request_id):
            return StrategySpecResponse.model_validate(
                {
                    "strategy_id": f"generated.same-dsl-{strategy_suffix}",
                    "display_name": "Same DSL",
                    "family": "momentum",
                    "description": "Long below 30, short above 70.",
                    "parameters": {},
                    "indicators": [{"id": "rsi14", "kind": "rsi", "period": 14}],
                    "rules": {
                        "long_entry": {"op": "below", "left": "rsi14", "right": 30},
                        "short_entry": {"op": "above", "left": "rsi14", "right": 70},
                        "exit": {"op": "opposite_signal"},
                    },
                    "warmup_bars": 14,
                }
            )

    try:
        service = StrategyAuthoringService(Store(DATABASE_URL), Designer())
        drafts = [
            service.create(
                StrategyDraftCreateIn(
                    owner_id=owner_id,
                    source=StrategySourceIn(type="text", text="Use RSI 14 for reversal entries."),
                    idempotency_key=f"same-dsl-{index}",
                )
            )
            for index, owner_id in enumerate(owner_ids)
        ]

        assert [draft["status"] for draft in drafts] == ["REVIEW_REQUIRED", "REVIEW_REQUIRED"]
        assert drafts[0]["draft_id"] != drafts[1]["draft_id"]
        assert drafts[0]["artifact_hash"] == drafts[1]["artifact_hash"]
    finally:
        with psycopg.connect(DATABASE_URL) as connection:
            connection.execute("DELETE FROM users WHERE id IN (%s, %s)", owner_ids)


def test_authoring_submission_persists_one_durable_job_without_calling_the_model() -> None:
    from app.infrastructure.postgres.store import Store
    from app.schemas import StrategyDraftCreateIn, StrategySourceIn
    from app.services.authoring import StrategyAuthoringService

    with psycopg.connect(DATABASE_URL) as connection:
        owner_id = connection.execute(
            "INSERT INTO users (email, password_hash, display_name, role) "
            "VALUES (%s, %s, %s, 'RESEARCHER') RETURNING id",
            (f"agent-submit-{uuid4().hex[:12]}@test.local", "x", "Agent Submit Tester"),
        ).fetchone()[0]

    class DesignerThatMustNotRun:
        def design(self, _text, _request_id):
            raise AssertionError("the durable agent worker, not submission, may call the model")

    request = StrategyDraftCreateIn(
        owner_id=owner_id,
        source=StrategySourceIn(type="text", text="Use RSI below 30 for long."),
        idempotency_key=f"agent-submit-{uuid4().hex}",
    )
    store = Store(DATABASE_URL)
    service = StrategyAuthoringService(store, DesignerThatMustNotRun())
    try:
        first = service.submit(request, "integration-agent-submit")
        second = service.submit(request, "integration-agent-submit-retry")

        assert first["draft_id"] == second["draft_id"]
        assert first["status"] == "DRAFT_CREATED"
        with psycopg.connect(DATABASE_URL) as connection:
            rows = connection.execute(
                """
                SELECT run.state,run.attempts_used,job.status
                FROM agent_runs run
                JOIN agent_jobs job ON job.agent_run_id=run.id
                WHERE run.draft_id=%s
                """,
                (first["draft_id"],),
            ).fetchall()
        assert rows == [("DRAFT_CREATED", 0, "queued")]
    finally:
        with psycopg.connect(DATABASE_URL) as connection:
            connection.execute("DELETE FROM users WHERE id=%s", (owner_id,))


def test_agent_orchestrator_completes_a_claimed_dsl_submission() -> None:
    from app.infrastructure.postgres.store import Store
    from app.schemas import StrategyDraftCreateIn, StrategySourceIn
    from app.services.agent_orchestrator import AgentOrchestrator
    from app.services.authoring import StrategyAuthoringService

    with psycopg.connect(DATABASE_URL) as connection:
        owner_id = connection.execute(
            "INSERT INTO users (email, password_hash, display_name, role) "
            "VALUES (%s, %s, %s, 'RESEARCHER') RETURNING id",
            (f"agent-worker-{uuid4().hex[:12]}@test.local", "x", "Agent Worker Tester"),
        ).fetchone()[0]

    dsl = {
        "strategy_id": "generated.agent-worker-rsi",
        "display_name": "Agent Worker RSI",
        "family": "momentum",
        "description": "Long below 30, short above 70.",
        "parameters": {},
        "indicators": [{"id": "rsi14", "kind": "rsi", "period": 14}],
        "rules": {
            "long_entry": {"op": "below", "left": "rsi14", "right": 30},
            "short_entry": {"op": "above", "left": "rsi14", "right": 70},
            "exit": {"op": "opposite_signal"},
        },
        "warmup_bars": 14,
    }
    store = Store(DATABASE_URL)
    service = StrategyAuthoringService(store, object())
    request = StrategyDraftCreateIn(
        owner_id=owner_id,
        source=StrategySourceIn(type="dsl", spec=dsl),
        idempotency_key=f"agent-worker-{uuid4().hex}",
    )
    try:
        pending = service.submit(request, "integration-agent-worker")

        assert AgentOrchestrator(store, service).process_once("agent-worker-test") is True

        completed = store.get_strategy_draft(pending["draft_id"], owner_id)
        assert completed["status"] == "REVIEW_REQUIRED"
        assert completed["artifact_hash"]
        with psycopg.connect(DATABASE_URL) as connection:
            rows = connection.execute(
                """
                SELECT run.state,job.status
                FROM agent_runs run
                JOIN agent_jobs job ON job.agent_run_id=run.id
                WHERE run.draft_id=%s
                """,
                (pending["draft_id"],),
            ).fetchall()
        assert rows == [("REVIEW_REQUIRED", "completed")]
        with psycopg.connect(DATABASE_URL) as connection:
            tools = connection.execute(
                """
                SELECT invocation.tool_name,invocation.state
                FROM tool_invocations invocation
                JOIN agent_runs run ON run.id=invocation.agent_run_id
                WHERE run.draft_id=%s
                ORDER BY invocation.sequence_no
                """,
                (pending["draft_id"],),
            ).fetchall()
        assert tools == [
            ("source.get_document", "SPEC_GENERATING"),
            ("strategy.validate_spec", "SPEC_VALIDATING"),
            ("strategy.save_draft_spec", "SPEC_VALIDATING"),
            ("artifact.compile_from_spec", "CODE_GENERATING"),
            ("artifact.save_version", "CODE_GENERATING"),
            ("artifact.run_policy_check", "POLICY_CHECKING"),
            ("sandbox.run_contract_tests", "SANDBOX_TESTING"),
            ("draft.mark_review_required", "SANDBOX_TESTING"),
        ]
    finally:
        with psycopg.connect(DATABASE_URL) as connection:
            connection.execute("DELETE FROM users WHERE id=%s", (owner_id,))


def test_agent_state_transition_is_fenced_by_lease_state_and_aggregate_version() -> None:
    from datetime import timedelta

    from app.errors import ApplicationError
    from app.infrastructure.postgres.store import Store
    from app.schemas import StrategyDraftCreateIn, StrategySourceIn
    from app.services.authoring import StrategyAuthoringService

    with psycopg.connect(DATABASE_URL) as connection:
        owner_id = connection.execute(
            "INSERT INTO users (email, password_hash, display_name, role) "
            "VALUES (%s, %s, %s, 'RESEARCHER') RETURNING id",
            (f"agent-cas-{uuid4().hex[:12]}@test.local", "x", "Agent CAS Tester"),
        ).fetchone()[0]

    store = Store(DATABASE_URL)
    request = StrategyDraftCreateIn(
        owner_id=owner_id,
        source=StrategySourceIn(type="dsl", spec={
            "strategy_id": "generated.agent-cas-rsi", "display_name": "Agent CAS RSI",
            "family": "momentum", "description": "Long below 30, short above 70.",
            "parameters": {}, "indicators": [{"id": "rsi14", "kind": "rsi", "period": 14}],
            "rules": {
                "long_entry": {"op": "below", "left": "rsi14", "right": 30},
                "short_entry": {"op": "above", "left": "rsi14", "right": 70},
                "exit": {"op": "opposite_signal"},
            }, "warmup_bars": 14,
        }),
        idempotency_key=f"agent-cas-{uuid4().hex}",
    )
    try:
        pending = StrategyAuthoringService(store, object()).submit(request)
        job = store.claim_agent_job("agent-cas-test", timedelta(seconds=30))
        assert job is not None

        assert store.advance_agent_run_state(
            job["id"], job["lease_token"], "DRAFT_CREATED", 0, "SOURCE_READY"
        ) == 1
        with pytest.raises(ApplicationError) as error:
            store.advance_agent_run_state(
                job["id"], job["lease_token"], "DRAFT_CREATED", 0, "SPEC_GENERATING"
            )
        assert error.value.code == "agent_state_conflict"
        assert store.get_strategy_draft(pending["draft_id"], owner_id)["status"] == "SOURCE_READY"
    finally:
        with psycopg.connect(DATABASE_URL) as connection:
            connection.execute("DELETE FROM users WHERE id=%s", (owner_id,))


def test_reclaimed_agent_job_continues_from_its_persisted_state_checkpoint() -> None:
    from datetime import timedelta

    from app.infrastructure.postgres.store import Store
    from app.schemas import StrategyDraftCreateIn, StrategySourceIn
    from app.services.agent_orchestrator import AgentOrchestrator
    from app.services.authoring import StrategyAuthoringService

    with psycopg.connect(DATABASE_URL) as connection:
        owner_id = connection.execute(
            "INSERT INTO users (email, password_hash, display_name, role) "
            "VALUES (%s, %s, %s, 'RESEARCHER') RETURNING id",
            (f"agent-resume-{uuid4().hex[:12]}@test.local", "x", "Agent Resume Tester"),
        ).fetchone()[0]

    dsl = {
        "strategy_id": "generated.agent-resume-rsi", "display_name": "Agent Resume RSI",
        "family": "momentum", "description": "Long below 30, short above 70.",
        "parameters": {}, "indicators": [{"id": "rsi14", "kind": "rsi", "period": 14}],
        "rules": {
            "long_entry": {"op": "below", "left": "rsi14", "right": 30},
            "short_entry": {"op": "above", "left": "rsi14", "right": 70},
            "exit": {"op": "opposite_signal"},
        }, "warmup_bars": 14,
    }
    store = Store(DATABASE_URL)
    try:
        pending = StrategyAuthoringService(store, object()).submit(
            StrategyDraftCreateIn(
                owner_id=owner_id, source=StrategySourceIn(type="dsl", spec=dsl),
                idempotency_key=f"agent-resume-{uuid4().hex}",
            )
        )
        first_lease = store.claim_agent_job("agent-resume-first", timedelta(seconds=30))
        assert first_lease is not None
        store.advance_agent_run_state(
            first_lease["id"], first_lease["lease_token"], "DRAFT_CREATED", 0, "SOURCE_READY"
        )
        with psycopg.connect(DATABASE_URL) as connection:
            connection.execute(
                "UPDATE agent_jobs SET lease_expires_at=now()-interval '1 second' WHERE id=%s",
                (first_lease["id"],),
            )

        assert AgentOrchestrator(store, StrategyAuthoringService(store, object())).process_once("agent-resume-second")
        assert store.get_strategy_draft(pending["draft_id"], owner_id)["status"] == "REVIEW_REQUIRED"
        with psycopg.connect(DATABASE_URL) as connection:
            transitions = connection.execute(
                """
                SELECT transition.state FROM agent_run_transitions transition
                JOIN agent_runs run ON run.id=transition.agent_run_id
                WHERE run.draft_id=%s ORDER BY transition.sequence_no
                """,
                (pending["draft_id"],),
            ).fetchall()
        assert [row[0] for row in transitions] == [
            "DRAFT_CREATED", "SOURCE_READY", "SPEC_GENERATING", "SPEC_VALIDATING",
            "CODE_GENERATING", "POLICY_CHECKING", "SANDBOX_TESTING", "REVIEW_REQUIRED",
        ]
    finally:
        with psycopg.connect(DATABASE_URL) as connection:
            connection.execute("DELETE FROM users WHERE id=%s", (owner_id,))


def test_cancelled_authoring_draft_is_not_claimed_by_the_agent_worker() -> None:
    from app.infrastructure.postgres.store import Store
    from app.schemas import StrategyDraftCreateIn, StrategySourceIn
    from app.services.agent_orchestrator import AgentOrchestrator
    from app.services.authoring import StrategyAuthoringService

    with psycopg.connect(DATABASE_URL) as connection:
        owner_id = connection.execute(
            "INSERT INTO users (email, password_hash, display_name, role) "
            "VALUES (%s, %s, %s, 'RESEARCHER') RETURNING id",
            (f"agent-cancel-{uuid4().hex[:12]}@test.local", "x", "Agent Cancel Tester"),
        ).fetchone()[0]

    class DesignerThatMustNotRun:
        def design(self, _text, _request_id):
            raise AssertionError("cancelled drafts must not reach the model")

    store = Store(DATABASE_URL)
    service = StrategyAuthoringService(store, DesignerThatMustNotRun())
    request = StrategyDraftCreateIn(
        owner_id=owner_id,
        source=StrategySourceIn(type="text", text="Use RSI below 30 for long."),
        idempotency_key=f"agent-cancel-{uuid4().hex}",
    )
    try:
        pending = service.submit(request)

        cancelled = store.cancel_strategy_draft(pending["draft_id"], owner_id)

        assert cancelled["status"] == "CANCELLED"
        assert AgentOrchestrator(store, service).process_once("cancelled-agent-worker") is False
        with psycopg.connect(DATABASE_URL) as connection:
            rows = connection.execute(
                """
                SELECT run.state,job.status
                FROM agent_runs run JOIN agent_jobs job ON job.agent_run_id=run.id
                WHERE run.draft_id=%s
                """,
                (pending["draft_id"],),
            ).fetchall()
        assert rows == [("CANCELLED", "cancelled")]
    finally:
        with psycopg.connect(DATABASE_URL) as connection:
            connection.execute("DELETE FROM users WHERE id=%s", (owner_id,))


def test_approved_dsl_strategy_is_resolved_by_the_backtest_worker(dispatcher) -> None:
    """An approved strategy must run from its persisted immutable runtime spec."""
    from app.infrastructure.postgres.store import Store
    from app.schemas import (
        ExperimentCreateIn,
        StrategyApprovalIn,
        StrategyDraftCreateIn,
        StrategySourceIn,
        StrategySpecResponse,
    )
    from app.services.authoring import StrategyAuthoringService

    seed_job_id, seed_experiment_id = seed_experiment(dispatcher, COMPOSITE_CANDIDATE)
    owner_id, dataset_version = _rows(
        dispatcher,
        "SELECT owner_id, d.dataset_version FROM experiments e JOIN market_datasets d ON d.id=e.market_dataset_id WHERE e.id=%s",
        (seed_experiment_id,),
    )[0]
    with dispatcher._conn.cursor() as cur:
        cur.execute("UPDATE backtest_jobs SET status='cancelled' WHERE id=%s", (seed_job_id,))
    dispatcher._conn.commit()

    class Designer:
        def design(self, _text, _request_id):
            return StrategySpecResponse.model_validate(
                {
                    "strategy_id": "generated.integration-rsi",
                    "display_name": "Integration RSI",
                    "family": "momentum",
                    "description": "Long below 30, short above 70.",
                    "parameters": {},
                    "indicators": [{"id": "rsi14", "kind": "rsi", "period": 14}],
                    "rules": {
                        "long_entry": {"op": "below", "left": "rsi14", "right": 30},
                        "short_entry": {"op": "above", "left": "rsi14", "right": 70},
                        "exit": {"op": "opposite_signal"},
                    },
                    "warmup_bars": 14,
                }
            )

    store = Store(DATABASE_URL)
    draft = StrategyAuthoringService(store, Designer()).create(
        StrategyDraftCreateIn(
            owner_id=owner_id,
            source=StrategySourceIn(type="text", text="Use RSI 14 for reversal entries."),
            idempotency_key="integration-generated-rsi",
        ),
        "integration-authoring",
    )
    assert draft["status"] == "REVIEW_REQUIRED"
    assert _rows(
        dispatcher,
        """
        SELECT attempt.attempt_no,attempt.status,attempt.error_code
        FROM agent_attempts attempt
        JOIN agent_runs run ON run.id=attempt.agent_run_id
        WHERE run.draft_id=%s
        ORDER BY attempt.attempt_no
        """,
        (draft["draft_id"],),
    ) == [(1, "passed", None)]
    assert _rows(
        dispatcher,
        """
        SELECT transition.sequence_no,transition.state
        FROM agent_run_transitions transition
        JOIN agent_runs run ON run.id=transition.agent_run_id
        WHERE run.draft_id=%s
        ORDER BY transition.sequence_no
        """,
        (draft["draft_id"],),
    ) == list(enumerate([
        "DRAFT_CREATED", "SOURCE_READY", "SPEC_GENERATING", "SPEC_VALIDATING",
        "CODE_GENERATING", "POLICY_CHECKING", "SANDBOX_TESTING", "REVIEW_REQUIRED",
    ]))

    approved = store.approve_strategy_draft(
        draft["draft_id"],
        StrategyApprovalIn(
            reviewer_id=owner_id,
            revision=draft["current_revision"],
            spec_hash=draft["spec_hash"],
            artifact_hash=draft["artifact_hash"],
            sandbox_report_hash=draft["sandbox_report_hash"],
            decision="approve",
            reason="Reviewed immutable DSL artifact.",
            idempotency_key="integration-generated-rsi-approval",
        ),
    )
    assert approved["status"] == "APPROVED"
    assert [item["draft_id"] for item in store.list_strategy_drafts(owner_id, 3)] == [draft["draft_id"]]

    accepted = store.create_experiment(
        ExperimentCreateIn(
            owner_id=owner_id,
            strategy_id=approved["strategy_spec"]["strategy_id"],
            strategy_version="v1",
            dataset_version=dataset_version,
            range_from=T0,
            range_to=T0 + timedelta(minutes=59, seconds=59, milliseconds=999),
            idempotency_key="integration-generated-rsi-experiment",
        ),
        "integration-authoring-backtest",
    )
    job = dispatcher.claim("generated-rsi-worker", timedelta(seconds=120))
    assert job is not None and job.id == accepted["run_id"]
    from app.worker import BacktestWorker, WorkerConfig

    BacktestWorker(dispatcher, config=WorkerConfig(worker_id="generated-rsi-worker"))._process(job)
    assert _rows(dispatcher, "SELECT status FROM backtest_jobs WHERE id=%s", (job.id,)) == [("completed",)]


def test_approved_custom_python_artifact_requires_deployment_and_never_enters_the_registry(dispatcher) -> None:
    from app.infrastructure.postgres.store import Store
    from app.schemas import StrategyApprovalIn, StrategyDraftCreateIn, StrategySourceIn
    from app.services.authoring import StrategyAuthoringService

    with dispatcher._conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (email,password_hash,display_name,role) VALUES (%s,%s,%s,'RESEARCHER') RETURNING id",
            (f"custom-review-{uuid4().hex[:12]}@test.local", "x", "Custom Review Tester"),
        )
        owner_id = cur.fetchone()[0]
    dispatcher._conn.commit()

    class DesignerThatMustNotRun:
        def design(self, _text, _request_id):
            raise AssertionError("custom Python must not call the DSL designer")

    store = Store(DATABASE_URL)
    try:
        draft = StrategyAuthoringService(store, DesignerThatMustNotRun()).create(
            StrategyDraftCreateIn(
                owner_id=owner_id,
                mode="custom_python",
                name_hint="Review-only custom strategy",
                source=StrategySourceIn(type="text", text="class Strategy:\n    def analyze(self, candles): return []\n"),
            )
        )
        approved = store.approve_strategy_draft(
            draft["draft_id"],
            StrategyApprovalIn(
                reviewer_id=owner_id,
                revision=draft["current_revision"],
                spec_hash=draft["spec_hash"],
                artifact_hash=draft["artifact_hash"],
                sandbox_report_hash=draft["sandbox_report_hash"],
                decision="approve",
                reason="Approved for the external build and deployment pipeline.",
            ),
        )

        assert approved["status"] == "APPROVED"
        assert _rows(dispatcher, "SELECT count(*) FROM strategy_versions WHERE code_fingerprint=%s", (draft["artifact_hash"],)) == [(0,)]
        assert _rows(
            dispatcher,
            "SELECT event_type FROM domain_events WHERE aggregate_id=%s ORDER BY occurred_at DESC LIMIT 1",
            (draft["draft_id"],),
        ) == [("StrategyCustomArtifactApprovedForDeployment",)]
        metrics = store.operational_metrics()
        assert metrics["research_agent_runs_review_required"] == 1
        assert metrics["research_sandbox_runs_passed"] == 1
    finally:
        with dispatcher._conn.cursor() as cur:
            cur.execute("DELETE FROM strategy_drafts WHERE owner_id=%s", (owner_id,))
            cur.execute("DELETE FROM users WHERE id=%s", (owner_id,))
        dispatcher._conn.commit()
