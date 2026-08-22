"""Composite signal combination (stub).

Mirrors `server/internal/domain/strategy/composite/contract.go`.
"""

from __future__ import annotations

from typing import Protocol

from ..contract import CombinationPolicy, ResolvedSignal, Signal


class SignalCombiner(Protocol):
    def combine(self, children: list[ResolvedSignal], policy: CombinationPolicy) -> Signal: ...


class WeightedVoteCombiner:
    def combine(self, children: list[ResolvedSignal], policy: CombinationPolicy) -> Signal:
        raise NotImplementedError


class MajorityVoteCombiner:
    def combine(self, children: list[ResolvedSignal], policy: CombinationPolicy) -> Signal:
        raise NotImplementedError
