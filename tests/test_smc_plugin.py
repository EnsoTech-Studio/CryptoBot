from datetime import UTC, datetime, timedelta

from app.domain.common import ACTION_BUY, ACTION_SELL
from app.domain.indicator import IndicatorView
from app.domain.market import Candle, CausalCandles
from app.domain.strategy import AnalysisContext
from app.domain.strategy.plugins import default_registry


def test_smc_market_structure_break_emits_only_causal_bos_signals() -> None:
    strategy = default_registry().resolve("smc", "v1")

    bullish = _context([95.0, 98.0, 110.0], support=90.0, resistance=100.0)
    bearish = _context([95.0, 92.0, 80.0], support=90.0, resistance=100.0)

    bullish_signal = strategy.analyze(bullish)
    bearish_signal = strategy.analyze(bearish)

    assert bullish_signal.action == ACTION_BUY
    assert bullish_signal.price == 110.0
    assert bullish_signal.evidence == {"structure": "bullish_bos", "level": 100.0}
    assert bearish_signal.action == ACTION_SELL
    assert bearish_signal.price == 80.0
    assert bearish_signal.evidence == {"structure": "bearish_bos", "level": 90.0}


def _context(closes: list[float], *, support: float, resistance: float) -> AnalysisContext:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = [
        Candle(
            provider="fixture",
            symbol="BTCUSDT",
            timeframe="5m",
            open_time=start + timedelta(minutes=index * 5),
            close_time=start + timedelta(minutes=(index + 1) * 5),
            open=close,
            high=close,
            low=close,
            close=close,
            volume=1.0,
        )
        for index, close in enumerate(closes)
    ]
    return AnalysisContext(
        provider="fixture",
        symbol="BTCUSDT",
        timeframe="5m",
        candles=CausalCandles(candles, len(candles) - 1),
        index=len(candles) - 1,
        indicators=IndicatorView(
            {
                "support:2": [None, support, support],
                "resistance:2": [None, resistance, resistance],
            },
            cursor=len(candles) - 1,
        ),
        params={"swing_period": 2},
    )
