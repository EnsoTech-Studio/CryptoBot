from uuid import uuid4

import pytest

from app.errors import ApplicationError
from app.infrastructure.postgres.store import Store
from app.schemas import StrategyApprovalIn


class _Result:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _Connection:
    def __init__(self, rows):
        self._rows = iter(rows)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, *_):
        return _Result(next(self._rows))


def test_approve_rejects_a_different_artifact_for_existing_strategy_version(monkeypatch):
    reviewer_id = uuid4()
    artifact_hash = "a" * 64
    draft = {
        "owner_id": reviewer_id,
        "status": "REVIEW_REQUIRED",
        "current_revision": 1,
        "spec_json": {"strategy_id": "generated.same-source", "display_name": "Same", "family": "trend", "description": "x"},
        "spec_hash": "c" * 64,
        "artifact_hash": artifact_hash,
        "sandbox_report_hash": "d" * 64,
        "sandbox_status": "passed",
    }
    store = Store("unused")
    monkeypatch.setattr(store, "_connect", lambda: _Connection([draft, {"code_fingerprint": "b" * 64}]))

    with pytest.raises(ApplicationError, match="different immutable artifact") as error:
        store.approve_strategy_draft(
            uuid4(),
            StrategyApprovalIn(
                reviewer_id=reviewer_id,
                revision=1,
                spec_hash=draft["spec_hash"],
                artifact_hash=artifact_hash,
                sandbox_report_hash=draft["sandbox_report_hash"],
                decision="approve",
                reason="approved",
            ),
        )

    assert error.value.code == "strategy_version_conflict"


def test_approve_rejects_a_draft_without_a_passing_preflight(monkeypatch):
    reviewer_id = uuid4()
    draft = {
        "owner_id": reviewer_id,
        "status": "REVIEW_REQUIRED",
        "current_revision": 1,
        "spec_json": {},
        "spec_hash": "c" * 64,
        "artifact_hash": "a" * 64,
        "sandbox_report_hash": "d" * 64,
        "sandbox_status": "failed",
    }
    store = Store("unused")
    monkeypatch.setattr(store, "_connect", lambda: _Connection([draft]))

    with pytest.raises(ApplicationError, match="preflight") as error:
        store.approve_strategy_draft(
            uuid4(),
            StrategyApprovalIn(
                reviewer_id=reviewer_id, revision=1, spec_hash=draft["spec_hash"],
                artifact_hash=draft["artifact_hash"], sandbox_report_hash=draft["sandbox_report_hash"],
                decision="approve", reason="approved",
            ),
        )

    assert error.value.code == "sandbox_not_passed"
