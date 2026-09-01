from __future__ import annotations

from typing import Any

from ...common import ACTION_BUY, ACTION_HOLD, ACTION_SELL
from ..contract import AnalysisContext, Definition, Signal


class SMCMarketStructureStrategy:
    """Causal break-of-structure admission for the SMC catalog entry."""

    def definition(self) -> Definition:
        return Definition(
            strategy_id="smc",
            version="v1",
            family="structure",
            parameters_schema={
                "type": "object",
                "properties": {"swing_period": {"type": "integer", "minimum": 2}},
            },
            input_requirements=["support:20", "resistance:20"],
            overlay_types=["market_structure"],
            warm_up_candles=lambda params: int(params.get("swing_period", 20)) + 1,
            display_name="SMC Market Structure Break",
            description="Causal bullish/bearish break of prior rolling structure.",
        )

    def requirements(self, params: dict[str, Any]) -> list[str]:
        period = int(params.get("swing_period", 20))
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
        previous_close = context.candles.at(context.index - 1).close
        # ponytail: BOS-only SMC; add order-block/liquidity modules only with their own fixtures.
        if price > resistance and previous_close <= resistance:
            return Signal(
                action=ACTION_BUY,
                price=price,
                confidence=min(1.0, (price - resistance) / max(abs(resistance), 1e-12)),
                evidence={"structure": "bullish_bos", "level": resistance},
            )
        if price < support and previous_close >= support:
            return Signal(
                action=ACTION_SELL,
                price=price,
                confidence=min(1.0, (support - price) / max(abs(support), 1e-12)),
                evidence={"structure": "bearish_bos", "level": support},
            )
        return Signal(action=ACTION_HOLD)
