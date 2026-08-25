from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import SearchRunCreateIn
from app.services.search import generate_candidates


SPACE = {
    "strategy_ids": ["ma_cross"],
    "parameter_grid": {
        "ma_cross": {
            "fast": [5, 10, 20],
            "slow": [10, 20],
        }
    },
}


def test_seeded_random_candidate_sequence_is_reproducible() -> None:
    first = generate_candidates("random_search", SPACE, 5, 42)
    second = generate_candidates("random_search", SPACE, 5, 42)
    assert [item["candidate_hash"] for item in first] == [
        item["candidate_hash"] for item in second
    ]
    assert len({item["candidate_hash"] for item in first}) == len(first)


def test_domain_guided_generator_filters_invalid_fast_slow_pairs() -> None:
    candidates = generate_candidates("domain_guided", SPACE, 10, 0)
    assert candidates
    for item in candidates:
        params = item["candidate_definition"]["parameters"]
        assert params["fast"] < params["slow"]
        assert "fast_lt_slow" in item["generation_meta"]["rule_ids"]


def test_generators_share_candidate_contract() -> None:
    for generator_id in ("grid", "random_search", "domain_guided"):
        candidate = generate_candidates(generator_id, SPACE, 1, 7)[0]
        assert set(candidate) >= {
            "strategy_id",
            "strategy_version",
            "candidate_definition",
            "candidate_hash",
            "generation_meta",
        }
        assert len(candidate["candidate_hash"]) == 64


def test_grid_generator_builds_composite_candidates_from_cardinality() -> None:
    candidates = generate_candidates(
        "grid",
        {
            "strategy_ids": ["ma_cross", "rsi", "macd"],
            "cardinality": [2],
            "policies": ["majority_vote", "weighted_vote"],
            "parameter_grid": {},
        },
        20,
        0,
    )
    assert len(candidates) == 6
    assert all(item["strategy_id"] == "composite" for item in candidates)
    assert all(len(item["candidate_definition"]["children"]) == 2 for item in candidates)
    assert {
        item["candidate_definition"]["policy"]["name"] for item in candidates
    } == {"majority_vote", "weighted_vote"}
    assert len({item["candidate_hash"] for item in candidates}) == len(candidates)


@pytest.mark.parametrize(
    "stop_conditions",
    [
        {},
        {"max_candidates": 0},
        {"max_candidates": 1.5},
        {"max_duration_sec": "10"},
        {"max_failure_rate": 1.1},
        {"unknown": 1},
    ],
)
def test_search_stop_conditions_reject_invalid_contracts(
    stop_conditions: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        SearchRunCreateIn.model_validate(
            {
                "owner_id": str(uuid4()),
                "generator_id": "grid",
                "search_space": {
                    "strategy_ids": ["ma_cross"],
                    "cardinality": [1],
                    "policies": ["weighted_vote"],
                    "parameter_grid": {},
                },
                "stop_conditions": stop_conditions,
                "dataset_version": "fixture-v1",
            }
        )


def test_failure_rate_is_a_valid_standalone_stop_condition() -> None:
    request = SearchRunCreateIn.model_validate(
        {
            "owner_id": str(uuid4()),
            "generator_id": "grid",
            "search_space": {
                "strategy_ids": ["ma_cross"],
                "cardinality": [1],
                "policies": ["weighted_vote"],
                "parameter_grid": {},
            },
            "stop_conditions": {"max_failure_rate": 0.3},
            "dataset_version": "fixture-v1",
        }
    )
    assert request.stop_conditions.max_failure_rate == 0.3
