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

import math
import re
from collections.abc import Callable
from typing import ClassVar

from ..common import Decimal, DomainError, LookAheadError

_SINGLE_REQUIREMENT = re.compile(
    r"^(sma|ema|rsi|support|resistance):([1-9][0-9]{0,6})$"
)
_BOLLINGER_REQUIREMENT = re.compile(
    r"^bollinger_(upper|middle|lower):([1-9][0-9]{0,6}):([0-9]+(?:\.[0-9]+)?)$"
)
_MACD_REQUIREMENT = re.compile(
    r"^macd_(line|signal|hist):([1-9][0-9]{0,6}):([1-9][0-9]{0,6}):([1-9][0-9]{0,6})$"
)


def parse_requirement(requirement: str) -> tuple[str, tuple[float, ...]]:
    match = _SINGLE_REQUIREMENT.match(requirement)
    if match:
        return match.group(1), (float(match.group(2)),)
    match = _BOLLINGER_REQUIREMENT.match(requirement)
    if match:
        return f"bollinger_{match.group(1)}", (float(match.group(2)), float(match.group(3)))
    match = _MACD_REQUIREMENT.match(requirement)
    if match:
        return f"macd_{match.group(1)}", tuple(float(match.group(i)) for i in range(2, 5))
    raise DomainError("validation error", f"unknown indicator requirement {requirement!r}")


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


def relative_strength_index(closes: list[Decimal], period: int) -> list[Decimal | None]:
    out: list[Decimal | None] = [None] * len(closes)
    if len(closes) <= period:
        return out
    gains = [max(0.0, closes[i] - closes[i - 1]) for i in range(1, len(closes))]
    losses = [max(0.0, closes[i - 1] - closes[i]) for i in range(1, len(closes))]
    average_gain = sum(gains[:period]) / period
    average_loss = sum(losses[:period]) / period
    out[period] = 100.0 if average_loss == 0 else 100.0 - 100.0 / (1.0 + average_gain / average_loss)
    for index in range(period + 1, len(closes)):
        average_gain = (average_gain * (period - 1) + gains[index - 1]) / period
        average_loss = (average_loss * (period - 1) + losses[index - 1]) / period
        out[index] = (
            100.0
            if average_loss == 0
            else 100.0 - 100.0 / (1.0 + average_gain / average_loss)
        )
    return out


def rolling_extreme(closes: list[Decimal], period: int, maximum: bool) -> list[Decimal | None]:
    out: list[Decimal | None] = [None] * len(closes)
    select = max if maximum else min
    for index in range(period - 1, len(closes)):
        out[index] = select(closes[index - period + 1 : index + 1])
    return out


def bollinger_band(
    closes: list[Decimal], period: int, deviation: float, band: str
) -> list[Decimal | None]:
    middle = simple_moving_average(closes, period)
    out: list[Decimal | None] = [None] * len(closes)
    for index in range(period - 1, len(closes)):
        mean = middle[index]
        assert mean is not None
        variance = sum((value - mean) ** 2 for value in closes[index - period + 1 : index + 1]) / period
        width = deviation * math.sqrt(variance)
        out[index] = mean if band == "middle" else mean + width if band == "upper" else mean - width
    return out


def macd_series(
    closes: list[Decimal], fast: int, slow: int, signal_period: int, component: str
) -> list[Decimal | None]:
    if fast >= slow:
        raise DomainError("validation error", "MACD fast period must be smaller than slow period")
    fast_values = exponential_moving_average(closes, fast)
    slow_values = exponential_moving_average(closes, slow)
    line: list[Decimal | None] = [
        None if fast_value is None or slow_value is None else fast_value - slow_value
        for fast_value, slow_value in zip(fast_values, slow_values, strict=True)
    ]
    available = [value for value in line if value is not None]
    compact_signal = exponential_moving_average(available, signal_period)
    signal_values: list[Decimal | None] = [None] * len(closes)
    start = next((index for index, value in enumerate(line) if value is not None), len(closes))
    for offset, value in enumerate(compact_signal):
        signal_values[start + offset] = value
    if component == "line":
        return line
    if component == "signal":
        return signal_values
    return [
        None if value is None or signal is None else value - signal
        for value, signal in zip(line, signal_values, strict=True)
    ]


class IndicatorView:
    """Causal view over precomputed indicator series (no look-ahead).

    `cursor` is the index of the just-closed candle; reads beyond it raise
    `LookAheadError`. Warm-up positions legitimately return `None`.
    """

    def __init__(self, series: dict[str, list[Decimal | None]], cursor: int) -> None:
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
    def precompute(
        self, closes: list[Decimal], requirements: list[str]
    ) -> dict[str, list[Decimal | None]]:
        raise NotImplementedError


class DeterministicLibrary(Library):
    """Precomputes every distinct requirement exactly once, in sorted order."""

    _BUILDERS: ClassVar[dict[str, Callable[[list[Decimal], int], list[Decimal | None]]]] = {
        "sma": simple_moving_average,
        "ema": exponential_moving_average,
        "rsi": relative_strength_index,
    }

    def precompute(
        self, closes: list[Decimal], requirements: list[str]
    ) -> dict[str, list[Decimal | None]]:
        series: dict[str, list[Decimal | None]] = {}
        for requirement in sorted(set(requirements)):
            kind, arguments = parse_requirement(requirement)
            if kind in self._BUILDERS:
                series[requirement] = self._BUILDERS[kind](closes, int(arguments[0]))
            elif kind in ("support", "resistance"):
                series[requirement] = rolling_extreme(
                    closes, int(arguments[0]), maximum=kind == "resistance"
                )
            elif kind.startswith("bollinger_"):
                series[requirement] = bollinger_band(
                    closes, int(arguments[0]), arguments[1], kind.removeprefix("bollinger_")
                )
            elif kind.startswith("macd_"):
                series[requirement] = macd_series(
                    closes,
                    int(arguments[0]),
                    int(arguments[1]),
                    int(arguments[2]),
                    kind.removeprefix("macd_"),
                )
            else:  # pragma: no cover - parser and builders are updated together
                raise DomainError("validation error", f"unsupported indicator kind {kind}")
        return series
