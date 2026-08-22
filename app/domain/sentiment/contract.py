"""Sentiment value objects (float64).

Mirrors `server/internal/domain/sentiment/contract.go`. Sentiment *inference*
remains in the Go `ai` service; these are the shared value objects consumed by
the strategy `AnalysisContext`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..common import Decimal

POSITIVE = "POSITIVE"
NEUTRAL = "NEUTRAL"
NEGATIVE = "NEGATIVE"


@dataclass
class Result:
    label: str
    score: Decimal
    model: str
    model_version: str
    analyzed_at: datetime


@dataclass
class NewsSentimentWindow:
    window_sec: int
    avg_score: Decimal
    item_count: int
    model_version: str
