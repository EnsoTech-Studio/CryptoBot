"""Backtest job contract (float64).

Mirrors `server/internal/domain/job/contract.go`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from ..backtest import ExperimentSnapshot
from ..common import JobStatus


@dataclass
class BacktestJob:
    id: UUID
    experiment_id: UUID
    snapshot: ExperimentSnapshot
    status: JobStatus
    priority: int
    attempt: int
    max_attempts: int
    leased_by: str | None = None
    lease_token: UUID | None = None
    lease_expires_at: datetime | None = None
    # claim-time run takeover bookkeeping (design.md §8.3.2): the run row this
    # claim owns, and whether the run was already completed so the worker skips
    # the engine entirely (AC-05c/AC-05d)
    run_id: UUID | None = field(default=None)
    run_already_completed: bool = field(default=False)
