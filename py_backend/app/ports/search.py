"""Candidate generator seam. Mirrors `server/internal/ports/search.go`."""

from __future__ import annotations

from typing import Protocol

from ..domain.search import SearchHistory, SearchSpace
from ..domain.strategy import CandidateStrategy


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
