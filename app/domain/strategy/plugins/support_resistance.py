from __future__ import annotations

from typing import Any

from ...common import ACTION_BUY, ACTION_HOLD, ACTION_SELL
from ..contract import AnalysisContext, Definition, Signal


class SupportResistanceStrategy:
    def definition(self) -> Definition:
        return Definition(
            strategy_id="support_resistance",
            version="v1",
            family="structure",
            parameters_schema={
                "type": "object",
                "properties": {"period": {"type": "integer", "minimum": 2}},
            },
            input_requirements=["support:20", "resistance:20"],
            overlay_types=["support", "resistance"],
            warm_up_candles=lambda params: int(params.get("period", 20)) + 1,
            display_name="Support / Resistance Breakout",
            description="Breakout against prior rolling support and resistance.",
        )

    def requirements(self, params: dict[str, Any]) -> list[str]:
        period = int(params.get("period", 20))
        return [f"support:{period}", f"resistance:{period}"]

    def analyze(self, context: AnalysisContext) -> Signal:
        if context.index < 1:
            return Signal(action=ACTION_HOLD)
        support_key, resistance_key = self.requirements(context.params)
        support = context.indicators.at(support_key, context.index - 1)
        resistance = context.indicators.at(resistance_key, context.index - 1)
        if support is None or resistance is None:
            return Signal(action=ACTION_HOLD)
        price = context.candles.at(context.index).close
        if price > resistance:
            return Signal(action=ACTION_BUY, price=price, confidence=min(1.0, (price - resistance) / resistance))
        if price < support:
            return Signal(action=ACTION_SELL, price=price, confidence=min(1.0, (support - price) / support))
        return Signal(action=ACTION_HOLD)

