"""HTTP boundary tests for the internal research service."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

TOKEN_HEADERS = {"Authorization": "Bearer development-internal-token"}


class FakeStore:
    def ready(self):
        return {"database": True, "active_score_policy": True}

    def operational_metrics(self):
        return {"research_jobs_queued": 2.0, "research_outbox_oldest_seconds": 0.0}

    def list_leaderboard(self, dataset_version, score_policy_version, limit, sort_by):
        del score_policy_version, limit, sort_by
        return [
            {
                "entry_id": uuid4(),
                "evaluation_id": uuid4(),
                "score": 72.5,
                "rank": 1,
                "score_policy_version": "v1",
                "dataset_version": dataset_version,
                "strategy_id": "ma_cross",
                "strategy_version": "v1",
                "candidate_hash": "a" * 64,
                "total_return_pct": 8.2,
                "win_rate_pct": 55.0,
                "max_drawdown_pct": -4.0,
                "trade_count": 12,
                "profit_factor": 1.4,
                "sharpe_ratio": 0.8,
                "observed_at": datetime(2026, 8, 25, tzinfo=UTC),
            }
        ]

    def list_strategy_drafts(self, owner_id, limit):
        self.listed_strategy_owner = owner_id
        self.listed_strategy_limit = limit
        now = datetime(2026, 8, 31, tzinfo=UTC)
        return [
            {
                "draft_id": uuid4(),
                "owner_id": owner_id,
                "source_type": "text",
                "mode": "dsl",
                "name_hint": "RSI mean reversion",
                "status": "APPROVED",
                "current_revision": 1,
                "source_hash": "a" * 64,
                "spec_hash": "b" * 64,
                "artifact_hash": "c" * 64,
                "sandbox_report_hash": "d" * 64,
                "repair_attempts_used": 1,
                "repair_attempts_max": 3,
                "strategy_spec": None,
                "created_at": now,
                "updated_at": now,
            }
        ]


app.state.store = FakeStore()
app.state.registry_sync_error = None
client = TestClient(app)


def test_health_returns_float64_service() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "research", "numeric": "float64"}
    assert response.headers["X-Request-ID"]


def test_ready_checks_database_policy_and_registry() -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    assert all(response.json()["checks"].values())


def test_metrics_requires_internal_auth_and_exposes_domain_gauges() -> None:
    assert client.get("/metrics").status_code == 401
    response = client.get("/metrics", headers=TOKEN_HEADERS)
    assert response.status_code == 200
    assert "cryptobot_research_jobs_queued 2.000000000" in response.text


def test_business_routes_require_internal_auth() -> None:
    response = client.get("/api/v1/strategies")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "internal_auth_required"


def test_strategies_return_real_registry_metadata() -> None:
    response = client.get("/api/v1/strategies", headers=TOKEN_HEADERS)
    assert response.status_code == 200
    strategy_ids = {item["strategy_id"] for item in response.json()["strategies"]}
    assert {"ma_cross", "rsi", "bollinger", "support_resistance", "news_sentiment", "macd", "composite"} <= strategy_ids


def test_strategy_draft_list_is_owned_and_bounded() -> None:
    owner_id = uuid4()
    response = client.get(
        "/api/v1/strategy-drafts?limit=3",
        headers={**TOKEN_HEADERS, "X-User-ID": str(owner_id)},
    )

    assert response.status_code == 200
    assert response.json()["drafts"][0]["owner_id"] == str(owner_id)
    assert app.state.store.listed_strategy_owner == owner_id
    assert app.state.store.listed_strategy_limit == 3


def test_leaderboard_requires_dataset_version() -> None:
    response = client.get("/api/v1/leaderboard", headers=TOKEN_HEADERS)
    assert response.status_code == 422


def test_leaderboard_returns_persisted_ranking_shape() -> None:
    response = client.get(
        "/api/v1/leaderboard?dataset_version=fixture-v1&limit=10",
        headers=TOKEN_HEADERS,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["entries"][0]["rank"] == 1
    assert body["entries"][0]["dataset_version"] == "fixture-v1"
    assert body["limit_applied"] == 10


def test_request_body_limit_is_enforced_before_validation() -> None:
    response = client.post(
        "/api/v1/experiments",
        headers={**TOKEN_HEADERS, "Content-Length": "2000000"},
        content=b"{}",
    )
    assert response.status_code == 413
    assert response.json()["code"] == "request_too_large"
