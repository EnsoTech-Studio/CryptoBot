"""PostgreSQL store for leaderboard + experiment facts (stub).

Mirrors `server/internal/infrastructure/postgres/store.go`. Deferred.
"""

from __future__ import annotations

from ...domain.ranking import LeaderboardEntry


class Store:
    def list_leaderboard(self, timeframe: str, symbol: str, top_k: int) -> list[LeaderboardEntry]:
        raise NotImplementedError
