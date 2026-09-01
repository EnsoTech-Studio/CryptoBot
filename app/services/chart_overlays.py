"""Backend-only chart overlays from the canonical strategy runtime."""

from __future__ import annotations

from typing import Any

from ..domain.common import ACTION_BUY, ACTION_SELL
from ..domain.indicator import DeterministicLibrary, IndicatorView, parse_requirement
from ..domain.market import Candle, CausalCandles
from ..domain.strategy import AnalysisContext
from ..domain.strategy.plugins import default_registry
from .backtest_engine import DeterministicEngine


def build_chart_overlays(
    candles: list[Candle], strategy_id: str, version: str, params: dict[str, Any] | None = None
) -> dict[str, list[dict[str, Any]]]:
    """Return indicator lines and closed-candle signals for one strategy."""
    strategy = default_registry().resolve(strategy_id, version)
    values = dict(params or {})
    requirements = DeterministicEngine._safe_requirements(strategy, values)
    warm_up = DeterministicEngine._safe_warm_up(strategy, values)
    indicators = DeterministicLibrary().precompute([candle.close for candle in candles], requirements)
    return {
        "series": _series(indicators, candles),
        "markers": _markers(strategy, values, indicators, candles, warm_up),
    }


def build_chart_overlay_delta(
    candles: list[Candle], strategy_id: str, version: str, params: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Return the latest overlay values for a closed-candle websocket update."""
    if not candles:
        return {"revised_from": None, "series": [], "markers": []}
    timestamp = candles[-1].open_time.isoformat()
    payload = build_chart_overlays(candles, strategy_id, version, params)
    series = []
    for item in payload["series"]:
        delta = dict(item)
        if points := item.get("points"):
            delta["points"] = [point for point in points if point["t"] == timestamp]
        if band := item.get("band"):
            delta["band"] = {
                name: [point for point in points if point["t"] == timestamp]
                for name, points in band.items()
            }
        series.append(delta)
    return {
        "revised_from": timestamp,
        "series": series,
        "markers": [marker for marker in payload["markers"] if marker["t"] == timestamp],
    }


def _series(indicators: dict[str, list[float | None]], candles: list[Candle]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, list[dict[str, float | str | None]]]] = {}
    output: list[dict[str, Any]] = []
    for requirement, values in indicators.items():
        kind, _ = parse_requirement(requirement)
        points = [{"t": candle.open_time.isoformat(), "v": value} for candle, value in zip(candles, values, strict=True)]
        if kind.startswith("bollinger_"):
            group = grouped.setdefault("bollinger", {})
            group[kind.removeprefix("bollinger_")] = points
        elif kind in ("sma", "ema"):
            output.append({"name": requirement, "overlay_type": "moving_average", "pane": "main", "points": points})
        elif kind == "rsi":
            output.append({"name": requirement, "overlay_type": "rsi", "pane": "sub", "unit": "index", "scale": {"min": 0, "max": 100}, "points": points})
        elif kind.startswith("macd_"):
            output.append({"name": requirement, "overlay_type": kind, "pane": "sub", "points": points})
        else:
            output.append({"name": requirement, "overlay_type": kind, "pane": "main", "points": points})
    if bands := grouped.get("bollinger"):
        output.append({"name": "bollinger", "overlay_type": "bollinger_band", "pane": "main", "band": bands})
    return output


def _markers(
    strategy: Any,
    params: dict[str, Any],
    indicators: dict[str, list[float | None]],
    candles: list[Candle],
    warm_up: int,
) -> list[dict[str, Any]]:
    markers: list[dict[str, Any]] = []
    for index in range(warm_up, len(candles)):
        candle = candles[index]
        signal = strategy.analyze(
            AnalysisContext(
                provider=candle.provider,
                symbol=candle.symbol,
                timeframe=candle.timeframe,
                candles=CausalCandles(candles, index),
                index=index,
                indicators=IndicatorView(indicators, index),
                params=params,
            )
        )
        if signal.action not in (ACTION_BUY, ACTION_SELL):
            continue
        markers.append({
            "t": candle.open_time.isoformat(),
            "overlay_type": "buy_signal" if signal.action == ACTION_BUY else "sell_signal",
            "confidence": signal.confidence,
            "evidence": signal.evidence if isinstance(signal.evidence, dict) else None,
        })
    return markers
