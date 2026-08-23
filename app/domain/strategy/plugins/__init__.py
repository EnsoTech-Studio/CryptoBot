"""Strategy plugins (MA, RSI, Bollinger, S/R, sentiment)."""

from .catalog import MovingAverageCross, default_registry, register_all

__all__ = ["MovingAverageCross", "default_registry", "register_all"]
