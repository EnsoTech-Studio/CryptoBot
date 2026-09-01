"""PostgreSQL job queue adapter — claim/heartbeat/complete/fail + persistence.

Implements `ports/job.JobDispatcher` on the `backtest_jobs` table exactly as
`design.md` §8.3 specifies:

- claim: `FOR UPDATE SKIP LOCKED` over `status='queued' OR expired lease`, then
  `UPDATE ... SET lease_token = gen_random_uuid()` — a **new token per claim**;
- every later UPDATE (heartbeat, run bookkeeping, complete, fail) is guarded by
  the lease token; a worker that lost its lease matches 0 rows, learns it via
  the rowcount and must not commit results over the takeover worker;
- claim also performs the conditional `backtest_runs` UPSERT of design.md §8.3.2
  (status=running only when the run is not yet completed) and writes the
  `BacktestStarted` outbox row; a claim that finds the run already completed
  marks the job completed **without** re-running the engine (AC-05c/AC-05d);
- result facts (`trades`, `run_signals`, `equity_points`) and the
  `BacktestCompleted` outbox row are written in the **same transaction** as the
  job completion (transactional outbox, design.md §5.7); `fail` writes the
  `BacktestFailed` outbox row;
- expired leases are reclaimed by the claim query itself (attempt += 1 each
  claim, `failed` after `max_attempts`);
- every method commits on success and **rolls back on any error** so one failed
  statement can never poison the shared connection with an aborted transaction;
  read-only loads commit immediately so the connection never sits
  `idle in transaction` during an engine run.

The SQL targets the same checksum-verified migrations used by Compose and the
PostgreSQL integration suite. Requires `psycopg` in queue mode.

Threading contract: the main connection is owned by the worker loop thread and
every main-connection method serializes on an RLock. `heartbeat` runs on a
separate thread and therefore opens its own short-lived connection per beat —
never the shared one, so transactions can never interleave across threads.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from ...domain.backtest import (
    EquityPoint,
    ExperimentSnapshot,
    MarketSnapshot,
    Result,
    RiskPolicy,
    TradeFact,
)
from ...domain.evaluation import EvaluationInput
from ...domain.common import ERR_LEASE_LOST, ERR_PROVIDER_UNAVAILABLE, ERR_VALIDATION, DomainError
from ...domain.job import BacktestJob
from ...domain.market import BBO, Candle
from ...domain.sentiment import NewsSentimentWindow
from ...domain.strategy import (
    ChildDefinition,
    CombinationPolicy,
    CompositeDefinition,
    Reference,
)
from ...services.backtest_engine import canonical_result_hash
from ...services.ranking import ScoreRanker

try:  # optional dependency — queue mode only
    import psycopg
except ImportError:  # pragma: no cover - fixture mode works without psycopg
    psycopg = None  # type: ignore[assignment]

_EQUITY_BATCH = 5_000  # bulk insert batch (specs/backtest.md: "Bulk insert theo batch")


def _hydrate_candidate(raw: Any) -> Any:
    """Hydrate a composite `candidate_definition` JSONB dict into its contract.

    Plain parameter dicts stay dicts; composite snapshots follow the schema of
    `specs/composite-strategy.md` §Snapshot schema.
    """
    if not isinstance(raw, dict) or "children" not in raw or "policy" not in raw:
        return raw
    policy = raw["policy"]
    children = [
        ChildDefinition(
            strategy_id=c["strategy_id"],
            version=c.get("version", "v1"),
            parameters=dict(c.get("parameters") or {}),
            weight=float(c.get("weight", 1.0)),
        )
        for c in raw["children"]
    ]
    return CompositeDefinition(
        strategy_id=raw.get("strategy_id", "composite"),
        version=raw.get("version", "v1"),
        children=children,
        combination=CombinationPolicy(
            policy=policy.get("name", "weighted_vote"),
            threshold=float(policy.get("threshold", 0.5)),
            encoding=policy.get("encoding", {"BUY": 1, "HOLD": 0, "SELL": -1}),
        ),
    )


class PostgresJobDispatcher:
    """One dispatcher per worker process; one main connection, autocommit off."""

    def __init__(self, conninfo: str, heartbeat: timedelta = timedelta(seconds=30)) -> None:
        if psycopg is None:
            raise DomainError(
                ERR_PROVIDER_UNAVAILABLE, "psycopg is required for queue mode (pip install psycopg)"
            )
        self._conninfo = conninfo
        self._heartbeat = heartbeat
        self._lock = threading.RLock()  # reentrant: claim() loads the snapshot
        self._conn = psycopg.connect(conninfo, autocommit=False, connect_timeout=5)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _run(self, work: Callable[[], Any]) -> Any:
        """Commit `work`'s transaction; roll back on any error and re-raise."""
        with self._lock:
            try:
                result = work()
                self._conn.commit()
                return result
            except Exception:
                self._conn.rollback()
                raise

    @staticmethod
    def _cancel_terminal_search_queue(cur: Any, experiment_id: UUID) -> None:
        """Remove unstarted work after a durable search stop condition fires."""
        cur.execute(
            """
            UPDATE backtest_jobs pending
            SET status='cancelled',completed_at=now(),last_error='search_stop_condition'
            FROM experiments pending_experiment
            JOIN search_candidates pending_candidate
              ON pending_candidate.id=pending_experiment.search_candidate_id
            JOIN search_runs search
              ON search.id=pending_candidate.search_run_id
            WHERE pending.experiment_id=pending_experiment.id
              AND search.id=(
                  SELECT source_candidate.search_run_id
                  FROM experiments source_experiment
                  JOIN search_candidates source_candidate
                    ON source_candidate.id=source_experiment.search_candidate_id
                  WHERE source_experiment.id=%s
              )
              AND search.status IN ('completed','failed','cancelled')
              AND pending.status='queued'
            """,
            (experiment_id,),
        )

    # -- JobDispatcher protocol ------------------------------------------------

    def enqueue(self, job: BacktestJob) -> None:
        def work() -> None:
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO backtest_jobs (id, experiment_id, status, priority, attempt, max_attempts)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (job.id, job.experiment_id, job.status, job.priority, job.attempt, job.max_attempts),
                )

        self._run(work)

    def claim(self, worker_id: str, lease: timedelta) -> BacktestJob | None:
        def work() -> tuple[Any, Any]:
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    WITH raw_candidates AS MATERIALIZED (
                        SELECT queued.id,queued.priority,queued.enqueued_at
                        FROM (
                            (
                                SELECT j.id,j.priority,j.enqueued_at
                                FROM backtest_jobs j
                                WHERE j.status='queued'
                                ORDER BY j.priority,j.enqueued_at
                                LIMIT 256
                            )
                            UNION ALL
                            (
                                SELECT j.id,j.priority,j.enqueued_at
                                FROM backtest_jobs j
                                WHERE j.status='leased' AND j.lease_expires_at<now()
                                ORDER BY j.lease_expires_at,j.priority,j.enqueued_at
                                LIMIT 256
                            )
                        ) AS queued
                        ORDER BY queued.priority,queued.enqueued_at
                        LIMIT 256
                    ),
                    candidate AS (
                        SELECT j.id,e.correlation_id
                        FROM raw_candidates raw
                        JOIN backtest_jobs j ON j.id=raw.id
                        JOIN experiments e ON e.id=j.experiment_id
                        JOIN users u ON u.id=e.owner_id AND u.is_active
                        LEFT JOIN user_quotas q ON q.user_id=u.id
                        LEFT JOIN search_candidates c ON c.id=e.search_candidate_id
                        LEFT JOIN search_runs s ON s.id=c.search_run_id
                        WHERE (s.id IS NULL OR s.status='running')
                          AND (
                              SELECT count(*) FROM backtest_jobs active_job
                              JOIN experiments active_experiment
                                ON active_experiment.id=active_job.experiment_id
                              WHERE active_experiment.owner_id=e.owner_id
                                AND active_job.status='leased'
                                AND active_job.lease_expires_at >= now()
                          ) < COALESCE(q.max_concurrent_runs,2)
                          AND pg_try_advisory_xact_lock(
                              hashtextextended(e.owner_id::text,1)
                          )
                        ORDER BY j.priority ASC, j.enqueued_at ASC
                        FOR UPDATE OF j SKIP LOCKED
                        LIMIT 1
                    )
                    UPDATE backtest_jobs j
                    SET status = 'leased',
                        attempt = j.attempt + 1,
                        leased_by = %(worker_id)s,
                        lease_token = gen_random_uuid(),
                        lease_expires_at = now() + %(lease)s,
                        last_error = CASE WHEN j.status = 'leased'
                                          THEN 'lease_expired_retry' ELSE NULL END
                    FROM candidate
                    WHERE j.id = candidate.id
                    RETURNING j.id, j.experiment_id, j.status, j.priority, j.attempt,
                              j.max_attempts, j.lease_token, j.lease_expires_at,
                              candidate.correlation_id
                    """,
                    {"worker_id": worker_id, "lease": lease},
                )
                row = cur.fetchone()
                if row is None:
                    return None, None
                # run takeover (design.md §8.3.2): only a run that is not yet
                # completed may be claimed; 0 rows => AC-05d short-circuit
                cur.execute(
                    """
                    INSERT INTO backtest_runs (experiment_id, status, worker_id, lease_token,
                                               attempt, started_at)
                    SELECT j.experiment_id, 'running', j.leased_by, j.lease_token,
                           j.attempt, now()
                    FROM backtest_jobs j WHERE j.id = %(job)s
                    ON CONFLICT (experiment_id) DO UPDATE
                    SET status = 'running', worker_id = EXCLUDED.worker_id,
                        lease_token = EXCLUDED.lease_token, attempt = EXCLUDED.attempt,
                        started_at = now(), error_code = NULL, error_detail = NULL
                    WHERE backtest_runs.status IN ('queued', 'running', 'failed')
                    RETURNING id
                    """,
                    {"job": row[0]},
                )
                run = cur.fetchone()
                if run is not None:
                    cur.execute(
                        """
                        INSERT INTO domain_events (
                            event_type, aggregate_type, aggregate_id, correlation_id, payload
                        ) VALUES (
                            'BacktestStarted', 'backtest_run', %s,
                            (SELECT correlation_id FROM experiments WHERE id=%s), %s
                        )
                        """,
                        (
                            run[0],
                            row[1],
                            json.dumps(
                                {
                                    "worker_id": worker_id,
                                    "occurred_at": datetime.now(tz=UTC).isoformat(),
                                }
                            ),
                        ),
                    )
                return row, run[0] if run is not None else None

        row, run_id = self._run(work)
        if row is None:
            return None
        (
            job_id,
            experiment_id,
            status,
            priority,
            attempt,
            max_attempts,
            token,
            expires,
            correlation_id,
        ) = row
        snapshot = self.load_snapshot(experiment_id)
        return BacktestJob(
            id=job_id,
            experiment_id=experiment_id,
            snapshot=snapshot,
            status=status,
            priority=priority,
            attempt=attempt,
            max_attempts=max_attempts,
            leased_by=worker_id,
            lease_token=token,
            lease_expires_at=expires,
            correlation_id=correlation_id,
            run_id=run_id,
            run_already_completed=run_id is None,
        )

    def complete(
        self, job_id: UUID, lease_token: UUID, result: Result | None = None
    ) -> tuple[bool, UUID | None]:
        """Mark completed (+ persist facts & outbox event when a result is given).

        Returns `(False, None)` when the lease guard matched 0 rows — the caller
        lost its lease and must discard everything it computed. On success
        returns `(True, run_id)` so the evaluator consumer references the real
        `backtest_runs.id`, never a guessed one.
        """
        run_id: UUID | None = None

        def work() -> bool:
            nonlocal run_id
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT experiment_id FROM backtest_jobs
                    WHERE id=%s AND status='leased' AND lease_token=%s FOR UPDATE
                    """,
                    (job_id, lease_token),
                )
                if cur.fetchone() is None:
                    return False
                if result is not None:
                    run_id = self._persist_result(cur, job_id, lease_token, result)
                cur.execute(
                    """
                    UPDATE backtest_jobs
                    SET status = 'completed', completed_at = now(),
                        leased_by = NULL, lease_token = NULL, lease_expires_at = NULL
                    WHERE id = %s AND status = 'leased' AND lease_token = %s
                    """,
                    (job_id, lease_token),
                )
                return cur.rowcount == 1

        updated = self._run(work)
        return updated, run_id if updated else None

    def fail(self, job_id: UUID, err: Exception, retryable: bool, lease_token: UUID) -> bool:
        code = getattr(err, "code", type(err).__name__)

        def work() -> bool:
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE backtest_jobs
                    SET status = (CASE
                            WHEN NOT %(retryable)s OR attempt >= max_attempts THEN 'failed'
                            ELSE 'queued'
                        END)::job_status,
                        last_error = %(error)s,
                        lease_token = NULL, leased_by = NULL, lease_expires_at = NULL,
                        completed_at = CASE WHEN NOT %(retryable)s OR attempt >= max_attempts
                                            THEN now() END
                    WHERE id = %(job)s AND status = 'leased' AND lease_token = %(tok)s
                    RETURNING status,experiment_id
                    """,
                    {
                        "retryable": retryable,
                        "error": f"{code}: {err}",
                        "job": job_id,
                        "tok": lease_token,
                    },
                )
                job_state = cur.fetchone()
                if job_state is None:
                    # lost the lease (job completed/re-claimed): must not touch
                    # the run row owned by another worker
                    return False
                cur.execute(
                    """
                    UPDATE backtest_runs
                    SET status = 'failed', error_code = %(code)s, error_detail = %(detail)s,
                        finished_at = now()
                    WHERE experiment_id = (SELECT experiment_id FROM backtest_jobs WHERE id = %(job)s)
                      AND lease_token = %(tok)s
                    RETURNING id
                    """,
                    {"code": code, "detail": str(err), "job": job_id, "tok": lease_token},
                )
                failed_run = cur.fetchone()
                if failed_run is not None:
                    cur.execute(
                        """
                        INSERT INTO domain_events (
                            event_type, aggregate_type, aggregate_id, correlation_id, payload
                        ) VALUES (
                            'BacktestFailed', 'backtest_run', %s,
                            (SELECT correlation_id FROM experiments WHERE id=%s), %s
                        )
                        """,
                        (
                            failed_run[0],
                            job_state[1],
                            json.dumps(
                                {
                                    "job_id": str(job_id),
                                    "error_code": code,
                                    "retryable": retryable,
                                    "occurred_at": datetime.now(tz=UTC).isoformat(),
                                }
                            ),
                        ),
                    )
                if job_state[0] == "failed":
                    cur.execute(
                        """
                        UPDATE search_runs s
                        SET failed=s.failed+1,
                            status=CASE
                                WHEN extract(epoch FROM now()-s.created_at) >=
                                     COALESCE((s.stop_conditions->>'max_duration_sec')::int,2147483647)
                                    THEN 'completed'
                                WHEN s.tested+s.failed+1 >= 20
                                 AND (s.failed+1)::float8 / GREATEST(s.tested+s.failed+1,1) >=
                                     COALESCE((s.stop_conditions->>'max_failure_rate')::float8,2)
                                    THEN 'failed'
                                WHEN s.tested+s.failed+1 >= s.generated THEN 'completed'
                                ELSE s.status END,
                            stop_reason=CASE
                                WHEN extract(epoch FROM now()-s.created_at) >=
                                     COALESCE((s.stop_conditions->>'max_duration_sec')::int,2147483647)
                                    THEN 'max_duration'
                                WHEN s.tested+s.failed+1 >= 20
                                 AND (s.failed+1)::float8 / GREATEST(s.tested+s.failed+1,1) >=
                                     COALESCE((s.stop_conditions->>'max_failure_rate')::float8,2)
                                    THEN 'max_failure_rate'
                                WHEN s.tested+s.failed+1 >= s.generated THEN
                                    CASE
                                        WHEN s.generated >=
                                             COALESCE((s.stop_conditions->>'max_candidates')::int,2147483647)
                                            THEN 'max_candidates'
                                        WHEN s.generator_exhausted THEN 'space_exhausted'
                                        ELSE 'completed'
                                    END
                                ELSE s.stop_reason END,
                            updated_at=now()
                        FROM search_candidates c
                        JOIN experiments e ON e.id=c.experiment_id
                        WHERE c.search_run_id=s.id AND e.id=%s
                        """,
                        (job_state[1],),
                    )
                    self._cancel_terminal_search_queue(cur, job_state[1])
                return True

        return self._run(work)

    def heartbeat(self, job_id: UUID, lease_token: UUID, lease: timedelta) -> bool:
        """Extend the lease from the heartbeat thread.

        Opens a dedicated short-lived autocommit connection on every beat: the
        main connection belongs to the worker-loop thread and must never see
        interleaved transactions from another thread. The extension equals the
        configured lease length — a beat must never shrink the lease.
        """
        assert psycopg is not None
        try:
            connection = psycopg.connect(
                self._conninfo, autocommit=True, connect_timeout=5
            )
        except TypeError:  # compatibility with lightweight scripted test adapters
            connection = psycopg.connect(self._conninfo, autocommit=True)
        with connection as conn, conn.cursor() as cur:
            cur.execute(
                """
                    UPDATE backtest_jobs
                    SET lease_expires_at = now() + %(extend)s
                    WHERE id = %(job)s AND status = 'leased' AND lease_token = %(tok)s
                    """,
                {"extend": lease, "job": job_id, "tok": lease_token},
            )
            return cur.rowcount == 1

    # -- snapshot & dataset loading ---------------------------------------------

    def load_snapshot(self, experiment_id: UUID) -> ExperimentSnapshot:
        return self._run(lambda: self._load_snapshot_locked(experiment_id))

    def _load_snapshot_locked(self, experiment_id: UUID) -> ExperimentSnapshot:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.id, e.owner_id, e.candidate_definition, e.candidate_hash,
                       e.initial_equity, e.fixed_notional, e.leverage, e.fee_bps, e.slippage_bps,
                       e.fill_policy, e.position_policy, e.open_position_at_end,
                       e.stop_loss_pct, e.take_profit_pct, e.intrabar_priority, e.evaluator_version,
                       e.sentiment_model,e.sentiment_model_version,e.sentiment_window_sec,
                       e.analysis_lag_sec,
                       e.created_at, e.market_dataset_id,e.replay_range_from,e.replay_range_to,
                       d.dataset_version, d.revision_no, d.provider, d.symbol, d.timeframe,
                       d.range_from, d.range_to, d.candle_count, d.content_hash,
                       COALESCE(e.bbo_dataset_hash,d.bbo_content_hash),
                       sv.strategy_id, sv.version
                FROM experiments e
                JOIN market_datasets d ON d.id = e.market_dataset_id
                JOIN strategy_versions sv ON sv.id = e.strategy_version_id
                WHERE e.id = %s
                """,
                (experiment_id,),
            )
            row = cur.fetchone()
        if row is None:
            raise DomainError(ERR_VALIDATION, f"experiment {experiment_id} not found")
        (
            eid, owner_id, candidate_definition, candidate_hash,
            initial_equity, fixed_notional, leverage, fee_bps, slippage_bps,
            fill_policy, position_policy, open_position_at_end,
            stop_loss_pct, take_profit_pct, intrabar_priority, evaluator_version,
            sentiment_model, sentiment_model_version, sentiment_window_sec, analysis_lag_sec,
            created_at, _dataset_id, replay_range_from, replay_range_to,
            dataset_version, revision_no, provider, symbol, timeframe,
            range_from, range_to, candle_count, content_hash, bbo_content_hash,
            strategy_id, strategy_version,
        ) = row
        risk = (
            RiskPolicy(
                stop_loss_pct=float(stop_loss_pct) if stop_loss_pct is not None else None,
                take_profit_pct=float(take_profit_pct) if take_profit_pct is not None else None,
                intrabar_priority=intrabar_priority,
            )
            if (stop_loss_pct is not None or take_profit_pct is not None)
            else None
        )
        return ExperimentSnapshot(
            experiment_id=eid,
            owner_id=owner_id,
            strategy=Reference(strategy_id, strategy_version),
            candidate_definition=_hydrate_candidate(candidate_definition),
            candidate_hash=candidate_hash,
            market=MarketSnapshot(
                dataset_version=dataset_version,
                revision_no=revision_no,
                provider=provider,
                symbol=symbol,
                timeframe=timeframe,
                range_from=replay_range_from,
                range_to=replay_range_to,
                candle_count=candle_count,
                content_hash=content_hash,
                bbo_content_hash=bbo_content_hash,
            ),
            initial_equity=float(initial_equity),
            fixed_notional=float(fixed_notional),
            leverage=float(leverage),
            fee_bps=int(fee_bps),
            slippage_bps=int(slippage_bps),
            fill_policy=fill_policy,
            position_policy=position_policy,
            open_position_at_end=open_position_at_end,
            risk_policy=risk,
            evaluator_version=evaluator_version,
            sentiment_model=sentiment_model,
            sentiment_model_version=sentiment_model_version,
            sentiment_window_sec=sentiment_window_sec,
            analysis_lag_sec=analysis_lag_sec,
            created_at=created_at,
        )

    def load_sentiment_windows(
        self, snapshot: ExperimentSnapshot, candles: list[Candle]
    ) -> list[NewsSentimentWindow | None]:
        """Precompute the entire causal sentiment series with one DB query."""
        if not candles:
            return []
        symbol = snapshot.market.symbol.upper()
        coin = symbol
        for suffix in ("USDT", "USDC", "BUSD", "USD"):
            if symbol.endswith(suffix) and len(symbol) > len(suffix):
                coin = symbol[: -len(suffix)]
                break
        first_cutoff = candles[0].close_time - timedelta(seconds=snapshot.analysis_lag_sec)
        last_cutoff = candles[-1].close_time - timedelta(seconds=snapshot.analysis_lag_sec)

        def work() -> list[Any]:
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT n.published_at,
                           CASE s.label WHEN 'POSITIVE' THEN s.score
                                        WHEN 'NEGATIVE' THEN -s.score ELSE 0 END AS signed_score
                    FROM news_items n
                    JOIN sentiment_results s ON s.news_item_id=n.id
                    WHERE %s=ANY(n.related_coins)
                      AND s.model=%s AND s.model_version=%s
                      AND n.published_at > %s - make_interval(secs => %s)
                      AND n.published_at <= %s
                    ORDER BY n.published_at,n.id
                    """,
                    (
                        coin,
                        snapshot.sentiment_model,
                        snapshot.sentiment_model_version,
                        first_cutoff,
                        snapshot.sentiment_window_sec,
                        last_cutoff,
                    ),
                )
                return cur.fetchall()

        rows = self._run(work)
        windows: list[NewsSentimentWindow | None] = []
        left = right = 0
        running_sum = 0.0
        for candle in candles:
            cutoff = candle.close_time - timedelta(seconds=snapshot.analysis_lag_sec)
            lower = cutoff - timedelta(seconds=snapshot.sentiment_window_sec)
            while right < len(rows) and rows[right][0] <= cutoff:
                running_sum += float(rows[right][1])
                right += 1
            while left < right and rows[left][0] <= lower:
                running_sum -= float(rows[left][1])
                left += 1
            count = right - left
            windows.append(
                None
                if count == 0
                else NewsSentimentWindow(
                    window_sec=snapshot.sentiment_window_sec,
                    avg_score=running_sum / count,
                    item_count=count,
                    model_version=snapshot.sentiment_model_version,
                )
            )
        return windows

    def load_dataset(self, snapshot: ExperimentSnapshot) -> tuple[list[Candle], list[BBO]]:
        """Read the frozen dataset snapshot (candles + BBO replay), never the
        operational cache (design.md §12.4 invariant 4)."""
        return self._run(lambda: self._load_dataset_locked(snapshot))

    def load_runtime_spec(self, reference: Reference) -> dict[str, Any] | None:
        def work() -> dict[str, Any] | None:
            with self._conn.cursor() as cur:
                cur.execute(
                    "SELECT spec_json FROM strategy_runtime_specs WHERE strategy_id=%s AND version=%s",
                    (reference.strategy_id, reference.version),
                )
                row = cur.fetchone()
                return None if row is None else row[0]

        return self._run(work)

    def _load_dataset_locked(self, snapshot: ExperimentSnapshot) -> tuple[list[Candle], list[BBO]]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.open_time, c.close_time, c.open, c.high, c.low, c.close, c.volume, c.trade_count
                FROM market_dataset_candles c
                JOIN market_datasets d ON d.id = c.market_dataset_id
                WHERE d.dataset_version = %s AND c.open_time >= %s AND c.close_time <= %s
                ORDER BY c.open_time
                """,
                (snapshot.market.dataset_version, snapshot.market.range_from, snapshot.market.range_to),
            )
            candle_rows = cur.fetchall()
            cur.execute(
                """
                SELECT b.event_time, b.bid, b.bid_qty, b.ask, b.ask_qty, b.update_id
                FROM market_dataset_bbo b
                JOIN market_datasets d ON d.id = b.market_dataset_id
                WHERE d.dataset_version = %s AND b.event_time >= %s AND b.event_time <= %s
                ORDER BY b.event_time, b.source_sequence
                """,
                (snapshot.market.dataset_version, snapshot.market.range_from, snapshot.market.range_to),
            )
            bbo_rows = cur.fetchall()
        candles = [
            Candle(
                provider=snapshot.market.provider,
                symbol=snapshot.market.symbol,
                timeframe=snapshot.market.timeframe,
                open_time=r[0],
                close_time=r[1],
                open=float(r[2]),
                high=float(r[3]),
                low=float(r[4]),
                close=float(r[5]),
                volume=float(r[6]),
                trade_count=r[7],
            )
            for r in candle_rows
        ]
        quotes = [
            BBO(
                provider=snapshot.market.provider,
                symbol=snapshot.market.symbol,
                event_time=r[0],
                bid=float(r[1]),
                bid_qty=float(r[2]),
                ask=float(r[3]),
                ask_qty=float(r[4]),
                update_id=r[5],
                source_sequence=index,
            )
            for index, r in enumerate(bbo_rows, start=1)
        ]
        return candles, quotes

    def load_evaluation_input(self, run_id: UUID) -> tuple[EvaluationInput, str]:
        """Rehydrate immutable run facts for the at-least-once evaluator consumer."""
        def work() -> tuple[EvaluationInput, str]:
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT e.initial_equity,d.timeframe
                    FROM backtest_runs r
                    JOIN experiments e ON e.id=r.experiment_id
                    JOIN market_datasets d ON d.id=e.market_dataset_id
                    WHERE r.id=%s AND r.status='completed'
                    """,
                    (run_id,),
                )
                header = cur.fetchone()
                if header is None:
                    raise DomainError(ERR_VALIDATION, f"completed run {run_id} not found")
                cur.execute(
                    """
                    SELECT sequence_no,side,entry_time,entry_price,quantity,fee_paid,
                           slippage_cost,signal_t,exit_time,exit_price,pnl_absolute,
                           pnl_percent,exit_reason,sl_price,tp_price
                    FROM trades WHERE backtest_run_id=%s ORDER BY sequence_no
                    """,
                    (run_id,),
                )
                trades = [
                    TradeFact(
                        sequence_no=row[0],
                        side=row[1],
                        entry_time=row[2],
                        entry_price=float(row[3]),
                        quantity=float(row[4]),
                        fee_paid=float(row[5]),
                        slippage_cost=float(row[6]),
                        signal_t=row[7],
                        exit_time=row[8],
                        exit_price=None if row[9] is None else float(row[9]),
                        pnl_absolute=None if row[10] is None else float(row[10]),
                        pnl_percent=None if row[11] is None else float(row[11]),
                        exit_reason=row[12],
                        sl_price=None if row[13] is None else float(row[13]),
                        tp_price=None if row[14] is None else float(row[14]),
                    )
                    for row in cur.fetchall()
                ]
                cur.execute(
                    """
                    SELECT point_time,equity,drawdown_pct FROM equity_points
                    WHERE backtest_run_id=%s ORDER BY point_time
                    """,
                    (run_id,),
                )
                points = [
                    EquityPoint(
                        point_time=row[0],
                        equity=float(row[1]),
                        drawdown_pct=None if row[2] is None else float(row[2]),
                    )
                    for row in cur.fetchall()
                ]
            return (
                EvaluationInput(
                    run_id=run_id,
                    initial_equity=float(header[0]),
                    trades=trades,
                    equity_points=points,
                ),
                header[1],
            )

        return self._run(work)

    # -- result persistence --------------------------------------------------------

    def persist_evaluation(self, run_id: UUID, evaluation: Any, rank: bool = True) -> None:
        """Idempotent evaluation insert (`ON CONFLICT DO NOTHING`) + outbox event.
        Called by the in-worker evaluator consumer (design.md §5.7.2 config B)."""
        def work() -> None:
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO evaluations (backtest_run_id, evaluator_version, total_return_pct,
                                             win_rate_pct, max_drawdown_pct, trade_count,
                                             open_trade_count, profit_factor, sharpe_ratio,
                                             avg_trade_pct)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (backtest_run_id, evaluator_version) DO NOTHING
                    RETURNING id
                    """,
                    (
                        run_id, evaluation.evaluator_version, evaluation.total_return_pct,
                        evaluation.win_rate_pct, evaluation.max_drawdown_pct, evaluation.trade_count,
                        evaluation.open_trade_count, evaluation.profit_factor,
                        evaluation.sharpe_ratio, evaluation.avg_trade_pct,
                    ),
                )
                inserted = cur.fetchone()
                if inserted is None:
                    return
                evaluation_id = inserted[0]
                cur.execute(
                    """
                    SELECT e.id,e.correlation_id
                    FROM backtest_runs r JOIN experiments e ON e.id=r.experiment_id
                    WHERE r.id=%s
                    """,
                    (run_id,),
                )
                experiment_id, correlation_id = cur.fetchone()
                cur.execute(
                    """
                    INSERT INTO domain_events (
                        event_type, aggregate_type, aggregate_id, correlation_id, payload
                    ) VALUES ('StrategyEvaluated', 'evaluation', %s, %s, %s)
                    """,
                    (
                        evaluation_id,
                        correlation_id,
                        json.dumps(
                            {
                                "backtest_run_id": str(run_id),
                                "evaluator_version": evaluation.evaluator_version,
                                "occurred_at": datetime.now(tz=UTC).isoformat(),
                            }
                        ),
                    ),
                )
                cur.execute(
                    """
                    UPDATE search_runs s
                    SET tested=s.tested+1,current_candidate_hash=c.candidate_hash,
                        status=CASE
                            WHEN extract(epoch FROM now()-s.created_at) >=
                                 COALESCE((s.stop_conditions->>'max_duration_sec')::int,2147483647)
                                THEN 'completed'
                            WHEN s.tested+s.failed+1 >= s.generated THEN 'completed'
                            ELSE s.status END,
                        stop_reason=CASE
                            WHEN extract(epoch FROM now()-s.created_at) >=
                                 COALESCE((s.stop_conditions->>'max_duration_sec')::int,2147483647)
                                THEN 'max_duration'
                            WHEN s.tested+s.failed+1 >= s.generated THEN
                                CASE
                                    WHEN s.generated >=
                                         COALESCE((s.stop_conditions->>'max_candidates')::int,2147483647)
                                        THEN 'max_candidates'
                                    WHEN s.generator_exhausted THEN 'space_exhausted'
                                    ELSE 'completed'
                                END
                            ELSE s.stop_reason END,
                        updated_at=now()
                    FROM search_candidates c
                    JOIN experiments e ON e.id=c.experiment_id
                    JOIN backtest_runs r ON r.experiment_id=e.id
                    WHERE c.search_run_id=s.id AND r.id=%s
                    """,
                    (run_id,),
                )

                if not rank:
                    self._cancel_terminal_search_queue(cur, experiment_id)
                    return
                cur.execute(
                    """
                    SELECT version,min_trades,weights FROM score_policies
                    WHERE is_active
                    """
                )
                policy = cur.fetchone()
                if policy is None or evaluation.trade_count < policy[1]:
                    self._cancel_terminal_search_queue(cur, experiment_id)
                    return
                metrics = {
                    "total_return_pct": evaluation.total_return_pct,
                    "win_rate_pct": evaluation.win_rate_pct,
                    "max_drawdown_pct": evaluation.max_drawdown_pct,
                    "profit_factor": evaluation.profit_factor,
                    "sharpe_ratio": evaluation.sharpe_ratio,
                }
                score = ScoreRanker().score(metrics, policy[2])
                cur.execute(
                    """
                    INSERT INTO leaderboard_entries(
                        evaluation_id,market_dataset_id,score_policy_version,score
                    )
                    SELECT %s,e.market_dataset_id,%s,%s
                    FROM backtest_runs r JOIN experiments e ON e.id=r.experiment_id
                    WHERE r.id=%s
                    ON CONFLICT(evaluation_id,score_policy_version) DO NOTHING
                    RETURNING id
                    """,
                    (evaluation_id, policy[0], score, run_id),
                )
                entry = cur.fetchone()
                if entry is None:
                    self._cancel_terminal_search_queue(cur, experiment_id)
                    return
                cur.execute(
                    """
                    INSERT INTO domain_events(
                        event_type,aggregate_type,aggregate_id,correlation_id,payload
                    ) VALUES ('LeaderboardUpdated','leaderboard_entry',%s,%s,%s)
                    """,
                    (
                        entry[0],
                        correlation_id,
                        json.dumps(
                            {
                                "evaluation_id": str(evaluation_id),
                                "score_policy_version": policy[0],
                                "score": score,
                                "occurred_at": datetime.now(tz=UTC).isoformat(),
                            }
                        ),
                    ),
                )
                cur.execute(
                    """
                    UPDATE search_runs s
                    SET non_improving=CASE
                            WHEN s.best_score IS NULL OR s.best_score < %(score)s THEN 0
                            ELSE s.non_improving+1 END,
                        best_score=CASE WHEN s.best_score IS NULL OR s.best_score < %(score)s
                                        THEN %(score)s ELSE s.best_score END,
                        status=CASE
                            WHEN s.status='running' AND extract(epoch FROM now()-s.created_at) >=
                                 COALESCE((s.stop_conditions->>'max_duration_sec')::int,2147483647)
                                THEN 'completed'
                            WHEN s.status='running' AND
                                 (CASE WHEN s.best_score IS NULL OR s.best_score < %(score)s
                                       THEN 0 ELSE s.non_improving+1 END) >=
                                 COALESCE((s.stop_conditions->>'max_non_improving')::int,2147483647)
                                THEN 'completed'
                            ELSE s.status END,
                        stop_reason=CASE
                            WHEN s.stop_reason IS NOT NULL THEN s.stop_reason
                            WHEN extract(epoch FROM now()-s.created_at) >=
                                 COALESCE((s.stop_conditions->>'max_duration_sec')::int,2147483647)
                                THEN 'max_duration'
                            WHEN (CASE WHEN s.best_score IS NULL OR s.best_score < %(score)s
                                       THEN 0 ELSE s.non_improving+1 END) >=
                                 COALESCE((s.stop_conditions->>'max_non_improving')::int,2147483647)
                                THEN 'max_non_improving'
                            ELSE s.stop_reason END,
                        updated_at=now()
                    FROM search_candidates c
                    JOIN experiments e ON e.id=c.experiment_id
                    JOIN backtest_runs r ON r.experiment_id=e.id
                    WHERE c.search_run_id=s.id AND r.id=%(run_id)s
                    """,
                    {"score": score, "run_id": run_id},
                )
                self._cancel_terminal_search_queue(cur, experiment_id)

        self._run(work)

    def _persist_result(
        self, cur: Any, job_id: UUID, lease_token: UUID, result: Result
    ) -> UUID | None:
        cur.execute(
            """
            SELECT id, status FROM backtest_runs
            WHERE experiment_id = (SELECT experiment_id FROM backtest_jobs WHERE id = %s)
            """,
            (job_id,),
        )
        run = cur.fetchone()
        if run is not None and run[1] == "completed":
            return run[0]  # takeover after completion: never re-write immutable facts
        settled = sum(1 for t in result.trades if t.exit_time is not None)
        result_hash = canonical_result_hash(result)
        if run is None:
            cur.execute(
                """
                INSERT INTO backtest_runs (experiment_id, status, worker_id, lease_token,
                                           candles_read, signals_count, duration_ms,
                                           result_hash, started_at, finished_at)
                SELECT j.experiment_id, 'completed', j.leased_by, j.lease_token,
                       %s, %s, %s, %s, now(), now()
                FROM backtest_jobs j WHERE j.id = %s
                RETURNING id
                """,
                (
                    result.candles_read,
                    len(result.signals),
                    result.duration_ms,
                    result_hash,
                    job_id,
                ),
            )
            run_id = cur.fetchone()[0]
        else:
            run_id = run[0]
            cur.execute(
                """
                UPDATE backtest_runs
                SET status = 'completed', candles_read = %s, signals_count = %s,
                    duration_ms = %s, result_hash = %s, finished_at = now()
                WHERE id = %s AND lease_token = %s
                """,
                (
                    result.candles_read,
                    len(result.signals),
                    result.duration_ms,
                    result_hash,
                    run_id,
                    lease_token,
                ),
            )
            if cur.rowcount != 1:
                raise DomainError(ERR_LEASE_LOST, f"lost lease on run {run_id} while persisting")

        cur.executemany(
            """
            INSERT INTO trades (backtest_run_id, sequence_no, side, signal_t, entry_time,
                                entry_price, exit_time, exit_price, quantity, fee_paid,
                                slippage_cost, entry_notional, exit_notional, spread_cost,
                                gross_pnl, net_pnl, pnl_absolute, pnl_percent, exit_reason,
                                sl_price, tp_price)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            [
                (
                    run_id, t.sequence_no, t.side, t.signal_t, t.entry_time, t.entry_price,
                    t.exit_time, t.exit_price, t.quantity, t.fee_paid, t.slippage_cost,
                    t.entry_notional, t.exit_notional, t.spread_cost, t.gross_pnl, t.net_pnl,
                    t.pnl_absolute, t.pnl_percent, t.exit_reason, t.sl_price, t.tp_price,
                )
                for t in result.trades
            ],
        )
        cur.executemany(
            """
            INSERT INTO run_signals (backtest_run_id, candle_time, signal, confidence, child_signals)
            VALUES (%s,%s,%s,%s,%s)
            """,
            [
                (
                    run_id, s.candle_time, s.action, s.confidence,
                    json.dumps(s.child_signals) if s.child_signals is not None else None,
                )
                for s in result.signals
            ],
        )
        rows = [(run_id, p.point_time, p.equity, p.drawdown_pct) for p in result.equity_points]
        for start in range(0, len(rows), _EQUITY_BATCH):
            cur.executemany(
                """
                INSERT INTO equity_points (backtest_run_id, point_time, equity, drawdown_pct)
                VALUES (%s,%s,%s,%s)
                """,
                rows[start : start + _EQUITY_BATCH],
            )
        # transactional outbox: BacktestCompleted (design.md §5.7) — identity only
        cur.execute(
            """
            INSERT INTO domain_events (
                event_type, aggregate_type, aggregate_id, correlation_id, payload
            ) VALUES (
                'BacktestCompleted', 'backtest_run', %s,
                (SELECT e.correlation_id FROM experiments e
                 JOIN backtest_jobs j ON j.experiment_id=e.id WHERE j.id=%s), %s
            )
            """,
            (
                run_id,
                job_id,
                json.dumps(
                    {
                        "settled_trade_count": settled,
                        "open_trade_count": len(result.trades) - settled,
                        "duration_ms": result.duration_ms,
                        "result_hash": result_hash,
                        "occurred_at": datetime.now(tz=UTC).isoformat(),
                    }
                ),
            ),
        )
        return run_id
