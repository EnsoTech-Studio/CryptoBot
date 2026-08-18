"""Indicator value objects + library (float64).

Mirrors `server/internal/domain/indicator/contract.go`. `IndicatorView` is the
causal guard: a strategy may only read indicator values up to the current cursor.
"""

from __future__ import annotations

from ..common import Decimal


class IndicatorView:
    """Causal view over precomputed indicator series (no look-ahead)."""

    def __init__(self, series: dict[str, list[Decimal]], cursor: int) -> None:
        raise NotImplementedError

    def at(self, name: str, index: int) -> Decimal:
        raise NotImplementedError

    def current(self, name: str) -> Decimal:
        raise NotImplementedError


class Library:
    def precompute(self, closes: list[Decimal], requirements: list[str]) -> dict[str, list[Decimal]]:
        raise NotImplementedError


class DeterministicLibrary(Library):
    def precompute(self, closes: list[Decimal], requirements: list[str]) -> dict[str, list[Decimal]]:
        raise NotImplementedError
