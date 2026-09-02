"""Lease-based at-least-once PostgreSQL outbox consumer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Callable, TypeVar
from uuid import UUID

import psycopg
from psycopg.rows import dict_row


@dataclass(frozen=True)
class ClaimedEvent:
    event_id: UUID
    event_type: str
    aggregate_id: UUID
    payload: dict[str, Any]
    attempt: int
    correlation_id: str | None = None


T = TypeVar("T")


class PostgresOutbox:
    """Serial outbox consumer backed by one bounded, reusable connection."""

    def __init__(self, conninfo: str, consumer_id: str, lease_seconds: int = 60) -> None:
        self._consumer_id = consumer_id
        self._lease = timedelta(seconds=lease_seconds)
        self._connection = psycopg.connect(
            conninfo,
            connect_timeout=5,
            row_factory=dict_row,
            autocommit=False,
            prepare_threshold=None,
        )

    def close(self) -> None:
        self._connection.close()

    def _transaction(self, work: Callable[[psycopg.Connection[Any]], T]) -> T:
        try:
            result = work(self._connection)
            self._connection.commit()
            return result
        except Exception:
            self._connection.rollback()
            raise

    def claim(self) -> ClaimedEvent | None:
        def work(connection: psycopg.Connection[Any]) -> ClaimedEvent | None:
            row = connection.execute(
                """
                WITH candidate AS (
                    SELECT e.event_id FROM domain_events e
                    WHERE (e.dispatch_status='pending' AND e.next_attempt_at<=now())
                       OR (e.dispatch_status='claimed' AND e.claim_expires_at<now())
                    ORDER BY e.occurred_at,e.event_id
                    FOR UPDATE SKIP LOCKED LIMIT 1
                )
                UPDATE domain_events e
                SET dispatch_status='claimed',claimed_by=%s,
                    claim_expires_at=now()+%s,attempt=e.attempt+1
                FROM candidate WHERE e.event_id=candidate.event_id
                RETURNING e.event_id,e.event_type,e.aggregate_id,e.payload,e.attempt,
                          e.correlation_id
                """,
                (self._consumer_id, self._lease),
            ).fetchone()
            return ClaimedEvent(**row) if row else None

        return self._transaction(work)

    def complete(self, event_id: UUID) -> None:
        def work(connection: psycopg.Connection[Any]) -> None:
            consumed = connection.execute(
                "SELECT 1 FROM event_consumptions WHERE event_id=%s AND consumer_id=%s",
                (event_id, self._consumer_id),
            ).fetchone()
            if consumed is not None:
                return
            delivered = connection.execute(
                """
                UPDATE domain_events SET dispatch_status='delivered',delivered_at=now(),
                    claimed_by=NULL,claim_expires_at=NULL,last_error=NULL
                WHERE event_id=%s AND dispatch_status='claimed' AND claimed_by=%s
                RETURNING event_id
                """,
                (event_id, self._consumer_id),
            ).fetchone()
            if delivered is None:
                raise RuntimeError("outbox lease lost before completion")
            connection.execute(
                """
                INSERT INTO event_consumptions(event_id,consumer_id)
                VALUES (%s,%s) ON CONFLICT DO NOTHING
                """,
                (event_id, self._consumer_id),
            )

        self._transaction(work)

    def fail(self, event: ClaimedEvent, error_code: str) -> None:
        delay = min(300, 2 ** min(event.attempt, 8))

        def work(connection: psycopg.Connection[Any]) -> None:
            connection.execute(
                """
                UPDATE domain_events
                SET dispatch_status=(CASE WHEN attempt>=max_attempts THEN 'dead'
                                          ELSE 'pending' END)::event_dispatch_status,
                    next_attempt_at=now()+make_interval(secs => %s),
                    claimed_by=NULL,claim_expires_at=NULL,last_error=%s
                WHERE event_id=%s AND dispatch_status='claimed' AND claimed_by=%s
                """,
                (delay, error_code[:500], event.event_id, self._consumer_id),
            )

        self._transaction(work)
