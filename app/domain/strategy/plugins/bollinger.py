from __future__ import annotations

from typing import Any

from ...common import ACTION_BUY, ACTION_HOLD, ACTION_SELL
from ..contract import AnalysisContext, Definition, Signal


class BollingerStrategy:
    def definition(self) -> Definition:
        return Definition(
            strategy_id="bollinger",
            version="v1",
            family="volatility",
            parameters_schema={
                "type": "object",
                "properties": {
                    "period": {"type": "integer", "minimum": 2},
                    "deviation": {"type": "number", "exclusiveMinimum": 0},
                },
            },
            input_requirements=["bollinger_upper:20:2", "bollinger_middle:20:2", "bollinger_lower:20:2"],
            overlay_types=["bollinger_band"],
            warm_up_candles=lambda params: int(params.get("period", 20)),
            display_name="Bollinger Reversion",
            description="Mean-reversion signals outside causal Bollinger bands.",
        )

    def requirements(self, params: dict[str, Any]) -> list[str]:
        period = int(params.get("period", 20))
        deviation = float(params.get("deviation", 2.0))
        suffix = f"{period}:{deviation:g}"
        return [
            f"bollinger_upper:{suffix}",
            f"bollinger_middle:{suffix}",
            f"bollinger_lower:{suffix}",
        ]

    def analyze(self, context: AnalysisContext) -> Signal:
        upper_key, _, lower_key = self.requirements(context.params)
        upper = context.indicators.current(upper_key)
        lower = context.indicators.current(lower_key)
        if upper is None or lower is None:
            return Signal(action=ACTION_HOLD)
        price = context.candles.at(context.index).close
        if price < lower:
            return Signal(action=ACTION_BUY, price=price, confidence=min(1.0, (lower - price) / lower))
        if price > upper:
            return Signal(action=ACTION_SELL, price=price, confidence=min(1.0, (price - upper) / upper))
        return Signal(action=ACTION_HOLD)

