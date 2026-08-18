"""Ranking service — scores evaluations into leaderboard entries (float64). Deferred stub."""

from __future__ import annotations

from ..domain.common import Decimal
from ..domain.ranking import LeaderboardEntry, ScorePolicy


class ScoreRanker:
    def rank(self, policy: ScorePolicy, score: Decimal, min_trades: int) -> LeaderboardEntry:
        raise NotImplementedError
