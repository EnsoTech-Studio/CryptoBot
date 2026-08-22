"""API response schemas (pydantic, float64).

Contract shapes for the moved endpoints. All numeric fields are Python `float`
(float64). Domain handlers are stubbed (501); these schemas pin the response
contract until the engines are implemented.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class LeaderboardEntryOut(BaseModel):
    entry_id: UUID
    evaluation_id: UUID
    score: float
    rank: int
    score_policy_version: str


class ExperimentSummaryOut(BaseModel):
    experiment_id: UUID
    candidate_hash: str
    status: str
    evaluator_version: str | None = None
    created_at: datetime | None = None


class TradeOut(BaseModel):
    sequence_no: int
    side: str
    entry_time: datetime
    entry_price: float
    quantity: float
    fee_paid: float
    slippage_cost: float
    exit_time: datetime | None = None
    exit_price: float | None = None
    pnl_absolute: float | None = None
    pnl_percent: float | None = None
    exit_reason: str | None = None


class EquityPointOut(BaseModel):
    point_time: datetime
    equity: float
    drawdown_pct: float | None = None
