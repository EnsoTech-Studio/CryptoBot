"""Static least-privilege policy for the logical agent roles."""

from __future__ import annotations

from collections.abc import Mapping

from ..errors import ApplicationError


_TOOLS_BY_ROLE: Mapping[str, frozenset[str]] = {
    "StrategyDesignerAgent": frozenset(
        {
            "source.get_document",
            "strategy.get_catalog",
            "strategy.get_dsl_schema",
            "strategy.validate_spec",
            "strategy.get_validation_errors",
            "strategy.save_draft_spec",
        }
    ),
    "StrategyImplementationAgent": frozenset(
        {
            "artifact.compile_from_spec",
            "artifact.create_custom_draft",
            "artifact.run_policy_check",
            "artifact.save_version",
            "sandbox.run_contract_tests",
            "sandbox.get_test_report",
            "draft.mark_review_required",
        }
    ),
    "StrategyRepairAgent": frozenset(
        {
            "agent.get_attempt_context",
            "sandbox.get_test_report",
            "strategy.apply_spec_patch",
            "artifact.apply_code_patch",
            "strategy.validate_spec",
            "artifact.run_policy_check",
            "sandbox.run_contract_tests",
            "draft.mark_failed",
        }
    ),
    "NewsExtractionAgent": frozenset(
        {
            "document.get_sanitized_html",
            "document.get_extraction_errors",
            "news.get_item_schema",
            "news.validate_extraction",
            "news.save_extraction",
        }
    ),
    "CandidateDiscoveryAgent": frozenset(
        {
            "search.get_search_space",
            "search.get_tested_hashes",
            "leaderboard.get_summary",
            "candidate.validate",
            "candidate.estimate_cost",
            "candidate.submit_batch",
        }
    ),
    "MarketInsightAgent": frozenset(
        {
            "market.get_snapshot",
            "indicator.get_snapshot",
            "news.get_recent_summary",
            "experiment.get_recent_results",
            "insight.save_draft",
        }
    ),
}

# State is part of authority: a known role may still not use one of its tools
# before the persisted workflow has reached the corresponding gate.
_STATES_BY_TOOL: Mapping[str, frozenset[str]] = {
    "source.get_document": frozenset({"SPEC_GENERATING"}),
    "strategy.get_catalog": frozenset({"SPEC_GENERATING"}),
    "strategy.get_dsl_schema": frozenset({"SPEC_GENERATING"}),
    "strategy.validate_spec": frozenset({"SPEC_VALIDATING", "REPAIRING"}),
    "strategy.get_validation_errors": frozenset({"SPEC_VALIDATING", "REPAIRING"}),
    "strategy.save_draft_spec": frozenset({"SPEC_VALIDATING"}),
    "artifact.compile_from_spec": frozenset({"CODE_GENERATING"}),
    "artifact.create_custom_draft": frozenset({"CODE_GENERATING"}),
    "artifact.run_policy_check": frozenset({"POLICY_CHECKING", "REPAIRING"}),
    "artifact.save_version": frozenset({"CODE_GENERATING"}),
    "sandbox.run_contract_tests": frozenset({"SANDBOX_TESTING", "REPAIRING"}),
    "sandbox.get_test_report": frozenset({"SANDBOX_TESTING", "REPAIRING"}),
    "draft.mark_review_required": frozenset({"SANDBOX_TESTING"}),
    "agent.get_attempt_context": frozenset({"REPAIRING"}),
    "strategy.apply_spec_patch": frozenset({"REPAIRING"}),
    "artifact.apply_code_patch": frozenset({"REPAIRING"}),
    "draft.mark_failed": frozenset({"REPAIRING"}),
    "document.get_sanitized_html": frozenset({"EXTRACTING"}),
    "document.get_extraction_errors": frozenset({"EXTRACTING", "VALIDATING"}),
    "news.get_item_schema": frozenset({"EXTRACTING"}),
    "news.validate_extraction": frozenset({"VALIDATING"}),
    "news.save_extraction": frozenset({"VALIDATING"}),
    "search.get_search_space": frozenset({"RUNNING"}),
    "search.get_tested_hashes": frozenset({"RUNNING"}),
    "leaderboard.get_summary": frozenset({"RUNNING"}),
    "candidate.validate": frozenset({"RUNNING"}),
    "candidate.estimate_cost": frozenset({"RUNNING"}),
    "candidate.submit_batch": frozenset({"RUNNING"}),
    "market.get_snapshot": frozenset({"RUNNING"}),
    "indicator.get_snapshot": frozenset({"RUNNING"}),
    "news.get_recent_summary": frozenset({"RUNNING"}),
    "experiment.get_recent_results": frozenset({"RUNNING"}),
    "insight.save_draft": frozenset({"RUNNING"}),
}

_NEXT_STATES: Mapping[str, frozenset[str]] = {
    "DRAFT_CREATED": frozenset({"SOURCE_READY"}),
    "SOURCE_READY": frozenset({"SPEC_GENERATING"}),
    "SPEC_GENERATING": frozenset({"SPEC_VALIDATING", "FAILED"}),
    "SPEC_VALIDATING": frozenset({"CODE_GENERATING", "REPAIRING", "FAILED"}),
    "CODE_GENERATING": frozenset({"POLICY_CHECKING", "FAILED"}),
    "POLICY_CHECKING": frozenset({"SANDBOX_TESTING", "REPAIRING", "FAILED"}),
    "SANDBOX_TESTING": frozenset({"REVIEW_REQUIRED", "REPAIRING", "FAILED"}),
    "REPAIRING": frozenset({"SPEC_GENERATING", "CODE_GENERATING", "FAILED"}),
    "REVIEW_REQUIRED": frozenset({"APPROVED", "REJECTED"}),
    "APPROVED": frozenset({"PUBLISHED"}),
}


class AgentWorkflow:
    """Deterministic authoring state machine; persistence is owned by Store."""

    def __init__(self, max_repairs: int = 3) -> None:
        self.state = "DRAFT_CREATED"
        self.history = [self.state]
        self._remaining_repairs = max_repairs

    def transition(self, target: str) -> None:
        if target not in _NEXT_STATES.get(self.state, frozenset()):
            raise ApplicationError("agent_state_conflict", "agent state transition is not permitted", 409)
        if target == "REPAIRING" and self._remaining_repairs <= 0:
            raise ApplicationError("agent_budget_exhausted", "agent repair budget is exhausted", 409)
        if target == "REPAIRING":
            self._remaining_repairs -= 1
        self.state = target
        self.history.append(target)


class ToolRegistry:
    """Answers only whether a fixed role may use a fixed typed tool."""

    def allows(self, role: str, tool: str, state: str) -> bool:
        return tool in _TOOLS_BY_ROLE.get(role, frozenset()) and state in _STATES_BY_TOOL.get(tool, frozenset())

    def require(self, role: str, tool: str, state: str) -> None:
        if not self.allows(role, tool, state):
            raise ApplicationError("agent_tool_forbidden", "agent tool is not permitted", 403)
