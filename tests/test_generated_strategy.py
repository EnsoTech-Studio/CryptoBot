from datetime import UTC, datetime, timedelta

from app.domain.common import ACTION_BUY
from app.domain.indicator import IndicatorView
from app.domain.market import Candle, CausalCandles
from app.domain.strategy import AnalysisContext, DeclarativeStrategy


def test_approved_declarative_spec_uses_causal_indicator_values():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = [
        Candle("fixture", "BTCUSDT", "5m", start + timedelta(minutes=i), start + timedelta(minutes=i + 1), 1, 1, 1, i + 1, 1)
        for i in range(3)
    ]
    spec = {
        "strategy_id": "generated.ma-cross-test",
        "display_name": "MA Cross",
        "family": "trend",
        "description": "A causal moving-average crossover.",
        "parameters": {},
        "indicators": [
            {"id": "fast", "kind": "sma", "period": 2},
            {"id": "slow", "kind": "sma", "period": 3},
        ],
        "rules": {
            "long_entry": {"op": "crosses_above", "left": "fast", "right": "slow"},
            "short_entry": {"op": "crosses_below", "left": "fast", "right": "slow"},
            "exit": {"op": "opposite_signal"},
        },
        "warmup_bars": 2,
    }
    strategy = DeclarativeStrategy(spec)
    context = AnalysisContext(
        provider="fixture",
        symbol="BTCUSDT",
        timeframe="5m",
        candles=CausalCandles(candles, 2),
        index=2,
        indicators=IndicatorView({"sma:2": [1.0, 1.5, 3.0], "sma:3": [2.0, 2.0, 2.0]}, 2),
    )
    assert strategy.analyze(context).action == ACTION_BUY
