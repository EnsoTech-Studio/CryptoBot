"""Safe interpreter for approved declarative StrategySpec values."""

from __future__ import annotations

from typing import Any

from ..common import ACTION_BUY, ACTION_HOLD, ACTION_SELL
from ..indicator import parse_requirement
from .contract import AnalysisContext, Definition, Signal


class DeclarativeStrategy:
    def __init__(self, spec: dict[str, Any]) -> None:
        self._spec = spec
        self._refs: dict[str, str] = {}
        self._requirements: list[str] = []
        for item in spec.get("indicators", []):
            self._bind_indicator(item)

    def definition(self) -> Definition:
        return Definition(
            strategy_id=self._spec["strategy_id"],
            version="v1",
            family=self._spec["family"],
            parameters_schema=self._spec.get("parameters", {}),
            input_requirements=self._requirements,
            overlay_types=[],
            warm_up_candles=lambda _params: int(self._spec["warmup_bars"]),
            display_name=self._spec["display_name"],
            description=self._spec["description"],
        )

    def requirements(self, _params: dict[str, Any]) -> list[str]:
        return list(self._requirements)

    def analyze(self, context: AnalysisContext) -> Signal:
        rules = self._spec["rules"]
        price = context.candles.at(context.index).close
        if self._matches(rules["long_entry"], context):
            return Signal(action=ACTION_BUY, price=price)
        if self._matches(rules["short_entry"], context):
            return Signal(action=ACTION_SELL, price=price)
        return Signal(action=ACTION_HOLD)

    def _bind_indicator(self, item: dict[str, Any]) -> None:
        kind = str(item["kind"]).lower()
        name = str(item.get("id", kind))
        period = _period(item.get("period", 14), self._spec.get("parameters", {}))
        if kind in {"sma", "ema", "rsi"}:
            requirement = f"{kind}:{period}"
            self._refs[name] = requirement
        elif kind == "support_resistance":
            support, resistance = f"support:{period}", f"resistance:{period}"
            self._refs[name + ".support"] = support
            self._refs[name + ".resistance"] = resistance
            requirement = support
            self._requirements.append(resistance)
        elif kind == "bollinger":
            deviation = float(_period(item.get("deviation", 2), self._spec.get("parameters", {})))
            suffix = f"{period}:{deviation:g}"
            lower, middle, upper = (
                f"bollinger_lower:{suffix}", f"bollinger_middle:{suffix}", f"bollinger_upper:{suffix}"
            )
            self._refs[name + ".lower"] = lower
            self._refs[name + ".middle"] = middle
            self._refs[name + ".upper"] = upper
            band = str(item.get("band", "middle")).lower()
            self._refs[name] = {"lower": lower, "middle": middle, "upper": upper}.get(band, middle)
            requirement = upper
            self._requirements.extend([lower, middle])
        elif kind == "macd":
            fast = _period(item.get("fast", 12), self._spec.get("parameters", {}))
            slow = _period(item.get("slow", 26), self._spec.get("parameters", {}))
            signal = _period(item.get("signal", 9), self._spec.get("parameters", {}))
            requirement = f"macd_line:{fast}:{slow}:{signal}"
            self._refs[name + ".signal"] = f"macd_signal:{fast}:{slow}:{signal}"
            self._refs[name + ".hist"] = f"macd_hist:{fast}:{slow}:{signal}"
        else:  # validate_spec normally catches this before runtime.
            raise ValueError(f"unsupported indicator {kind}")
        self._refs.setdefault(name, requirement)
        self._requirements.append(requirement)

    def _matches(self, rule: Any, context: AnalysisContext) -> bool:
        if isinstance(rule, list):
            return all(self._matches(item, context) for item in rule)
        if not isinstance(rule, dict):
            return False
        op = rule.get("op")
        if op in {"and", "all"}:
            return all(self._matches(item, context) for item in rule.get("items", []))
        if op in {"or", "any"}:
            return any(self._matches(item, context) for item in rule.get("items", []))
        left = self._value(rule.get("left"), context)
        right = self._value(rule.get("right"), context)
        previous_left = self._value(rule.get("left"), context, context.index - 1)
        previous_right = self._value(rule.get("right"), context, context.index - 1)
        if None in (left, right):
            return False
        if op == "crosses_above":
            return previous_left is not None and previous_right is not None and left > right and previous_left <= previous_right
        if op == "crosses_below":
            return previous_left is not None and previous_right is not None and left < right and previous_left >= previous_right
        if op == "above":
            return left > right
        if op == "below":
            return left < right
        if op == "equals":
            return left == right
        return False

    def _value(self, ref: Any, context: AnalysisContext, index: int | None = None) -> float | None:
        cursor = context.index if index is None else index
        if isinstance(ref, (int, float)):
            return float(ref)
        if ref == "close":
            return float(context.candles.at(cursor).close) if cursor >= 0 else None
        if not isinstance(ref, str):
            return None
        requirement = self._refs.get(ref, ref)
        try:
            parse_requirement(requirement)
            return context.indicators.at(requirement, cursor)
        except Exception:
            return None


def _period(value: Any, parameters: dict[str, Any]) -> int:
    if isinstance(value, str) and value.startswith("$"):
        field = parameters.get(value[1:], {})
        value = field.get("default", 14) if isinstance(field, dict) else 14
    period = int(value)
    if period < 1:
        raise ValueError("indicator period must be positive")
    return period
