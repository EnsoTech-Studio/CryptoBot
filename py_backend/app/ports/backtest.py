"""Backtest engine seam. Mirrors `server/internal/ports/backtest.go`."""

from __future__ import annotations

from typing import Protocol

from ..domain.backtest import ExperimentSnapshot, Result
from ..domain.market import BBO, Candle


class BacktestEngine(Protocol):
    def run(self, snapshot: ExperimentSnapshot, candles: list[Candle], bbo: list[BBO]) -> Result: ...
