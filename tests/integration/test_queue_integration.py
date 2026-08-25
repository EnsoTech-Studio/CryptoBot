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
                                     evaluator_version)
            VALUES (%s, %s, %s, %s, %s, %s, 'v1') RETURNING id
            """,
            (user_id, versions[strategy_id], psycopg.types.json.Jsonb(candidate),
             "c" * 64, dataset_id, "b" * 64),
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
                market_dataset_id,bbo_dataset_hash,evaluator_version,correlation_id
            )
            SELECT owner_id,strategy_version_id,candidate_definition,%s,
                   market_dataset_id,bbo_dataset_hash,evaluator_version,%s
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
