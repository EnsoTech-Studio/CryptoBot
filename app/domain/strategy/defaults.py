"""Canonical defaults for built-in strategy parameters.

Defaults are kept separate from the versioned strategy schema so adding
provenance for an existing strategy version does not mutate its immutable
database row.  The execution engine and API use this module when a caller
omits an optional parameter.
"""

from __future__ import annotations

from typing import Any


BUILTIN_DEFAULT_PARAMS: dict[tuple[str, str], dict[str, Any]] = {
    ("ma_cross", "v1"): {"fast": 20, "slow": 50},
    ("ema_cross", "v1"): {"fast": 20, "slow": 50},
    ("rsi", "v1"): {"period": 14, "oversold": 30.0, "overbought": 70.0},
    ("bollinger", "v1"): {"period": 20, "deviation": 2.0},
    ("macd", "v1"): {"fast": 12, "slow": 26, "signal": 9},
    ("smc", "v1"): {"swing_period": 20},
    ("support_resistance", "v1"): {"period": 20},
    ("news_sentiment", "v1"): {"buy_above": 0.7, "sell_below": -0.7, "min_items": 3},
}


def default_parameters(strategy_id: str, version: str = "v1") -> dict[str, Any]:
    """Return a copy so callers can safely merge explicit parameters."""

    return dict(BUILTIN_DEFAULT_PARAMS.get((strategy_id, version), {}))


def effective_parameters(
    strategy_id: str,
    version: str,
    parameters: dict[str, Any] | None = None,
    schema: dict[str, Any] | None = None,
    stored_defaults: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge built-in, schema/database and explicit values in precedence order."""

    result = default_parameters(strategy_id, version)
    if schema:
        for name, definition in (schema.get("properties") or {}).items():
            if isinstance(definition, dict) and "default" in definition:
                result.setdefault(name, definition["default"])
    result.update(stored_defaults or {})
    result.update(parameters or {})
    return result
