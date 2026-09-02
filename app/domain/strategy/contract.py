"""Strategy domain contracts (float64).

Mirrors `server/internal/domain/strategy/contract.go`. All numeric fields are
Python `float` (float64).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from ..common import Action, Decimal, Timeframe
from ..indicator import IndicatorView
from ..market import CausalCandles
from ..sentiment import NewsSentimentWindow

Params = dict[str, Any]


@dataclass
class Definition:
    strategy_id: str
    version: str
    family: str | None = None
    parameters_schema: Any | None = None
    input_requirements: list[str] = field(default_factory=list)
    overlay_types: list[str] = field(default_factory=list)
    warm_up_candles: Any | None = None  # callable(Params) -> int
    is_composite: bool = False
    display_name: str = ""
    description: str = ""
    code_fingerprint: str | None = None


@dataclass
class AnalysisContext:
    provider: str
    symbol: str
    timeframe: Timeframe
    candles: CausalCandles
    index: int
    indicators: IndicatorView
    news_sentiment: NewsSentimentWindow | None = None
    params: Params = field(default_factory=dict)


@dataclass
class Signal:
    action: Action
    confidence: Decimal | None = None
    price: Decimal | None = None
    signed_size: Decimal | None = None
    evidence: Any | None = None


class Strategy(Protocol):
    def definition(self) -> Definition: ...

    def analyze(self, context: AnalysisContext) -> Signal: ...


@dataclass
class Reference:
    strategy_id: str
    version: str


@dataclass
class ChildSignal:
    strategy: Reference
    signal: Signal
    weight: Decimal


@dataclass
class ResolvedSignal:
    strategy_id: str
    version: str
    signal: Signal
    weight: Decimal


@dataclass
class CombinationPolicy:
    policy: str
    threshold: Decimal
    encoding: dict[str, int]


@dataclass
class ChildDefinition:
    strategy_id: str
    version: str
    parameters: Params
    weight: Decimal


@dataclass
class CompositeDefinition:
    strategy_id: str
    version: str
    children: list[ChildDefinition]
    combination: CombinationPolicy


CompositeSpec = CompositeDefinition


@dataclass
class CandidateStrategy:
    definition: CompositeDefinition
    candidate_hash: str
    generated_by: str
    generation_meta: Any | None = None
