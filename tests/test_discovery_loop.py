from decimal import Decimal

from app.services.search import (
    discovery_assessment,
    discovery_generator_probabilities,
    discovery_propose,
    discovery_split,
)

SPACE = {
    "strategy_ids": ["ma_cross", "rsi", "macd"],
    "parameter_grid": {
        "ma_cross": {"fast": [5, 10], "slow": [20, 30]},
        "rsi": {"period": [10, 14]},
        "macd": {"fast_period": [8, 12]},
    },
}


def test_discovery_split_is_contiguous_and_keeps_test_sealed() -> None:
    split = discovery_split(100)
    assert split == {
        "train": (0, 60),
        "validation_1": (60, 66),
        "validation_2": (66, 72),
        "validation_3": (72, 80),
        "test": (80, 100),
    }


def test_discovery_assessment_applies_gates_and_penalties() -> None:
    train = {"sharpe_ratio": 1.2, "trade_count": 12}
    validations = [
        {"sharpe_ratio": 1.0, "trade_count": 10, "max_drawdown_pct": -8},
        {"sharpe_ratio": 1.1, "trade_count": 10, "max_drawdown_pct": -10},
        {"sharpe_ratio": 1.2, "trade_count": 10, "max_drawdown_pct": -5},
    ]
    assessment = discovery_assessment(train, validations, 0.2, [0.94])
    assert assessment["accepted"] is True
    assert assessment["score"] > 0

    rejected = discovery_assessment({"sharpe_ratio": None, "trade_count": 12}, validations, 0.2)
    assert rejected == {"accepted": False, "rejection_reason": "cheap_filter"}


def test_demo_mode_admits_low_trade_candidate_with_explicit_override() -> None:
    empty = {"sharpe_ratio": None, "trade_count": 0, "total_return_pct": 0.0}
    assessment = discovery_assessment(empty, [empty, empty, empty], 0.2, demo_mode=True)
    assert assessment["accepted"] is True
    assert assessment["score"] == 0.0
    assert assessment["demo_override"] == "cheap_filter"


def test_demo_mode_accepts_database_decimal_metrics() -> None:
    empty = {"sharpe_ratio": None, "trade_count": 0, "total_return_pct": Decimal("0")}
    assessment = discovery_assessment(
        {"sharpe_ratio": Decimal("0.76"), "trade_count": 3, "total_return_pct": Decimal("0.19")},
        [empty, empty, empty],
        0.2,
        demo_mode=True,
    )
    assert assessment["accepted"] is True
    assert assessment["demo_override"] == "cheap_filter"


def test_discovery_generator_selection_and_lineage_are_seeded() -> None:
    weights = discovery_generator_probabilities(
        20, {"random", "mutation"}, {"random": {"terminal": 10, "accepted": 4}}
    )
    assert sum(weights.values()) == 1.0
    assert all(value >= 0.05 for value in weights.values())

    parent = {
        "id": "00000000-0000-0000-0000-000000000001",
        "candidate_definition": {
            "strategy_id": "ma_cross",
            "version": "v1",
            "parameters": {"fast": 5, "slow": 20},
        },
        "generator": "random",
        "generation": 0,
        "terminal": True,
        "accepted": True,
        "score": 1.0,
    }
    first = discovery_propose(SPACE, 9, [parent])
    second = discovery_propose(SPACE, 9, [parent])
    assert first == second
    assert first is not None
    assert first["generation_meta"]["generator"] in {"random", "mutation"}


def test_discovery_archives_duplicate_without_queue_candidate() -> None:
    first = discovery_propose(SPACE, 1, [])
    assert first is not None
    archive = [{**first, "terminal": True, "accepted": False}]
    assert discovery_propose(SPACE, 1, archive) is None
