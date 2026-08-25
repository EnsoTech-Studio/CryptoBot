from __future__ import annotations

from ...common import ACTION_BUY, ACTION_HOLD, ACTION_SELL
from ..contract import AnalysisContext, Definition, Signal


class NewsSentimentStrategy:
    def definition(self) -> Definition:
        return Definition(
            strategy_id="news_sentiment",
            version="v1",
            family="information",
            parameters_schema={
                "type": "object",
                "properties": {
                    "buy_above": {"type": "number", "minimum": -1, "maximum": 1},
                    "sell_below": {"type": "number", "minimum": -1, "maximum": 1},
                    "min_items": {"type": "integer", "minimum": 1},
                },
            },
            input_requirements=["news_sentiment"],
            overlay_types=["sentiment"],
            warm_up_candles=lambda _params: 1,
            display_name="News Sentiment",
            description="Consumes a versioned sentiment window supplied in AnalysisContext.",
        )

    def requirements(self, _params: dict[str, object]) -> list[str]:
        return []

    def analyze(self, context: AnalysisContext) -> Signal:
        window = context.news_sentiment
        min_items = int(context.params.get("min_items", 3))
        legacy_threshold = float(context.params.get("threshold", 0.7))
        buy_above = float(context.params.get("buy_above", legacy_threshold))
        sell_below = float(context.params.get("sell_below", -legacy_threshold))
        if window is None or window.item_count < min_items:
            return Signal(
                action=ACTION_HOLD,
                evidence={
                    "reason": "insufficient_sentiment_data",
                    "item_count": 0 if window is None else window.item_count,
                },
            )
        price = context.candles.at(context.index).close
        evidence = {
            "avg_score": window.avg_score,
            "item_count": window.item_count,
            "model_version": window.model_version,
        }
        if window.avg_score > buy_above:
            return Signal(action=ACTION_BUY, price=price, confidence=abs(window.avg_score), evidence=evidence)
        if window.avg_score < sell_below:
            return Signal(action=ACTION_SELL, price=price, confidence=abs(window.avg_score), evidence=evidence)
        return Signal(action=ACTION_HOLD, evidence=evidence)
