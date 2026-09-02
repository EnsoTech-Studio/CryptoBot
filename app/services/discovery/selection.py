"""Generator and parent selection policy."""

from __future__ import annotations

import random
from typing import Any


WEIGHTS = {"random": 0.35, "mutation": 0.30, "crossover": 0.15, "ensemble": 0.10, "llm": 0.10}


def generator_probabilities(
    terminal_trials: int,
    eligible: set[str],
    stats: dict[str, dict[str, int]] | None = None,
) -> dict[str, float]:
    usable = sorted(set(WEIGHTS) & eligible)
    if not usable:
        raise ValueError("no eligible discovery generator")
    if terminal_trials < 20:
        total = sum(WEIGHTS[name] for name in usable)
        return {name: WEIGHTS[name] / total for name in usable}
    stats = stats or {}
    floor = 0.05
    remaining = 1.0 - floor * len(usable)
    weights = {
        name: 0.1 + int(stats.get(name, {}).get("accepted", 0)) / max(1, int(stats.get(name, {}).get("terminal", 0)))
        for name in usable
    }
    total = sum(weights.values())
    return {name: floor + remaining * weights[name] / total for name in usable}


def select_parents(accepted: list[dict[str, Any]], randomizer: random.Random) -> list[dict[str, Any]]:
    ranked = sorted(accepted, key=lambda item: (-float(item.get("score", 0)), str(item.get("id", ""))))
    top = ranked[: max(1, (len(ranked) + 4) // 5)]
    shuffled: list[dict[str, Any]] = []
    remaining = list(ranked)
    while remaining:
        source = top if randomizer.random() < 0.8 and top else remaining
        parent = source[randomizer.randrange(len(source))]
        shuffled.append(parent)
        remaining.remove(parent)
        top = [item for item in top if item in remaining]
    return shuffled
