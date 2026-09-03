import json

import pytest

from app.services.predictor import Predictor, _canonicalize_strategy_spec


def test_legacy_strategy_with_unknown_condition_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported legacy condition"):
        _canonicalize_strategy_spec(
            {
                "strategy_id": "sma-cross",
                "indicators": [
                    {"id": "sma20", "kind": "sma", "params": {"period": 20}},
                    {"id": "sma50", "kind": "sma", "params": {"period": 50}},
                ],
                "long_entry": {"condition": "sma20.value is much stronger"},
                "short_entry": {"condition": "sma20.value is much weaker"},
            }
        )


def test_legacy_object_shape_with_entry_rules_is_canonicalized() -> None:
    result = _canonicalize_strategy_spec(
        {
            "name": "SMA20_50_Crossover",
            "description": "Long when SMA20 crosses above SMA50.",
            "indicators": {
                "sma20": {"type": "SMA", "period": 20, "source": "close"},
                "sma50": {"type": "SMA", "period": 50, "source": "close"},
            },
            "entry": {
                "long": {"condition": "crossover(sma20,sma50)"},
                "short": {"condition": "crossunder(sma20,sma50)"},
            },
        }
    )

    assert result["strategy_id"] == "generated.SMA20_50_Crossover"
    assert result["rules"] == {
        "long_entry": {"op": "crosses_above", "left": "sma20", "right": "sma50"},
        "short_entry": {"op": "crosses_below", "left": "sma20", "right": "sma50"},
        "exit": {"op": "opposite_signal"},
    }
    assert result["warmup_bars"] == 50


def test_legacy_typed_rules_and_indicator_names_are_canonicalized() -> None:
    result = _canonicalize_strategy_spec(
        {
            "strategy_id": "generated_sma_crossover_20_50",
            "description": "Causal crossover.",
            "indicators": [
                {"name": "sma20", "kind": "sma", "params": {"period": 20}},
                {"name": "sma50", "kind": "sma", "params": {"period": 50}},
            ],
            "rules": {
                "long_entry": {"type": "crossover", "left": "sma20", "right": "sma50"},
                "short_entry": {"type": "crossunder", "left": "sma20", "right": "sma50"},
            },
        }
    )

    assert result["strategy_id"] == "generated.sma_crossover_20_50"
    assert result["indicators"] == [
        {"id": "sma20", "kind": "sma", "period": 20},
        {"id": "sma50", "kind": "sma", "period": 50},
    ]
    assert result["rules"]["long_entry"] == {"op": "crosses_above", "left": "sma20", "right": "sma50"}
    assert result["rules"]["short_entry"] == {"op": "crosses_below", "left": "sma20", "right": "sma50"}


def test_legacy_condition_operator_and_indicator_alias_are_canonicalized() -> None:
    result = _canonicalize_strategy_spec(
        {
            "strategy_id": "generated_sma_crossover_20_50",
            "description": "Causal crossover.",
            "indicators": [
                {"kind": "sma", "period": 20, "alias": "sma20"},
                {"kind": "sma", "period": 50, "alias": "sma50"},
            ],
            "rules": {
                "long_entry": {"condition": "crossover", "left": "sma20", "right": "sma50"},
                "short_entry": {"condition": "crossunder", "left": "sma20", "right": "sma50"},
            },
        }
    )

    assert [indicator["id"] for indicator in result["indicators"]] == ["sma20", "sma50"]
    assert result["rules"]["long_entry"] == {"op": "crosses_above", "left": "sma20", "right": "sma50"}


def test_llm_comparison_aliases_and_value_wrappers_are_canonicalized() -> None:
    result = _canonicalize_strategy_spec(
        {
            "strategy_id": "generated_rsi_strategy_001",
            "description": "RSI threshold strategy.",
            "indicators": [{"id": "rsi1", "kind": "rsi"}],
            "rules": {
                "long_entry": {"op": "<", "left": {"indicator": "rsi1"}, "right": {"value": 30}},
                "short_entry": {"op": ">", "left": {"indicator": "rsi1"}, "right": {"value": 70}},
            },
            "warmup_bars": 14,
        }
    )

    assert result["rules"]["long_entry"] == {"op": "below", "left": "rsi1", "right": 30}
    assert result["rules"]["short_entry"] == {"op": "above", "left": "rsi1", "right": 70}


def test_llm_boolean_bollinger_rule_shape_is_canonicalized() -> None:
    result = _canonicalize_strategy_spec(
        {
            "strategy_id": "generated_rsi_bollinger_long_001",
            "parameters": {},
            "indicators": [
                {"id": "rsi_14", "kind": "rsi", "parameters": {"period": 14}},
                {"id": "bb", "kind": "bollinger", "parameters": {"period": 20, "stddev": 2}},
            ],
            "rules": {
                "long_entry": {
                    "op": "and",
                    "left": {"op": "cross_below", "left": {"indicator_id": "rsi_14"}, "right": {"value": 30}},
                    "right": {"op": "below", "left": {"series": "close"}, "right": {"indicator_id": "bb", "component": "lower"}},
                },
                "short_entry": {"op": "always_false"},
            },
        }
    )

    assert result["indicators"] == [
        {"id": "rsi_14", "kind": "rsi", "period": 14},
        {"id": "bb", "kind": "bollinger", "period": 20, "deviation": 2},
    ]
    assert result["rules"]["long_entry"] == {
        "op": "and",
        "items": [
            {"op": "crosses_below", "left": "rsi_14", "right": 30},
            {"op": "below", "left": "close", "right": "bb.lower"},
        ],
    }
    assert result["rules"]["short_entry"] == {"op": "equals", "left": 0, "right": 1}


def test_design_prompt_requires_the_runtime_dsl_shape(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    observed = {}
    response = {
        "schema_version": "strategy-spec/v1",
        "strategy_id": "generated.sma-cross",
        "display_name": "SMA Cross",
        "family": "trend",
        "description": "Causal SMA crossover.",
        "parameters": {},
        "indicators": [{"id": "sma20", "kind": "sma", "period": 20}],
        "rules": {
            "long_entry": {"op": "above", "left": "close", "right": "sma20"},
            "short_entry": {"op": "below", "left": "close", "right": "sma20"},
            "exit": {"op": "opposite_signal"},
        },
        "warmup_bars": 20,
    }

    def requester(request, _timeout):
        observed.update(json.loads(request.data))
        return json.dumps({"choices": [{"message": {"content": json.dumps({"spec_json": json.dumps(response)})}}]}).encode()

    assert Predictor(requester).design("Use an SMA crossover.") == response
    assert "Entry comparison form" in observed["messages"][0]["content"]
    assert observed["response_format"]["json_schema"]["name"] == "strategy_spec"


def test_openai_configuration_is_preferred_and_uses_shared_model(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.setenv("MODEL_CHEAP", "gpt-test-mini")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://openai.example/v1")
    monkeypatch.setenv("SENTIMENT_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setenv("SENTIMENT_MODEL_VERSION", "groq-2026-08-31")
    observed = {}

    def requester(request, _timeout):
        observed["url"] = request.full_url
        observed["authorization"] = request.headers["Authorization"]
        observed["payload"] = json.loads(request.data)
        return json.dumps({"choices": [{"message": {"content": json.dumps({"label": "NEUTRAL", "score": 0.5})}}]}).encode()

    result = Predictor(requester).predict("market update")

    assert result.model == "gpt-test-mini"
    assert result.model_version == "openai-gpt-4o-mini"
    assert observed["url"] == "https://openai.example/v1/chat/completions"
    assert observed["authorization"] == "Bearer openai-test-key"
    assert observed["payload"]["model"] == "gpt-test-mini"
    assert observed["payload"]["temperature"] == 0
    assert "reasoning_effort" not in observed["payload"]


def test_openai_provider_can_be_forced_without_groq_key(monkeypatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    predictor = Predictor(lambda _request, _timeout: b"{}")

    assert predictor.provider == "openai"
    assert predictor.model == "gpt-4o-mini"
    assert predictor.model_version == "openai-gpt-4o-mini"


def test_news_strategy_analysis_uses_selected_openai_model(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://openai.example/v1")
    observed = {}

    def requester(request, _timeout):
        observed["payload"] = json.loads(request.data)
        return json.dumps({"choices": [{"message": {"content": json.dumps({
            "reasoning": "1. Đọc sentiment thật.\n2. Đánh giá coverage.",
            "result_json": json.dumps({"strategy_id": "news_sentiment@v1", "version": "1.0", "decision": "BULLISH_NEWS_FILTER"}),
        })}}]}).encode()

    result = Predictor(requester).analyze_news_strategy(
        {
            "sentiment_mix": {"positive": 60, "neutral": 30, "negative": 10},
            "coverage": {"items_total": 10, "items_analyzed": 8, "items_unanalyzed": 2},
            "average_score": 0.72,
        },
        model_override="gpt-4o-mini",
    )

    assert result.model == "gpt-4o-mini"
    assert result.model_version == "openai-gpt-4o-mini"
    assert observed["payload"]["model"] == "gpt-4o-mini"
    assert observed["payload"]["temperature"] == 0
    assert "reasoning_effort" not in observed["payload"]
    assert "Quy trình suy luận AI" in observed["payload"]["messages"][0]["content"]
    parsed = json.loads(result.result)
    assert parsed["decision"] == "BULLISH_NEWS_FILTER"
    assert parsed["strategy_id"] == "news_sentiment"
    assert parsed["version"] == "v1"


def test_python_repair_returns_only_a_bounded_replacement_artifact(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    observed = {}

    def requester(request, _timeout):
        observed.update(json.loads(request.data))
        return json.dumps({"choices": [{"message": {"content": json.dumps({"artifact": "class Strategy:\n    def analyze(self, candles):\n        return ()"})}}]}).encode()

    repaired = Predictor(requester).repair_python(
        "class Strategy:\n    def analyze(self, candles):\n        return []", "strategy_sandbox_failed"
    )

    assert repaired.endswith("return ()")
    assert observed["response_format"]["json_schema"]["name"] == "strategy_python_repair"
    assert "untrusted code" in observed["messages"][0]["content"]


def test_discovery_proposal_normalizes_component_shorthand(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    response = {
        "hypothesis": "Trend and momentum complement each other.",
        "operation": "combine",
        "candidate_json": json.dumps(
            {
                "components": [
                    {"strategy_id": "ma_cross", "parameters": {"fast": 5, "slow": 20}},
                    {"strategy_id": "rsi", "parameters": {"period": 14}},
                ],
                "weights": [0.7, 0.3],
                "policy": "weighted_vote",
            }
        ),
    }

    def requester(request, _timeout):
        payload = json.loads(request.data)
        assert "test_metrics" in payload["messages"][1]["content"]
        return json.dumps({"choices": [{"message": {"content": json.dumps(response)}}]}).encode()

    result = Predictor(requester).propose_discovery(
        {"mode": "combine", "search_space": {"strategy_ids": ["ma_cross", "rsi"]}, "archive": [], "research": {"test_metrics": "sealed"}}
    )

    assert result["operation"] == "combine"
    assert result["candidate_definition"]["strategy_id"] == "composite"
    assert [child["weight"] for child in result["candidate_definition"]["children"]] == [0.7, 0.3]


def test_discovery_proposal_normalizes_strategies_alias(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    response = {
        "hypothesis": "Trend and momentum diversify the signal.",
        "operation": "combine",
        "candidate_json": json.dumps(
            {
                "strategies": [
                    {"strategy_id": "ma_cross", "parameters": {}},
                    {"strategy_id": "rsi", "parameters": {}},
                ],
                "policy": "majority_vote",
            }
        ),
    }

    def requester(request, _timeout):
        return json.dumps({"choices": [{"message": {"content": json.dumps(response)}}]}).encode()

    result = Predictor(requester).propose_discovery(
        {"mode": "combine", "search_space": {"strategy_ids": ["ma_cross", "rsi"]}}
    )

    assert result["candidate_definition"]["policy"]["name"] == "majority_vote"
    assert [child["strategy_id"] for child in result["candidate_definition"]["children"]] == ["ma_cross", "rsi"]


def test_near_spec_is_normalized_before_contract_validation() -> None:
    result = _canonicalize_strategy_spec(
        {
            "schema_version": "1.0",
            "strategy_id": "generated_sma_crossover_20_50",
            "display_name": "SMA 20/50 Crossover",
            "family": "crossover",
            "description": "Causal crossover.",
            "parameters": {"sma_fast_period": 20, "sma_slow_period": 50},
            "indicators": [{"id": "sma_fast", "kind": "sma"}, {"id": "sma_slow", "kind": "sma"}],
            "rules": {
                "long_entry": {"op": "crossover", "left": {"indicator": "sma_fast"}, "right": {"indicator": "sma_slow"}},
                "short_entry": {"op": "crossunder", "left": {"indicator": "sma_fast"}, "right": {"indicator": "sma_slow"}},
                "exit": {"op": "opposite_signal"},
            },
            "warmup_bars": 50,
        }
    )

    assert result["schema_version"] == "strategy-spec/v1"
    assert result["family"] == "trend"
    assert result["parameters"] == {"sma_fast_period": {"default": 20}, "sma_slow_period": {"default": 50}}
    assert result["indicators"] == [
        {"id": "sma_fast", "kind": "sma", "period": "$sma_fast_period"},
        {"id": "sma_slow", "kind": "sma", "period": "$sma_slow_period"},
    ]
    assert result["rules"]["long_entry"] == {"op": "crosses_above", "left": "sma_fast", "right": "sma_slow"}


def test_canonical_shape_derives_period_and_warmup_from_length_parameters() -> None:
    result = _canonicalize_strategy_spec(
        {
            "schema_version": "strategy-spec/v1",
            "strategy_id": "generated.sma-cross",
            "display_name": "SMA Cross",
            "family": "trend",
            "description": "Causal crossover.",
            "parameters": {"sma20_length": {"default": 20}, "sma50_length": {"default": 50}},
            "indicators": [{"id": "sma20", "kind": "sma"}, {"id": "sma50", "kind": "sma"}],
            "rules": {
                "long_entry": {"op": "crosses_above", "left": "sma20", "right": "sma50"},
                "short_entry": {"op": "crosses_below", "left": "sma20", "right": "sma50"},
                "exit": {"op": "opposite_signal"},
            },
            "warmup_bars": 1,
        }
    )

    assert result["indicators"] == [
        {"id": "sma20", "kind": "sma", "period": "$sma20_length"},
        {"id": "sma50", "kind": "sma", "period": "$sma50_length"},
    ]
    assert result["warmup_bars"] == 50
