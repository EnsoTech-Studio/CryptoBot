"""Backtest job contract (float64).

Mirrors `server/internal/domain/job/contract.go`.
"""

from __future__ import annotations

from dataclasses import dataclass
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
