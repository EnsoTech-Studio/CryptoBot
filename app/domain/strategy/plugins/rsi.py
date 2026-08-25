from __future__ import annotations

from typing import Any

from ...common import ACTION_BUY, ACTION_HOLD, ACTION_SELL
from ..contract import AnalysisContext, Definition, Signal


class RSIStrategy:
    def definition(self) -> Definition:
        return Definition(
            strategy_id="rsi",
            version="v1",
            family="momentum",
            parameters_schema={
                "type": "object",
                "properties": {
                    "period": {"type": "integer", "minimum": 2},
                    "oversold": {"type": "number", "minimum": 0, "maximum": 100},
                    "overbought": {"type": "number", "minimum": 0, "maximum": 100},
                },
            },
            input_requirements=["rsi:14"],
            overlay_types=["rsi"],
            warm_up_candles=lambda params: int(params.get("period", 14)) + 1,
            display_name="Relative Strength Index",
            description="RSI threshold crossing using closed candles only.",
        )

    def requirements(self, params: dict[str, Any]) -> list[str]:
        return [f"rsi:{int(params.get('period', 14))}"]

    def analyze(self, context: AnalysisContext) -> Signal:
        period = int(context.params.get("period", 14))
        oversold = float(context.params.get("oversold", 30.0))
        overbought = float(context.params.get("overbought", 70.0))
        key = f"rsi:{period}"
        if context.index < 1:
            return Signal(action=ACTION_HOLD)
        current = context.indicators.at(key, context.index)
        previous = context.indicators.at(key, context.index - 1)
        if current is None or previous is None:
            return Signal(action=ACTION_HOLD)
        price = context.candles.at(context.index).close
        if current <= oversold < previous:
            return Signal(action=ACTION_BUY, price=price, confidence=(oversold - current) / 100.0)
        if current >= overbought > previous:
            return Signal(action=ACTION_SELL, price=price, confidence=(current - overbought) / 100.0)
        return Signal(action=ACTION_HOLD)

