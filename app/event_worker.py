"""Transactional-outbox consumer for evaluation/ranking and event delivery."""

from __future__ import annotations

import json
import os
import signal
import sys
import threading
from datetime import UTC, datetime
from uuid import UUID

from .config import Settings
from .infrastructure.ai import DiscoveryLLMHTTPAdapter
from .infrastructure.postgres.dispatcher import PostgresJobDispatcher
from .infrastructure.postgres.outbox import ClaimedEvent, PostgresOutbox
from .infrastructure.postgres.store import Store
from .services.evaluator import DeterministicEvaluator
from .worker import default_evaluation_policy


def _log_event(level: str, operation: str, event: ClaimedEvent, **fields: object) -> None:
    print(
        json.dumps(
            {
                "timestamp": datetime.now(tz=UTC).isoformat(),
                "level": level,
                "service": "research-event-worker",
                "operation": operation,
                "event_id": str(event.event_id),
                "aggregate_id": str(event.aggregate_id),
                "event_type": event.event_type,
                "correlation_id": event.correlation_id,
                "attempt": event.attempt,
                **fields,
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        file=sys.stderr if level == "error" else sys.stdout,
        flush=True,
    )


class EventWorker:
    def __init__(self, conninfo: str, worker_id: str, lease_seconds: int = 60) -> None:
        settings = Settings.from_env()
        self._outbox = PostgresOutbox(conninfo, worker_id, lease_seconds=lease_seconds)
        self._dispatcher = PostgresJobDispatcher(conninfo)
        self._discovery_llm = DiscoveryLLMHTTPAdapter(settings.ai_service_url, settings.ai_timeout_s)
        self._store = Store(conninfo, self._discovery_llm, settings.discovery_demo_mode)
        self._store.reconcile_discovery()
        self._evaluator = DeterministicEvaluator()
        self._stop = threading.Event()

    def stop(self, *_: object) -> None:
        self._stop.set()

    def close(self) -> None:
        self._outbox.close()
        self._dispatcher.close()
        self._discovery_llm.close()

    def run_forever(self) -> None:
        while not self._stop.is_set():
            event = self._outbox.claim()
            if event is None:
                self._stop.wait(0.5)
                continue
            try:
                self._handle(event)
                self._outbox.complete(event.event_id)
            except Exception as exc:  # noqa: BLE001 - retry/dead-letter boundary
                self._outbox.fail(event, type(exc).__name__)
                _log_event(
                    "error",
                    "event_delivery_failed",
                    event,
                    error_code=type(exc).__name__,
                )

    def _handle(self, event: ClaimedEvent) -> None:
        if event.event_type != "BacktestCompleted":
            return
        evaluation_input, timeframe = self._dispatcher.load_evaluation_input(
            UUID(str(event.aggregate_id))
        )
        evaluation = self._evaluator.evaluate(
            evaluation_input, default_evaluation_policy(timeframe)
        )
        self._dispatcher.persist_evaluation(event.aggregate_id, evaluation)
        self._store.advance_discovery_for_experiment(
            self._dispatcher.experiment_id_for_run(UUID(str(event.aggregate_id)))
        )


def main() -> int:
    settings = Settings.from_env()
    worker = EventWorker(
        settings.database_url,
        os.getenv("EVENT_WORKER_ID", "events-v2"),
        lease_seconds=settings.event_lease_s,
    )
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, worker.stop)
    try:
        worker.run_forever()
    finally:
        worker.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
