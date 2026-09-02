from datetime import UTC, datetime

from app.infrastructure.dataset import load_fixture_dataset


def test_fixture_ohlcv_is_aggregated_to_requested_timeframe(tmp_path) -> None:
    (tmp_path / "ohlcv.csv").write_text(
        "T,O,H,L,C,V\n"
        "1772582640000,100,101,99,100.5,1\n"
        "1772582700000,100.5,102,100,101.5,2\n"
        "1772582760000,101.5,103,101,102.5,3\n"
        "1772586240000,102.5,104,102,103.5,4\n",
        encoding="utf-8",
    )
    (tmp_path / "bbo.csv").write_text("b,a,T\n100,101,1772582640000\n", encoding="utf-8")

    candles, _, info = load_fixture_dataset(
        tmp_path, provider="binance", symbol="SOLUSDT", timeframe="1h"
    )

    assert len(candles) == 2
    assert candles[0].open_time == datetime(2026, 3, 4, 0, 0, tzinfo=UTC)
    assert candles[0].close_time == datetime(2026, 3, 4, 0, 59, 59, 999000, tzinfo=UTC)
    assert (candles[0].open, candles[0].high, candles[0].low, candles[0].close) == (
        100.0,
        103.0,
        99.0,
        102.5,
    )
    assert candles[0].volume == 6.0
    assert candles[1].open_time == datetime(2026, 3, 4, 1, 0, tzinfo=UTC)
    assert info.candle_count == 2
