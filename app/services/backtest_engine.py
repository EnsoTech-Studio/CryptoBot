"""Domain services (engines) — deterministic stubs, float64."""

from __future__ import annotations

from ..domain.backtest import ExperimentSnapshot, Result
from ..domain.market import BBO, Candle


class DeterministicEngine:
    """BBO-limit backtest engine. Deferred — raises `NotImplementedError`."""

    def run(self, snapshot: ExperimentSnapshot, candles: list[Candle], bbo: list[BBO]) -> Result:
        raise NotImplementedError
