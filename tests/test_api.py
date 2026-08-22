"""Smoke tests for the strategy/backtest backend route surface."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_float64_service() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "strategy-backtest"
    assert body["numeric"] == "float64"


def test_ready() -> None:
    response = client.get("/ready")
    assert response.status_code == 200


def test_leaderboard_route_exists() -> None:
    response = client.get("/api/v1/leaderboard")
    assert response.status_code == 501
    assert response.json()["error"] == "not implemented"


def test_strategies_route_exists() -> None:
    response = client.get("/api/v1/strategies")
    assert response.status_code == 501
