"""Search contracts (float64).

Mirrors `server/internal/domain/search/contract.go`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from ..common import Decimal
from ..strategy import CandidateStrategy


@dataclass
class SearchSpace:
    strategy_ids: list[str] = field(default_factory=list)
    parameter_grid: dict[str, dict[str, list[Any]]] = field(default_factory=dict)
    cardinality: tuple[int, int] = (0, 0)
    policies: list[str] = field(default_factory=list)
    weight_options: list[Decimal] = field(default_factory=list)


@dataclass
class ScoredCandidate:
    candidate: CandidateStrategy
    score: Decimal


class HashSet(Protocol):
    def has(self, key: str) -> bool: ...

    def add(self, key: str) -> None: ...


@dataclass
class SearchHistory:
    tested_hashes: HashSet | None = None
    top_k: list[ScoredCandidate] = field(default_factory=list)
    best_score: Decimal | None = None
    non_improving_count: int = 0


History = SearchHistory


class CandidateGenerator(Protocol):
    def generator_id(self) -> str: ...

    def generator_version(self) -> str: ...

    def generate(
        self,
        space: SearchSpace,
        batch: int,
        seed: int | None,
        history: SearchHistory,
    ) -> list[CandidateStrategy]: ...


@dataclass
class StopConditions:
    max_candidates: int | None = None
    max_duration_sec: int | None = None
    max_non_improving: int | None = None
    max_failure_rate: Decimal | None = None


@dataclass
class SearchRun:
    generator_id: str
    generator_version: str
    stop_conditions: StopConditions = field(default_factory=StopConditions)
    seed: int | None = None
    execution_config: Any | None = None
