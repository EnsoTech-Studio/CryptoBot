"""Composite signal combination.

Mirrors `server/internal/domain/strategy/composite/contract.go`. Combiners fold
child signals into one canonical signal per `specs/composite-strategy.md`. They
are pure: same children + same policy in, same signal out.

Weighted vote (`specs/composite-strategy.md` §Weighted vote):

- ``score = Σ(weight × encoding[action]) / Σ(weight)`` — normalized so
  unnormalized weights (2/3/5) give the same score as 0.2/0.3/0.5;
- strict comparison: ``score > threshold`` BUY, ``score < -threshold`` SELL,
  ``score == threshold`` is HOLD (AC-06);
- ``confidence = abs(score)``; ``evidence = {"score": score}``;
- price is the weighted price over non-HOLD children:
  ``Σ(weight × price) / Σ(weight)`` — a non-HOLD child without a positive
  price is a validation error, never silently dropped.

Majority vote is plurality: the action with the highest vote count wins,
including without more than half of the children; ties return HOLD
deterministically. ``confidence = votes / total``; ``evidence`` carries the
vote counts.
"""

from __future__ import annotations

from typing import Protocol

from ...common import (
    ACTION_BUY,
    ACTION_HOLD,
    ACTION_SELL,
    ERR_INVALID_SIGNAL,
    ERR_VALIDATION,
    Decimal,
    DomainError,
)
from ..contract import CombinationPolicy, ResolvedSignal, Signal


class SignalCombiner(Protocol):
    def combine(self, children: list[ResolvedSignal], policy: CombinationPolicy) -> Signal: ...

_ENCODING = {ACTION_BUY: 1, ACTION_HOLD: 0, ACTION_SELL: -1}


def _non_hold(children: list[ResolvedSignal]) -> list[ResolvedSignal]:
    """Validate that every non-HOLD child carries a positive price."""
    active = [c for c in children if c.signal.action != ACTION_HOLD]
    for child in active:
        price = child.signal.price
        if price is None or price <= 0:
            raise DomainError(
                ERR_INVALID_SIGNAL,
                f"child {child.strategy_id}@{child.version} is {child.signal.action} "
                "without a positive price",
            )
    return active


def _weighted_price(active: list[ResolvedSignal]) -> Decimal | None:
    if not active:
        return None
    total = sum(child.weight for child in active)
    if total <= 0:
        return active[0].signal.price  # all active weights zero: no weighting possible
    return sum(child.weight * child.signal.price for child in active) / total


class WeightedVoteCombiner:
    """Net weighted vote, normalized, against a strict symmetric threshold."""

    def combine(self, children: list[ResolvedSignal], policy: CombinationPolicy) -> Signal:
        score = 0.0
        total_weight = 0.0
        for child in children:
            if child.weight < 0:
                raise DomainError(ERR_VALIDATION, "child weight must be >= 0")
            total_weight += child.weight
            score += child.weight * _ENCODING[child.signal.action]
        if total_weight <= 0:
            raise DomainError(ERR_VALIDATION, "total weight must be > 0")
        score /= total_weight
        active = _non_hold(children)
        action = ACTION_HOLD
        if score > policy.threshold:
            action = ACTION_BUY
        elif score < -policy.threshold:
            action = ACTION_SELL
        price = _weighted_price(active) if action != ACTION_HOLD else None
        return Signal(
            action=action,
            confidence=abs(score),
            price=price,
            evidence={"score": score},
        )


class MajorityVoteCombiner:
    """Plurality vote: highest count wins, ties HOLD, confidence = votes/total."""

    def combine(self, children: list[ResolvedSignal], policy: CombinationPolicy) -> Signal:
        counts = {ACTION_BUY: 0, ACTION_SELL: 0, ACTION_HOLD: 0}
        for child in children:
            if child.signal.action not in counts:
                raise DomainError(ERR_VALIDATION, f"unknown action {child.signal.action!r}")
            counts[child.signal.action] += 1
        best = max(counts, key=lambda a: counts[a])
        tied = sum(1 for count in counts.values() if count == counts[best]) > 1
        active = _non_hold(children)
        if tied or best == ACTION_HOLD or not active:
            return Signal(action=ACTION_HOLD, evidence={"votes": counts})
        first = active[0].signal
        return Signal(
            action=best,
            confidence=counts[best] / len(children),
            price=first.price,
            evidence={"votes": counts},
        )
