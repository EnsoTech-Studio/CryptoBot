"""Indicator value objects + library (float64).

Mirrors `server/internal/domain/indicator/contract.go`. `IndicatorView` is the
causal guard: a strategy may only read indicator values up to the current cursor
(rule R2, `specs/python-research.md`). Values inside the warm-up window are
`None` — strategies must treat that as "not ready" and hold.

Requirement strings are the contract between plugin and library:

- ``sma:<period>``  — simple moving average (rolling mean),
- ``ema:<period>``  — exponential moving average, SMA-seeded at ``period - 1``.

The SMA uses a rolling sum and the EMA the standard recursive form with
``alpha = 2 / (period + 1)``; both are float64-deterministic for identical
inputs, so identical replays yield byte-identical series.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import ClassVar

from ..common import Decimal, DomainError, LookAheadError

_REQUIREMENT = re.compile(r"^(sma|ema):([1-9][0-9]{0,6})$")


def parse_requirement(requirement: str) -> tuple[str, int]:
    match = _REQUIREMENT.match(requirement)
    if match is None:
        raise DomainError("validation error", f"unknown indicator requirement {requirement!r}")
    return match.group(1), int(match.group(2))


def simple_moving_average(closes: list[Decimal], period: int) -> list[Decimal | None]:
    out: list[Decimal | None] = [None] * len(closes)
    running = 0.0
    for i, price in enumerate(closes):
        running += price
        if i >= period:
            running -= closes[i - period]
        if i >= period - 1:
            out[i] = running / period
    return out


def exponential_moving_average(closes: list[Decimal], period: int) -> list[Decimal | None]:
    out: list[Decimal | None] = [None] * len(closes)
    if len(closes) < period:
        return out
    alpha = 2.0 / (period + 1)
    out[period - 1] = sum(closes[:period]) / period
    for i in range(period, len(closes)):
        out[i] = closes[i] * alpha + out[i - 1] * (1.0 - alpha)  # type: ignore[operator]
    return out


class IndicatorView:
    """Causal view over precomputed indicator series (no look-ahead).

    `cursor` is the index of the just-closed candle; reads beyond it raise
    `LookAheadError`. Warm-up positions legitimately return `None`.
    """

    def __init__(self, series: dict[str, list[Decimal]], cursor: int) -> None:
        self._series = series
        self._cursor = cursor

    def at(self, name: str, index: int) -> Decimal | None:
        if name not in self._series:
            raise DomainError("validation error", f"indicator {name!r} was not precomputed")
        if index < 0 or index > self._cursor:
            raise LookAheadError(
                f"indicator {name!r} index {index} is outside the causal window [0, {self._cursor}]"
            )
        return self._series[name][index]

    def current(self, name: str) -> Decimal | None:
        return self.at(name, self._cursor)


class Library:
    def precompute(self, closes: list[Decimal], requirements: list[str]) -> dict[str, list[Decimal]]:
        raise NotImplementedError


class DeterministicLibrary(Library):
    """Precomputes every distinct requirement exactly once, in sorted order."""

    _BUILDERS: ClassVar[dict[str, Callable[[list[Decimal], int], list[Decimal | None]]]] = {
        "sma": simple_moving_average,
        "ema": exponential_moving_average,
    }

    def precompute(self, closes: list[Decimal], requirements: list[str]) -> dict[str, list[Decimal]]:
        series: dict[str, list[Decimal]] = {}
        for requirement in sorted(set(requirements)):
            kind, period = parse_requirement(requirement)
            series[requirement] = self._BUILDERS[kind](closes, period)
        return series
