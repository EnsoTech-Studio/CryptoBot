"""Package-owned bootstrap seam for MA/RSI/Bollinger/SR/sentiment plugins.

Mirrors `server/internal/domain/strategy/plugins/catalog.go`. This catalog ships
the two verification strategies of the fixture acceptance
(`specs/python-research.md` AC-07): `ma_cross@v1` (SMA fast/slow) and
`ema_cross@v1` (EMA fast/slow). RSI, Bollinger, support/resistance and sentiment
plugins are future registrations at this same seam — no core change needed.

Shared strict-crossover semantics (identical for MA and EMA):

- diff = fast(i) - slow(i), both indicator values defined at `i` and `i - 1`;
- BUY  when diff > 0 and prev_diff <= 0  (crossed up through zero);
- SELL when diff < 0 and prev_diff >= 0  (crossed down through zero);
- otherwise HOLD.

The emitted `Signal.price` is the just-closed candle's close — the fixture LIMIT
price required by `specs/backtest.md` §B ("Strategy signal dùng candle close làm
LIMIT price trong fixture").
"""

from __future__ import annotations

from typing import Any

from ...common import ACTION_BUY, ACTION_HOLD, ACTION_SELL
from ..contract import AnalysisContext, Definition, Signal
from ..registry import Registry
from .bollinger import BollingerStrategy
from .composite_root import CompositeRoot
from .macd import MACDStrategy
from .news_sentiment import NewsSentimentStrategy
from .rsi import RSIStrategy
from .smc import SMCMarketStructureStrategy
from .support_resistance import SupportResistanceStrategy

DEFAULT_FAST = 20
DEFAULT_SLOW = 50


def _periods(params: dict[str, Any], default_fast: int, default_slow: int) -> tuple[int, int]:
    fast = int(params.get("fast", default_fast))
    slow = int(params.get("slow", default_slow))
    if fast < 1 or slow < 1:
        raise ValueError("fast/slow periods must be >= 1")
    return fast, slow


class MovingAverageCross:
    """Trend plugin: strict crossover of two moving averages of one kind."""

    def __init__(self, kind: str, strategy_id: str, display_name: str) -> None:
        self._kind = kind
        self._strategy_id = strategy_id
        self._display_name = display_name

    # -- strategy contract ------------------------------------------------

    def definition(self) -> Definition:
        return Definition(
            strategy_id=self._strategy_id,
            version="v1",
            family="trend",
            parameters_schema={
                "type": "object",
                "properties": {
                    "fast": {"type": "integer", "minimum": 1},
                    "slow": {"type": "integer", "minimum": 1},
                },
            },
            input_requirements=self.requirements({}),
            overlay_types=["ma_fast", "ma_slow"],
            warm_up_candles=lambda params: max(_periods(params, DEFAULT_FAST, DEFAULT_SLOW)),
            display_name=self._display_name,
            description=(
                f"Strict {self._kind.upper()} fast/slow crossover; "
                "signal price is the closed candle's close."
            ),
        )

    def requirements(self, params: dict[str, Any]) -> list[str]:
        fast, slow = _periods(params, DEFAULT_FAST, DEFAULT_SLOW)
        return [f"{self._kind}:{fast}", f"{self._kind}:{slow}"]

    def analyze(self, context: AnalysisContext) -> Signal:
        fast, slow = _periods(context.params, DEFAULT_FAST, DEFAULT_SLOW)
        fast_key, slow_key = f"{self._kind}:{fast}", f"{self._kind}:{slow}"
        view = context.indicators
        i = context.index
        fast_now, slow_now = view.at(fast_key, i), view.at(slow_key, i)
        fast_prev, slow_prev = view.at(fast_key, i - 1), view.at(slow_key, i - 1)
        if i < 1 or None in (fast_now, slow_now, fast_prev, slow_prev):
            return Signal(action=ACTION_HOLD)
        diff = fast_now - slow_now
        prev_diff = fast_prev - slow_prev
        close = context.candles.at(i).close
        if diff > 0 and prev_diff <= 0:
            return Signal(action=ACTION_BUY, price=close)
        if diff < 0 and prev_diff >= 0:
            return Signal(action=ACTION_SELL, price=close)
        return Signal(action=ACTION_HOLD)


def register_all(registry: Registry) -> None:
    registry.register(lambda: MovingAverageCross("sma", "ma_cross", "MA Cross (SMA)"))
    registry.register(lambda: MovingAverageCross("ema", "ema_cross", "EMA Cross (EMA)"))
    registry.register(RSIStrategy)
    registry.register(BollingerStrategy)
    registry.register(SupportResistanceStrategy)
    registry.register(SMCMarketStructureStrategy)
    registry.register(NewsSentimentStrategy)
    registry.register(MACDStrategy)
    registry.register(CompositeRoot)


def default_registry() -> Registry:
    """Fresh registry with every catalog plugin registered."""
    registry = Registry()
    register_all(registry)
    return registry
