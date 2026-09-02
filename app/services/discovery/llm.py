"""Validation for model-authored candidates before queue admission."""

from __future__ import annotations

import json
import math
from typing import Any

from ...domain.common import DomainError, hash_canonical_json
from ...domain.strategy.plugins import default_registry
from .generators import DomainGuidedGenerator, flat_leaves


class DiscoveryProposalError(ValueError):
    """The model response is not an allowed catalog candidate."""


def validate_llm_proposal(
    proposal: dict[str, Any],
    search_space: dict[str, Any],
    archive: list[dict[str, Any]],
    catalog: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate strict model output and return a canonical candidate envelope.

    The model can choose catalog leaves and parameters only. It cannot create
    executable code, nested composites, test-aware rules, or a duplicate hash.
    """
    definition = proposal.get("candidate_definition") or proposal.get("candidate")
    if not isinstance(definition, dict):
        raise DiscoveryProposalError("candidate_definition is required")
    definition = json.loads(json.dumps(definition, sort_keys=True, allow_nan=False))
    allowed = set(search_space.get("strategy_ids") or [])
    if definition.get("strategy_id") == "composite":
        children = definition.get("children")
        if not isinstance(children, list) or not 2 <= len(children) <= 5:
            raise DiscoveryProposalError("composite must contain 2..5 leaves")
        if not all(isinstance(leaf, dict) for leaf in children):
            raise DiscoveryProposalError("composite leaves must be objects")
        if len({(leaf.get("strategy_id"), hash_canonical_json(leaf.get("parameters", {}))) for leaf in children}) != len(children):
            raise DiscoveryProposalError("composite leaves must be unique")
        policy = definition.get("policy")
        if not isinstance(policy, dict) or policy.get("name") not in (search_space.get("policies") or ["weighted_vote"]):
            raise DiscoveryProposalError("composite policy is not allowed")
        weights = [leaf.get("weight") for leaf in children]
        if any(not isinstance(weight, (int, float)) or isinstance(weight, bool) or not math.isfinite(float(weight)) or float(weight) < 0 for weight in weights):
            raise DiscoveryProposalError("composite weights must be finite and non-negative")
        total = sum(float(weight) for weight in weights)
        if total <= 0:
            raise DiscoveryProposalError("composite weights must have a positive total")
        for leaf in children:
            leaf["weight"] = float(leaf["weight"]) / total
    elif definition.get("strategy_id") not in allowed:
        raise DiscoveryProposalError("strategy is outside the selected catalog")
    leaves = flat_leaves(definition)
    for leaf in leaves:
        _validate_leaf(leaf, allowed, search_space, catalog or {})
    valid, _rules = DomainGuidedGenerator._rules({"candidate_definition": definition})
    if not valid:
        raise DiscoveryProposalError("candidate violates domain parameter rules")
    candidate_hash = hash_canonical_json(definition)
    if candidate_hash in {item.get("candidate_hash") for item in archive}:
        raise DiscoveryProposalError("candidate duplicates an archived hash")
    return {"candidate_definition": definition, "candidate_hash": candidate_hash}


def _validate_leaf(
    leaf: dict[str, Any],
    allowed: set[str],
    search_space: dict[str, Any],
    catalog: dict[str, dict[str, Any]],
) -> None:
    strategy_id = leaf.get("strategy_id")
    if strategy_id not in allowed or leaf.get("version", "v1") != "v1":
        raise DiscoveryProposalError("leaf is outside the selected catalog")
    params = leaf.get("parameters") or {}
    if not isinstance(params, dict):
        raise DiscoveryProposalError("leaf parameters must be an object")
    try:
        definition = default_registry().resolve(strategy_id, "v1").definition()
    except (DomainError, KeyError) as exc:
        # Approved declarative strategies are persisted in the catalog but are
        # intentionally absent from the built-in Python registry.
        metadata = catalog.get(strategy_id)
        if metadata is None:
            raise DiscoveryProposalError("leaf is not registered") from exc
        schema = metadata.get("parameters_schema") or {}
        properties = schema.get("properties", schema) if isinstance(schema, dict) else {}
    else:
        properties = (definition.parameters_schema or {}).get("properties", {})
    if set(params) - set(properties):
        raise DiscoveryProposalError("leaf contains an unknown parameter")
    configured = (search_space.get("parameter_grid") or {}).get(strategy_id) or {}
    for name, value in params.items():
        schema = properties[name]
        if name in configured and configured[name] and value not in configured[name]:
            raise DiscoveryProposalError("leaf parameter is outside the configured search values")
        if schema.get("type") == "integer" and (isinstance(value, bool) or not isinstance(value, int)):
            raise DiscoveryProposalError("integer parameter has the wrong type")
        if schema.get("type") == "number" and (isinstance(value, bool) or not isinstance(value, (int, float))):
            raise DiscoveryProposalError("numeric parameter has the wrong type")
        number = float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None
        if number is not None:
            if number < float(schema.get("minimum", -math.inf)) or number <= float(schema.get("exclusiveMinimum", -math.inf)):
                raise DiscoveryProposalError("leaf parameter is below its minimum")
            if number > float(schema.get("maximum", math.inf)):
                raise DiscoveryProposalError("leaf parameter exceeds its maximum")
