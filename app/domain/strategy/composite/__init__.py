"""Composite strategy (signal combination)."""

from .contract import MajorityVoteCombiner, SignalCombiner, WeightedVoteCombiner

__all__ = ["MajorityVoteCombiner", "SignalCombiner", "WeightedVoteCombiner"]
