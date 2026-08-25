"""Deterministic, replaceable candidate generators for search runs."""

from __future__ import annotations

import itertools
import random
from collections.abc import Iterator
from typing import Any

from ..domain.common import hash_canonical_json


def _parameter_sets(parameters: dict[str, list[Any]]) -> Iterator[dict[str, Any]]:
    names = sorted(parameters)
    values = [parameters[name] for name in names]
    for combination in itertools.product(*values):
        yield dict(zip(names, combination, strict=True))


def _candidate(strategy_id: str, parameters: dict[str, Any]) -> dict[str, Any]:
    definition = {
        "strategy_id": strategy_id,
        "version": "v1",
        "parameters": parameters,
    }
    return {
        "strategy_id": strategy_id,
        "strategy_version": "v1",
        "candidate_definition": definition,
        "candidate_hash": hash_canonical_json(definition),
        "generation_meta": {},
    }


def _parameter_variants(
    search_space: dict[str, Any], strategy_id: str
) -> list[dict[str, Any]]:
    parameters = (search_space.get("parameter_grid") or {}).get(strategy_id) or {}
    return list(_parameter_sets(parameters)) if parameters else [{}]


def _composite_candidate(
    child_specs: tuple[tuple[str, dict[str, Any]], ...], policy: str
) -> dict[str, Any]:
    definition = {
        "strategy_id": "composite",
        "version": "v1",
        "children": [
            {
                "strategy_id": strategy_id,
                "version": "v1",
                "parameters": parameters,
                "weight": 1.0,
            }
            for strategy_id, parameters in child_specs
        ],
        "policy": {
            "name": policy,
            "threshold": 0.5,
            "encoding": {"BUY": 1, "HOLD": 0, "SELL": -1},
        },
    }
    return {
        "strategy_id": "composite",
        "strategy_version": "v1",
        "candidate_definition": definition,
        "candidate_hash": hash_canonical_json(definition),
        "generation_meta": {
            "cardinality": len(child_specs),
            "combination_policy": policy,
        },
    }


class GridGenerator:
    generator_id = "grid"
    generator_version = "v1"

    def generate(self, search_space: dict[str, Any], limit: int, seed: int) -> list[dict[str, Any]]:
        del seed
        strategy_ids = sorted(set(search_space.get("strategy_ids") or []))
        cardinalities = sorted(set(search_space.get("cardinality") or [1]))
        policies = sorted(set(search_space.get("policies") or ["weighted_vote"]))
        output: list[dict[str, Any]] = []
        for cardinality in cardinalities:
            if cardinality < 1 or cardinality > len(strategy_ids):
                continue
            if cardinality == 1:
                for strategy_id in strategy_ids:
                    for parameter_set in _parameter_variants(search_space, strategy_id):
                        output.append(_candidate(strategy_id, parameter_set))
                        if len(output) >= limit:
                            return output
                continue
            for selected in itertools.combinations(strategy_ids, cardinality):
                variant_sets = [
                    [(strategy_id, params) for params in _parameter_variants(search_space, strategy_id)]
                    for strategy_id in selected
                ]
                for child_specs in itertools.product(*variant_sets):
                    for policy in policies:
                        output.append(_composite_candidate(child_specs, policy))
                        if len(output) >= limit:
                            return output
        return output


class RandomGenerator:
    generator_id = "random_search"
    generator_version = "v1"

    def generate(self, search_space: dict[str, Any], limit: int, seed: int) -> list[dict[str, Any]]:
        pool = GridGenerator().generate(search_space, max(limit * 20, limit), seed)
        randomizer = random.Random(seed)
        randomizer.shuffle(pool)
        return pool[:limit]


class DomainGuidedGenerator:
    generator_id = "domain_guided"
    generator_version = "v1"

    @staticmethod
    def _rules(candidate: dict[str, Any]) -> tuple[bool, list[str]]:
        applied: list[str] = []
        definition = candidate["candidate_definition"]
        definitions = definition.get("children") or [definition]
        for child in definitions:
            strategy_id = child["strategy_id"]
            params = child.get("parameters") or {}
            if strategy_id in {"ma_cross", "ema_cross", "macd"}:
                fast = params.get("fast", params.get("fast_period"))
                slow = params.get("slow", params.get("slow_period"))
                if fast is not None and slow is not None:
                    applied.append("fast_lt_slow")
                    if int(fast) >= int(slow):
                        return False, applied
            if strategy_id == "rsi":
                buy = params.get("buy_below", params.get("buy_threshold"))
                sell = params.get("sell_above", params.get("sell_threshold"))
                if buy is not None and sell is not None:
                    applied.append("rsi_buy_lt_sell")
                    if float(buy) >= float(sell):
                        return False, applied
            if strategy_id == "bollinger":
                applied.append("bollinger_positive_stddev")
                if float(params.get("stddev", 2)) <= 0:
                    return False, applied
        return True, applied or ["schema_valid"]

    def generate(self, search_space: dict[str, Any], limit: int, seed: int) -> list[dict[str, Any]]:
        del seed
        output: list[dict[str, Any]] = []
        # The grid iterator is deterministic; domain rules only remove invalid
        # regions and record the rules used in candidate provenance.
        for candidate in GridGenerator().generate(search_space, max(limit * 50, 500), 0):
            valid, rules = self._rules(candidate)
            if not valid:
                continue
            candidate["generation_meta"] = {"rule_ids": rules}
            output.append(candidate)
            if len(output) == limit:
                break
        return output


_GENERATORS = {
    "grid": GridGenerator,
    "random": RandomGenerator,
    "random_search": RandomGenerator,
    "domain_guided": DomainGuidedGenerator,
}


def generate_candidates(
    generator_id: str, search_space: dict[str, Any], limit: int, seed: int
) -> list[dict[str, Any]]:
    try:
        generator = _GENERATORS[generator_id]()
    except KeyError as exc:
        raise ValueError(f"unknown candidate generator {generator_id!r}") from exc
    return generator.generate(search_space, limit, seed)
