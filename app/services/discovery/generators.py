"""Reusable deterministic candidate generators."""

from __future__ import annotations

import itertools
import json
import random
from collections.abc import Iterator
from typing import Any

from ...domain.common import hash_canonical_json


def _parameter_sets(parameters: dict[str, list[Any]]) -> Iterator[dict[str, Any]]:
    names = sorted(parameters)
    values = [parameters[name] for name in names]
    for combination in itertools.product(*values):
        yield dict(zip(names, combination, strict=True))


def _candidate(strategy_id: str, parameters: dict[str, Any]) -> dict[str, Any]:
    return _candidate_from_definition(
        {"strategy_id": strategy_id, "version": "v1", "parameters": parameters}
    )


def _candidate_from_definition(definition: dict[str, Any]) -> dict[str, Any]:
    return {
        "strategy_id": definition["strategy_id"],
        "strategy_version": definition.get("version", "v1"),
        "candidate_definition": definition,
        "candidate_hash": hash_canonical_json(definition),
        "generation_meta": {},
    }


def _parameter_variants(search_space: dict[str, Any], strategy_id: str) -> list[dict[str, Any]]:
    parameters = (search_space.get("parameter_grid") or {}).get(strategy_id) or {}
    return list(_parameter_sets(parameters)) if parameters else [{}]


def flat_leaves(definition: dict[str, Any]) -> list[dict[str, Any]]:
    if definition.get("strategy_id") == "composite":
        return [dict(leaf) for leaf in definition.get("children", [])]
    return [{**definition, "weight": 1.0}]


def composite_from_leaves(leaves: list[dict[str, Any]], policy: str = "weighted_vote") -> dict[str, Any]:
    if len(leaves) < 2:
        raise ValueError("composite needs at least two unique leaves")
    weight = 1.0 / len(leaves)
    return {
        "strategy_id": "composite",
        "version": "v1",
        "children": [{**leaf, "weight": weight} for leaf in leaves],
        "policy": {
            "name": policy,
            "threshold": 0.5,
            "encoding": {"BUY": 1, "HOLD": 0, "SELL": -1},
        },
    }


def _composite_candidate(child_specs: tuple[tuple[str, dict[str, Any]], ...], policy: str) -> dict[str, Any]:
    definition = composite_from_leaves(
        [{"strategy_id": strategy_id, "version": "v1", "parameters": parameters} for strategy_id, parameters in child_specs],
        policy,
    )
    return {
        "strategy_id": "composite",
        "strategy_version": "v1",
        "candidate_definition": definition,
        "candidate_hash": hash_canonical_json(definition),
        "generation_meta": {"cardinality": len(child_specs), "combination_policy": policy},
    }


def mutate_definition(
    source: dict[str, Any], search_space: dict[str, Any], randomizer: random.Random
) -> dict[str, Any]:
    definition = json.loads(json.dumps(source, sort_keys=True, allow_nan=False))
    leaves = definition.get("children") if definition.get("strategy_id") == "composite" else [definition]
    leaf = leaves[randomizer.randrange(len(leaves))]
    choices = (search_space.get("parameter_grid") or {}).get(leaf["strategy_id"], {})
    mutable = [(name, values) for name, values in choices.items() if values]
    if mutable:
        name, values = mutable[randomizer.randrange(len(mutable))]
        leaf.setdefault("parameters", {})[name] = values[randomizer.randrange(len(values))]
    return definition


def crossover_definition(
    first: dict[str, Any], second: dict[str, Any], randomizer: random.Random
) -> dict[str, Any]:
    left = json.loads(json.dumps(first, sort_keys=True, allow_nan=False))
    right = json.loads(json.dumps(second, sort_keys=True, allow_nan=False))
    if left.get("strategy_id") == right.get("strategy_id") and left.get("strategy_id") != "composite":
        for name, value in right.get("parameters", {}).items():
            if randomizer.random() < 0.5:
                left.setdefault("parameters", {})[name] = value
        return left
    leaves = flat_leaves(left) + flat_leaves(right)
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for leaf in leaves:
        unique.setdefault((leaf["strategy_id"], hash_canonical_json(leaf.get("parameters", {}))), leaf)
    return composite_from_leaves(list(unique.values())[:5])


def ensemble_definition(definitions: list[dict[str, Any]]) -> dict[str, Any]:
    leaves = [leaf for definition in definitions for leaf in flat_leaves(definition)]
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for leaf in leaves:
        unique.setdefault((leaf["strategy_id"], hash_canonical_json(leaf.get("parameters", {}))), leaf)
    return composite_from_leaves(list(unique.values())[:5])


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
                variant_sets = [[(strategy_id, params) for params in _parameter_variants(search_space, strategy_id)] for strategy_id in selected]
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
        random.Random(seed).shuffle(pool)
        return pool[:limit]


class DomainGuidedGenerator:
    generator_id = "domain_guided"
    generator_version = "v1"

    @staticmethod
    def _rules(candidate: dict[str, Any]) -> tuple[bool, list[str]]:
        applied: list[str] = []
        definition = candidate["candidate_definition"]
        for child in definition.get("children") or [definition]:
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
                applied.append("bollinger_positive_deviation")
                if float(params.get("deviation", 2)) <= 0:
                    return False, applied
        return True, applied or ["schema_valid"]

    def generate(self, search_space: dict[str, Any], limit: int, seed: int) -> list[dict[str, Any]]:
        del seed
        output: list[dict[str, Any]] = []
        for candidate in GridGenerator().generate(search_space, max(limit * 50, 500), 0):
            valid, rules = self._rules(candidate)
            if valid:
                candidate["generation_meta"] = {"rule_ids": rules}
                output.append(candidate)
            if len(output) == limit:
                break
        return output


class GeneticGenerator:
    """Small bounded genetic search: crossover, then one legal mutation."""

    generator_id = "genetic"
    generator_version = "v1"

    def generate(self, search_space: dict[str, Any], limit: int, seed: int) -> list[dict[str, Any]]:
        pool = GridGenerator().generate(search_space, max(8, limit * 4), seed)
        if not pool:
            return []
        rng = random.Random(seed)
        output: list[dict[str, Any]] = []
        seen: set[str] = set()
        for _ in range(max(limit * 8, 8)):
            left, right = rng.choice(pool), rng.choice(pool)
            definition = self._crossover(left["candidate_definition"], right["candidate_definition"], rng)
            definition = self._mutate(definition, search_space, rng)
            candidate = _candidate_from_definition(definition)
            candidate["generation_meta"] = {"operation": "crossover_mutation", "generator_version": self.generator_version}
            if candidate["candidate_hash"] not in seen:
                seen.add(candidate["candidate_hash"])
                output.append(candidate)
            if len(output) >= limit:
                return output
        return output

    @staticmethod
    def _crossover(left: dict[str, Any], right: dict[str, Any], rng: random.Random) -> dict[str, Any]:
        return crossover_definition(left, right, rng)

    @staticmethod
    def _mutate(definition: dict[str, Any], search_space: dict[str, Any], rng: random.Random) -> dict[str, Any]:
        return mutate_definition(definition, search_space, rng)
