"""Durable executor for queued Strategy Authoring commands."""

from __future__ import annotations

from datetime import timedelta
from threading import Event, Thread
from typing import Any

from ..errors import ApplicationError


class AgentOrchestrator:
    """Claims one persisted job; logical agent roles stay inside research."""

    def __init__(
        self, store: object, authoring: object, lease_seconds: float = 120.0, heartbeat_seconds: float = 30.0
    ) -> None:
        self._store = store
        self._authoring = authoring
        self._lease = timedelta(seconds=lease_seconds)
        self._heartbeat_seconds = heartbeat_seconds

    def process_once(self, worker_id: str) -> bool:
        job: dict[str, Any] | None = self._store.claim_agent_job(worker_id, self._lease)
        if job is None:
            return False
        stop_heartbeat = Event()

        def heartbeat() -> None:
            while not stop_heartbeat.wait(self._heartbeat_seconds):
                if not self._store.heartbeat_agent_job(job["id"], job["lease_token"], self._lease):
                    return

        heartbeat_thread = Thread(target=heartbeat, name="agent-job-heartbeat", daemon=True)
        heartbeat_thread.start()
        try:
            self._authoring.process_claimed_job(job)
        except ApplicationError as exc:
            if exc.status_code >= 500:
                self._store.retry_agent_job(job["id"], job["lease_token"], exc.code)
            else:
                self._store.fail_agent_job(job["id"], job["lease_token"], exc.code)
        except Exception:  # noqa: BLE001 - worker never exposes internals to a draft
            self._store.fail_agent_job(job["id"], job["lease_token"], "agent_internal_error")
        finally:
            stop_heartbeat.set()
            heartbeat_thread.join(timeout=self._heartbeat_seconds * 2)
        return True
