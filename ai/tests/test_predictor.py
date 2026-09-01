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


def test_design_prompt_requires_the_runtime_dsl_shape(monkeypatch) -> None:
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
    assert "Never use `name`, `alias`, `type`, `params`, `entry`, or `condition`" in observed["messages"][0]["content"]
    assert observed["response_format"]["json_schema"]["name"] == "strategy_spec"


def test_python_repair_returns_only_a_bounded_replacement_artifact(monkeypatch) -> None:
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
