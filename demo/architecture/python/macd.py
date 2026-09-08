from __future__ import annotations

from typing import Any

from ...common import ACTION_BUY, ACTION_HOLD, ACTION_SELL
from ..contract import AnalysisContext, Definition, Signal


class MACDStrategy:
    def definition(self) -> Definition:
        return Definition(
            strategy_id="macd",
            version="v1",
            family="trend",
            parameters_schema={
                "type": "object",
                "properties": {
                    "fast": {"type": "integer", "minimum": 1},
                    "slow": {"type": "integer", "minimum": 2},
                    "signal": {"type": "integer", "minimum": 1},
                },
            },
            input_requirements=["macd_line:12:26:9", "macd_signal:12:26:9", "macd_hist:12:26:9"],
            overlay_types=["macd"],
            warm_up_candles=lambda params: int(params.get("slow", 26)) + int(params.get("signal", 9)),
            display_name="MACD Cross",
            description="MACD line and signal crossover.",
        )

    def requirements(self, params: dict[str, Any]) -> list[str]:
        fast = int(params.get("fast", 12))
        slow = int(params.get("slow", 26))
        signal = int(params.get("signal", 9))
        suffix = f"{fast}:{slow}:{signal}"
        return [f"macd_line:{suffix}", f"macd_signal:{suffix}", f"macd_hist:{suffix}"]

    def analyze(self, context: AnalysisContext) -> Signal:
        if context.index < 1:
            return Signal(action=ACTION_HOLD)
        line_key, signal_key, _ = self.requirements(context.params)
        line = context.indicators.at(line_key, context.index)
        signal = context.indicators.at(signal_key, context.index)
        previous_line = context.indicators.at(line_key, context.index - 1)
        previous_signal = context.indicators.at(signal_key, context.index - 1)
        if None in (line, signal, previous_line, previous_signal):
            return Signal(action=ACTION_HOLD)
        price = context.candles.at(context.index).close
        if line > signal and previous_line <= previous_signal:
            return Signal(action=ACTION_BUY, price=price, confidence=min(1.0, abs(line - signal) / price))
        if line < signal and previous_line >= previous_signal:
            return Signal(action=ACTION_SELL, price=price, confidence=min(1.0, abs(line - signal) / price))
        return Signal(action=ACTION_HOLD)

