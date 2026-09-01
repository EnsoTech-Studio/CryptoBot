import pytest

from app.errors import ApplicationError
from app.services.agent_tools import AgentWorkflow, ToolRegistry


def test_designer_agent_can_only_use_its_declared_typed_tools():
    tools = ToolRegistry()

    assert tools.allows("StrategyDesignerAgent", "strategy.validate_spec", "SPEC_VALIDATING")
    assert not tools.allows("StrategyDesignerAgent", "strategy.validate_spec", "CODE_GENERATING")
    assert not tools.allows("StrategyDesignerAgent", "shell.execute", "SPEC_VALIDATING")

    with pytest.raises(ApplicationError) as error:
        tools.require("StrategyDesignerAgent", "shell.execute", "SPEC_VALIDATING")

    assert error.value.code == "agent_tool_forbidden"


def test_authoring_workflow_rejects_illegal_transitions_and_keeps_audit_history():
    workflow = AgentWorkflow()

    with pytest.raises(ApplicationError) as error:
        workflow.transition("CODE_GENERATING")
    assert error.value.code == "agent_state_conflict"

    for state in ("SOURCE_READY", "SPEC_GENERATING", "SPEC_VALIDATING", "CODE_GENERATING", "POLICY_CHECKING", "SANDBOX_TESTING", "REVIEW_REQUIRED"):
        workflow.transition(state)

    assert workflow.state == "REVIEW_REQUIRED"
    assert workflow.history == [
        "DRAFT_CREATED", "SOURCE_READY", "SPEC_GENERATING", "SPEC_VALIDATING",
        "CODE_GENERATING", "POLICY_CHECKING", "SANDBOX_TESTING", "REVIEW_REQUIRED",
    ]


def test_authoring_workflow_refuses_repairs_after_its_budget_is_exhausted():
    workflow = AgentWorkflow(max_repairs=1)

    for state in ("SOURCE_READY", "SPEC_GENERATING", "SPEC_VALIDATING", "REPAIRING", "CODE_GENERATING", "POLICY_CHECKING"):
        workflow.transition(state)

    with pytest.raises(ApplicationError) as error:
        workflow.transition("REPAIRING")

    assert error.value.code == "agent_budget_exhausted"
