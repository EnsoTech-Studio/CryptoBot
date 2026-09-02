import os
from pathlib import Path
from uuid import uuid4

import pytest

from app.services.artifact_store import persist_generated_artifact
from app.services.discovery.llm import DiscoveryProposalError, validate_llm_proposal
from app.services.search import generate_candidates


SPACE = {
    "strategy_ids": ["ma_cross", "rsi", "macd"],
    "cardinality": [1, 2],
    "policies": ["weighted_vote"],
    "parameter_grid": {
        "ma_cross": {"fast": [5, 10], "slow": [20, 30]},
        "rsi": {"period": [10, 14]},
        "macd": {"fast": [8, 12], "slow": [20, 30], "signal": [5, 9]},
    },
}


def test_genetic_generation_is_seeded_and_bounded() -> None:
    first = generate_candidates("genetic", SPACE, 5, 23)
    second = generate_candidates("genetic", SPACE, 5, 23)

    assert first
    assert len(first) <= 5
    assert [item["candidate_hash"] for item in first] == [item["candidate_hash"] for item in second]
    assert all(item["generation_meta"]["operation"] == "crossover_mutation" for item in first)


def test_weighted_composite_generation_normalizes_children() -> None:
    candidates = generate_candidates("grid", SPACE, 100, 0)
    composites = [item for item in candidates if item["strategy_id"] == "composite"]

    assert composites
    for candidate in composites:
        children = candidate["candidate_definition"]["children"]
        assert 2 <= len(children) <= 5
        assert sum(child["weight"] for child in children) == pytest.approx(1.0)
        assert candidate["candidate_definition"]["policy"]["name"] == "weighted_vote"


def test_llm_proposal_is_catalog_bound_and_weight_normalized() -> None:
    proposal = {
        "candidate_definition": {
            "strategy_id": "composite",
            "version": "v1",
            "children": [
                {"strategy_id": "ma_cross", "version": "v1", "parameters": {"fast": 5, "slow": 20}, "weight": 3},
                {"strategy_id": "rsi", "version": "v1", "parameters": {"period": 14}, "weight": 2},
            ],
            "policy": {"name": "weighted_vote", "threshold": 0.5},
        }
    }

    result = validate_llm_proposal(proposal, SPACE, [])

    children = result["candidate_definition"]["children"]
    assert [child["weight"] for child in children] == pytest.approx([0.6, 0.4])
    assert len(result["candidate_hash"]) == 64


@pytest.mark.parametrize(
    "definition, error",
    [
        (
            {"strategy_id": "ma_cross", "version": "v1", "parameters": {"fast": 5, "unknown": 20}},
            "unknown parameter",
        ),
        (
            {
                "strategy_id": "composite",
                "version": "v1",
                "children": [
                    {"strategy_id": "ma_cross", "version": "v1", "parameters": {"fast": 5, "slow": 20}, "weight": 1},
                    {"strategy_id": "ma_cross", "version": "v1", "parameters": {"fast": 5, "slow": 20}, "weight": 1},
                ],
                "policy": {"name": "weighted_vote"},
            },
            "unique",
        ),
        (
            {
                "strategy_id": "composite",
                "version": "v1",
                "children": ["not-a-leaf", {"strategy_id": "rsi", "parameters": {"period": 14}, "weight": 1}],
                "policy": {"name": "weighted_vote"},
            },
            "objects",
        ),
    ],
)
def test_llm_proposal_rejects_unsafe_or_duplicate_shapes(definition: dict, error: str) -> None:
    with pytest.raises(DiscoveryProposalError, match=error):
        validate_llm_proposal({"candidate_definition": definition}, SPACE, [])


def test_generated_artifact_stays_outside_source_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "generated"
    monkeypatch.setenv("GENERATED_STRATEGY_DIR", str(root))
    draft_id = uuid4()

    path = persist_generated_artifact(draft_id, 1, "STRATEGY_SPEC = {'strategy_id': 'generated.demo'}\n")

    assert path == root / str(draft_id) / "revision-1.py"
    assert path.read_text(encoding="utf-8").startswith("STRATEGY_SPEC")
    assert os.stat(path).st_mode & 0o777 == 0o600
    assert not (Path.cwd() / "src" / "generated.demo.py").exists()
