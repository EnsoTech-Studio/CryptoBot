"""Deterministic, replaceable candidate generators for search runs."""

from __future__ import annotations

import json
import random
from typing import Any

from ..domain.common import DomainError, hash_canonical_json
from ..domain.strategy.plugins import default_registry
from .discovery.generators import (
    DomainGuidedGenerator,
    GeneticGenerator,
    GridGenerator,
    RandomGenerator,
    crossover_definition,
    ensemble_definition,
    flat_leaves,
    mutate_definition,
)
from .discovery.llm import DiscoveryProposalError, validate_llm_proposal
from .discovery.selection import WEIGHTS, generator_probabilities, select_parents
from .discovery.validation import (
    discovery_assessment as _discovery_assessment,
    discovery_complexity as _discovery_complexity,
    discovery_split as _discovery_split,
)

discovery_assessment = _discovery_assessment
discovery_complexity = _discovery_complexity
discovery_split = _discovery_split


_GENERATORS = {
    "grid": GridGenerator,
    "random": RandomGenerator,
    "random_search": RandomGenerator,
    "domain_guided": DomainGuidedGenerator,
    "genetic": GeneticGenerator,
}


# Discovery reuses the persisted search-candidate shape.  Lineage and
# assessment facts live in ``generation_meta``; this keeps existing search
# queue admission and experiment snapshots as their single owners.
_DISCOVERY_WEIGHTS = WEIGHTS


def discovery_generator_probabilities(
    terminal_trials: int,
    eligible: set[str],
    stats: dict[str, dict[str, int]] | None = None,
) -> dict[str, float]:
    return generator_probabilities(terminal_trials, eligible, stats)


def discovery_propose(
    search_space: dict[str, Any],
    seed: int,
    archive: list[dict[str, Any]],
    llm_propose: Any | None = None,
    research: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Propose one reproducible candidate from existing search-candidate records.

    ``None`` means no generator can produce an admissible proposal.  Callers
    archive that result instead of inserting a fake backtest trial.
    """
    randomizer = random.Random(seed)
    accepted = [
        item for item in archive if item.get("accepted") and item.get("candidate_definition")
    ]
    terminal = [item for item in archive if item.get("terminal", True)]
    eligible = {"random"}
    if accepted:
        eligible.add("mutation")
    if len(accepted) >= 2:
        eligible.update({"crossover", "ensemble"})
    if llm_propose is not None:
        eligible.add("llm")
    stats: dict[str, dict[str, int]] = {}
    for name in _DISCOVERY_WEIGHTS:
        rows = [item for item in terminal if item.get("generator") == name]
        stats[name] = {
            "terminal": len(rows),
            "accepted": sum(bool(item.get("accepted")) for item in rows),
        }
    probabilities = discovery_generator_probabilities(len(terminal), eligible, stats)
    point = randomizer.random()
    generator = next(iter(sorted(probabilities)))
    cumulative = 0.0
    for name in sorted(probabilities):
        cumulative += probabilities[name]
        if point < cumulative:
            generator = name
            break
    parent_pool = _discovery_parents(accepted, randomizer)
    if generator == "llm":
        proposal = llm_propose(search_space, archive, research or {}) if llm_propose else None
        if not isinstance(proposal, dict):
            return None
        try:
            validated = validate_llm_proposal(proposal, search_space, archive)
        except DiscoveryProposalError:
            raise
        except (TypeError, ValueError) as exc:
            raise DiscoveryProposalError("candidate response is invalid") from exc
        candidate = _discovery_candidate(
            validated["candidate_definition"],
            "llm",
            [],
            {key: proposal[key] for key in ("hypothesis", "operation", "provider", "model", "model_version", "prompt_version", "request_hash") if key in proposal},
        )
        return _admit_discovery_proposal(candidate, archive)
    if generator == "random":
        candidates = RandomGenerator().generate(search_space, 1, seed)
        candidate = (
            _discovery_candidate(candidates[0]["candidate_definition"], "random", [])
            if candidates
            else None
        )
        return _admit_discovery_proposal(candidate, archive)
    if generator == "mutation":
        parent = parent_pool[0]
        definition = mutate_definition(parent["candidate_definition"], search_space, randomizer)
        return _admit_discovery_proposal(
            _discovery_candidate(definition, "mutation", [parent]), archive
        )
    if generator == "crossover":
        first, second = parent_pool[:2]
        definition = crossover_definition(
            first["candidate_definition"], second["candidate_definition"], randomizer
        )
        return _admit_discovery_proposal(
            _discovery_candidate(definition, "crossover", [first, second]), archive
        )
    parents = parent_pool[: min(5, max(2, len(parent_pool)))]
    definition = ensemble_definition([parent["candidate_definition"] for parent in parents])
    return _admit_discovery_proposal(_discovery_candidate(definition, "ensemble", parents), archive)


def _discovery_parents(
    accepted: list[dict[str, Any]], randomizer: random.Random
) -> list[dict[str, Any]]:
    return select_parents(accepted, randomizer)


def _discovery_candidate(
    definition: dict[str, Any],
    generator: str,
    parents: list[dict[str, Any]],
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    definition = json.loads(json.dumps(definition, sort_keys=True, allow_nan=False))
    parent_ids = [str(parent["id"]) for parent in parents if parent.get("id") is not None]
    return {
        "strategy_id": definition["strategy_id"],
        "strategy_version": definition.get("version", "v1"),
        "candidate_definition": definition,
        "candidate_hash": hash_canonical_json(definition),
        "generation_meta": {
            "generator": generator,
            "parent_ids": parent_ids,
            "generation": 0
            if not parents
            else max(int(parent.get("generation", 0)) for parent in parents) + 1,
            **(extra_meta or {}),
        },
    }


def _admit_discovery_proposal(
    candidate: dict[str, Any] | None, archive: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Reject duplicate or invalid candidates before queue admission."""
    if candidate is None:
        return None
    if candidate["candidate_hash"] in {item.get("candidate_hash") for item in archive}:
        return None
    leaves = flat_leaves(candidate["candidate_definition"])
    try:
        registry = default_registry()
        for leaf in leaves:
            registry.resolve(leaf["strategy_id"], leaf.get("version", "v1"))
    except (DomainError, KeyError):
        return None
    valid, _rules = DomainGuidedGenerator._rules(candidate)
    return candidate if valid else None


def generate_candidates(
    generator_id: str, search_space: dict[str, Any], limit: int, seed: int
) -> list[dict[str, Any]]:
    try:
        generator = _GENERATORS[generator_id]()
    except KeyError as exc:
        raise ValueError(f"unknown candidate generator {generator_id!r}") from exc
    return generator.generate(search_space, limit, seed)
