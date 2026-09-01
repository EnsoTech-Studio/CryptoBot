from uuid import uuid4

import pytest

from app.errors import ApplicationError
from app.schemas import StrategyDraftCreateIn, StrategySourceIn, StrategySpecResponse
from app.services.authoring import (
    StrategyAuthoringService,
    compile_dsl,
    preflight_dsl,
    stabilize_generated_id,
    validate_spec,
)


def valid_spec(**overrides):
    payload = {
        "strategy_id": "generated.rsi-bollinger",
        "display_name": "RSI Bollinger",
        "family": "momentum",
        "description": "Long below the lower band and short above the upper band.",
        "parameters": {"rsi": {"period": 14}},
        "indicators": [{"id": "rsi14", "kind": "rsi", "period": 14}],
        "rules": {
            "long_entry": {"op": "below", "left": "rsi14", "right": 30},
            "short_entry": {"op": "above", "left": "rsi14", "right": 70},
            "exit": {"op": "opposite_signal"},
        },
        "warmup_bars": 14,
    }
    payload.update(overrides)
    return StrategySpecResponse.model_validate(payload)


def test_compile_is_deterministic_and_data_only():
    spec = valid_spec()
    assert compile_dsl(spec) == compile_dsl(spec)
    assert "STRATEGY_SPEC =" in compile_dsl(spec)
    assert "import " not in compile_dsl(spec)


def test_preflight_proves_the_compiled_artifact_is_data_only_and_loadable():
    report = preflight_dsl(valid_spec(), compile_dsl(valid_spec()))

    assert report["status"] == "passed"
    assert report["checks"] == ["artifact_ast", "spec_round_trip", "safe_runtime"]


def test_preflight_rejects_any_executable_artifact():
    with pytest.raises(ApplicationError, match="data-only"):
        preflight_dsl(valid_spec(), "import os\n")


def test_validate_accepts_supported_indicator_alias():
    validate_spec(
        valid_spec(
            indicators=[{"id": "bands", "kind": "Bollinger Bands", "period": 20}],
            warmup_bars=20,
            rules={
                "long_entry": {"op": "below", "left": "close", "right": "bands"},
                "short_entry": {"op": "above", "left": "close", "right": "bands"},
                "exit": {"op": "opposite_signal"},
            },
        )
    )


@pytest.mark.parametrize("indicator", ["python", "http", "unknown"])
def test_validate_rejects_unknown_indicator(indicator):
    with pytest.raises(ApplicationError):
        validate_spec(valid_spec(indicators=[{"kind": indicator}]))


def test_validate_rejects_non_generated_id():
    with pytest.raises(ApplicationError):
        validate_spec(valid_spec(strategy_id="rsi-bollinger"))


def test_stabilized_id_changes_when_the_immutable_spec_changes():
    first = stabilize_generated_id(valid_spec(display_name="RSI Bollinger"), "same-source")
    second = stabilize_generated_id(valid_spec(display_name="RSI Bollinger v2"), "same-source")

    assert first.strategy_id != second.strategy_id


def test_validate_rejects_a_warmup_shorter_than_its_indicator_period():
    with pytest.raises(ApplicationError):
        validate_spec(valid_spec(warmup_bars=13))


@pytest.mark.parametrize(
    "rule",
    [
        {"op": "above", "left": "unknown_indicator", "right": 30},
        "rsi14 < 30",
    ],
)
def test_validate_rejects_unexecutable_entry_rule(rule):
    with pytest.raises(ApplicationError):
        validate_spec(valid_spec(rules={"long_entry": rule, "short_entry": rule, "exit": {"op": "opposite_signal"}}))


class FakeDesigner:
    def design(self, _text, _request_id):
        return valid_spec()


class FakeStore:
    def create_strategy_draft(self, **kwargs):
        return kwargs


def test_create_from_text_returns_frozen_artifact():
    request = StrategyDraftCreateIn(
        owner_id=uuid4(),
        source=StrategySourceIn(type="text", text="Use RSI below 30 for long."),
    )
    result = StrategyAuthoringService(FakeStore(), FakeDesigner()).create(request, "req-1")
    assert result["artifact_hash"]
    assert result["spec"]["strategy_id"].startswith("generated.rsi-bollinger-")


def test_create_repairs_one_invalid_model_spec_with_bounded_feedback():
    class RepairingDesigner:
        def __init__(self):
            self.inputs = []

        def design(self, text, _request_id):
            self.inputs.append(text)
            return valid_spec(indicators=[{"id": "bad", "kind": "unsupported"}]) if len(self.inputs) == 1 else valid_spec()

    request = StrategyDraftCreateIn(
        owner_id=uuid4(),
        source=StrategySourceIn(type="text", text="Use RSI below 30 for long."),
    )
    designer = RepairingDesigner()
    result = StrategyAuthoringService(FakeStore(), designer).create(request)

    assert len(designer.inputs) == 2
    assert "unsupported" in designer.inputs[1]
    assert result["attempts_used"] == 2


def test_create_stops_after_three_invalid_model_specs():
    class InvalidDesigner:
        def __init__(self):
            self.inputs = []

        def design(self, text, _request_id):
            self.inputs.append(text)
            return valid_spec(indicators=[{"id": "bad", "kind": "unsupported"}])

    request = StrategyDraftCreateIn(
        owner_id=uuid4(),
        source=StrategySourceIn(type="text", text="Use RSI below 30 for long."),
    )
    designer = InvalidDesigner()

    with pytest.raises(ApplicationError, match="could not produce") as exc:
        StrategyAuthoringService(FakeStore(), designer).create(request)

    assert exc.value.code == "strategy_design_invalid"
    assert len(designer.inputs) == 3
