from __future__ import annotations

from app.domain.indicator import DeterministicLibrary
from app.domain.strategy.plugins import default_registry
from app.services.ranking import ScoreRanker
from app.services.search import generate_candidates


def test_indicator_library_supports_blueprint_catalog() -> None:
    closes = [100.0 + ((index % 7) - 3) for index in range(80)]
    requirements = [
        "sma:10",
        "ema:10",
        "rsi:14",
        "bollinger_upper:20:2",
        "bollinger_middle:20:2",
        "bollinger_lower:20:2",
        "support:20",
        "resistance:20",
        "macd_line:12:26:9",
        "macd_signal:12:26:9",
        "macd_hist:12:26:9",
    ]
    result = DeterministicLibrary().precompute(closes, requirements)
    assert set(result) == set(requirements)
    assert all(len(values) == len(closes) for values in result.values())
    assert result["rsi:14"][-1] is not None
    assert result["macd_signal:12:26:9"][-1] is not None


def test_registry_contains_all_required_and_demo_plugins() -> None:
    strategy_ids = {item.strategy_id for item in default_registry().list()}
    assert {
        "ma_cross",
        "rsi",
        "bollinger",
        "support_resistance",
        "news_sentiment",
        "macd",
        "composite",
    } <= strategy_ids


def test_generators_share_the_same_candidate_contract() -> None:
    space = {
        "strategy_ids": ["ma_cross"],
        "parameter_grid": {"ma_cross": {"fast": [3, 5], "slow": [10, 20]}},
    }
    grid = generate_candidates("grid", space, 3, 7)
    random = generate_candidates("random", space, 3, 7)
    assert len(grid) == len(random) == 3
    assert set(grid[0]) == set(random[0])
    assert len({candidate["candidate_hash"] for candidate in grid}) == 3


def test_score_ranker_is_deterministic_and_bounded() -> None:
    metrics = {
        "total_return_pct": 20.0,
        "win_rate_pct": 60.0,
        "max_drawdown_pct": -10.0,
        "profit_factor": 2.0,
        "sharpe_ratio": 1.0,
    }
    weights = {
        "total_return_pct": 0.4,
        "win_rate_pct": 0.2,
        "max_drawdown_pct": 0.2,
        "profit_factor": 0.1,
        "sharpe_ratio": 0.1,
    }
    ranker = ScoreRanker()
    assert ranker.score(metrics, weights) == ranker.score(metrics, weights)
    assert 0 <= ranker.score(metrics, weights) <= 100
