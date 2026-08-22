"""Job dispatcher seam. Mirrors `server/internal/ports/job.go`."""

from __future__ import annotations

from datetime import timedelta
from typing import Protocol
from uuid import UUID

from ..domain.job import BacktestJob


class JobDispatcher(Protocol):
    def enqueue(self, job: BacktestJob) -> None: ...

    def claim(self, worker_id: str, lease: timedelta) -> BacktestJob: ...

    def complete(self, job_id: UUID) -> None: ...

    def fail(self, job_id: UUID, err: Exception, retryable: bool) -> None: ...
