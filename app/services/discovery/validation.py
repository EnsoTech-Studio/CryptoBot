"""Chronological split and anti-overfit assessment policy."""

from __future__ import annotations

import math
import statistics
from decimal import Decimal
from typing import Any


def discovery_split(candle_count: int) -> dict[str, tuple[int, int]]:
    """Freeze 60/20/20 index boundaries before any discovery admission."""
    train_end = candle_count * 60 // 100
    validation_end = candle_count * 80 // 100
    validation_width = (validation_end - train_end) // 3
    if train_end < 1 or validation_width < 1 or candle_count <= validation_end:
        raise ValueError("dataset too small for discovery split")
    return {
        "train": (0, train_end),
        "validation_1": (train_end, train_end + validation_width),
        "validation_2": (train_end + validation_width, train_end + validation_width * 2),
        "validation_3": (train_end + validation_width * 2, validation_end),
        "test": (validation_end, candle_count),
    }


def discovery_assessment(
    train: dict[str, Any],
    validations: list[dict[str, Any]],
    complexity: float,
    correlations: list[float | None] | None = None,
    archive_best_score: float | None = None,
    demo_mode: bool = False,
) -> dict[str, Any]:
    """Apply train/validation gates; test metrics never enter this function.

    Demo mode keeps the split and test seal intact but admits candidates with
    too few/no trades so the UI can demonstrate the complete loop. It is
    explicitly opt-in and marks the assessment as a demo override.
    """
    if len(validations) != 3:
        raise ValueError("discovery requires exactly three validation windows")
    train_sharpe = _assessment_sharpe(train, demo_mode)
    if train_sharpe is None or (not demo_mode and int(train.get("trade_count", 0)) < 10):
        return {"accepted": False, "rejection_reason": "cheap_filter"}
    validation_sharpes = [_assessment_sharpe(item, demo_mode) for item in validations]
    if any(
        sharpe is None or (not demo_mode and int(item.get("trade_count", 0)) < 10)
        for item, sharpe in zip(validations, validation_sharpes)
    ):
        if demo_mode:
            return _demo_assessment(complexity)
        return {"accepted": False, "rejection_reason": "validation_gate"}
    median = statistics.median(float(sharpe) for sharpe in validation_sharpes if sharpe is not None)
    gap = abs(float(train_sharpe) - median)
    if gap > 1.0:
        if demo_mode:
            return _demo_assessment(complexity, median=median, gap=gap)
        return {
            "accepted": False,
            "rejection_reason": "generalization_gap",
            "median_validation_sharpe": median,
            "generalization_gap": gap,
        }
    correlations = correlations or []
    if any(value is None for value in correlations):
        if demo_mode:
            return _demo_assessment(complexity, median=median, gap=gap)
        return {
            "accepted": False,
            "rejection_reason": "insufficient_return_alignment",
            "median_validation_sharpe": median,
            "generalization_gap": gap,
        }
    similarity = min(1.0, max(0.0, (max(correlations, default=0.0) - 0.95) / 0.05))
    candidate_complexity = min(1.0, max(0.0, float(complexity)))
    drawdown = max(abs(float(item.get("max_drawdown_pct", 0.0))) for item in validations)
    score = median - 0.5 * gap - 0.2 * drawdown / 100 - 0.1 * candidate_complexity - 0.2 * similarity
    if demo_mode and score <= 0:
        return _demo_assessment(complexity, median=median, gap=gap, similarity=similarity)
    if similarity and archive_best_score is not None and score >= archive_best_score + 0.10:
        score += 0.2 * similarity
        similarity = 0.0
    return {
        "accepted": score > 0,
        "rejection_reason": None if score > 0 else "non_positive_score",
        "score": score,
        "median_validation_sharpe": median,
        "generalization_gap": gap,
        "complexity": candidate_complexity,
        "similarity": similarity,
    }


def _assessment_sharpe(metric: dict[str, Any], demo_mode: bool) -> float | None:
    sharpe = metric.get("sharpe_ratio")
    if _finite(sharpe):
        return float(sharpe)
    if demo_mode and _finite(metric.get("total_return_pct")):
        return float(metric["total_return_pct"])
    return None


def _demo_assessment(
    complexity: float,
    *,
    median: float = 0.0,
    gap: float = 0.0,
    similarity: float = 0.0,
) -> dict[str, Any]:
    return {
        "accepted": True,
        "rejection_reason": None,
        "score": 0.0,
        "median_validation_sharpe": median,
        "generalization_gap": gap,
        "complexity": min(1.0, max(0.0, float(complexity))),
        "similarity": similarity,
        "demo_override": "cheap_filter",
    }


def discovery_complexity(definition: dict[str, Any]) -> float:
    """Clamp flat leaf count and configured parameter count to [0, 1]."""
    leaves = definition.get("children") if definition.get("strategy_id") == "composite" else None
    leaves = leaves if isinstance(leaves, list) else [definition]
    parameters = sum(len(leaf.get("parameters", {})) for leaf in leaves if isinstance(leaf, dict))
    return min(1.0, ((len(leaves) - 1) / 4 + min(1.0, parameters / 10)) / 2)


def _finite(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return False
    return math.isfinite(float(value))
