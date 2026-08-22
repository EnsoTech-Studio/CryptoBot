"""Ranking / leaderboard contracts (float64).

Mirrors `server/internal/domain/ranking/contract.go`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from ..common import Decimal


@dataclass
class ScorePolicy:
    version: str
    min_trades: int
    weights: dict[str, Decimal] = field(default_factory=dict)


@dataclass
class LeaderboardEntry:
    entry_id: UUID
    evaluation_id: UUID
    score: Decimal
    rank: int
    score_policy_version: str


class RankingService(Protocol):
    def rank(self, policy: ScorePolicy, score: Decimal, min_trades: int) -> LeaderboardEntry: ...
