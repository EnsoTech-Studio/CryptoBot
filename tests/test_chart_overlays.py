"""Chart overlays must use the same indicator library as strategy execution."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.domain.market import Candle
from app.services.chart_overlays import build_chart_overlay_delta, build_chart_overlays


def _candles() -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        Candle(
            provider="binance_usdm",
            symbol="ETHUSDT",
            timeframe="5m",
            open_time=start + timedelta(minutes=5 * index),
            close_time=start + timedelta(minutes=5 * (index + 1)),
            open=100 + index,
            high=101 + index,
            low=99 + index,
            close=100 + index,
            volume=1.0,
        )
        for index in range(6)
    ]


def test_ma_overlay_uses_the_canonical_indicator_series() -> None:
    payload = build_chart_overlays(_candles(), "ma_cross", "v1", {"fast": 2, "slow": 3})

    series = {item["name"]: item for item in payload["series"]}
    assert series["sma:2"] == {
        "name": "sma:2",
        "overlay_type": "moving_average",
        "pane": "main",
        "points": [
            {"t": "2026-01-01T00:00:00+00:00", "v": None},
            {"t": "2026-01-01T00:05:00+00:00", "v": 100.5},
            {"t": "2026-01-01T00:10:00+00:00", "v": 101.5},
            {"t": "2026-01-01T00:15:00+00:00", "v": 102.5},
            {"t": "2026-01-01T00:20:00+00:00", "v": 103.5},
            {"t": "2026-01-01T00:25:00+00:00", "v": 104.5},
        ],
    }
    assert series["sma:3"]["points"][2]["v"] == 101.0
    assert payload["markers"] == []


def test_overlay_delta_contains_only_the_latest_candle_values() -> None:
    payload = build_chart_overlay_delta(_candles(), "ma_cross", "v1", {"fast": 2, "slow": 3})

    assert payload["revised_from"] == "2026-01-01T00:25:00+00:00"
    assert all(len(item["points"]) == 1 for item in payload["series"])
    assert payload["series"][0]["points"] == [
        {"t": "2026-01-01T00:25:00+00:00", "v": 104.5}
    ]
    assert payload["markers"] == []
