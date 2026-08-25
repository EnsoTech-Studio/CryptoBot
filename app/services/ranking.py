"""Pure, versioned leaderboard score calculation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..domain.common import ERR_VALIDATION, DomainError


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return min(high, max(low, value))


class ScoreRanker:
    """Calculate a comparable 0..100 score from immutable evaluation metrics."""

    _supported = {
        "total_return_pct",
        "win_rate_pct",
        "max_drawdown_pct",
        "profit_factor",
        "sharpe_ratio",
    }

    def score(self, metrics: Mapping[str, Any], weights: Mapping[str, float]) -> float:
        if not weights or not set(weights).issubset(self._supported):
            raise DomainError(ERR_VALIDATION, "unsupported score policy metric")
        if any(float(weight) < 0 for weight in weights.values()):
            raise DomainError(ERR_VALIDATION, "score policy weights must be non-negative")
        if abs(sum(float(value) for value in weights.values()) - 1.0) > 1e-9:
            raise DomainError(ERR_VALIDATION, "score policy weights must sum to 1.0")

        normalized = {
            "total_return_pct": _clamp((float(metrics["total_return_pct"]) + 100.0) / 200.0),
            "win_rate_pct": _clamp(float(metrics["win_rate_pct"]) / 100.0),
            "max_drawdown_pct": 1.0
            - _clamp(abs(float(metrics["max_drawdown_pct"])) / 100.0),
            "profit_factor": _clamp(float(metrics.get("profit_factor") or 0.0) / 5.0),
            "sharpe_ratio": _clamp((float(metrics.get("sharpe_ratio") or 0.0) + 3.0) / 6.0),
        }
        return round(
            100.0
            * sum(normalized[name] * float(weight) for name, weight in weights.items()),
            6,
        )
