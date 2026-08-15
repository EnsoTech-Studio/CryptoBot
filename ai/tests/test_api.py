from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["service"] == "ai"


def test_predict_rejects_blank_text() -> None:
    response = client.post("/predict", json={"text": "   "})

    assert response.status_code == 422


def test_predict_returns_sentiment_result() -> None:
    response = client.post("/predict", json={"text": "market sentiment is positive"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["model"] == "sentiment-v1"
    assert payload["model_version"] == "2026-08-01"
    assert payload["label"] in {"POSITIVE", "NEUTRAL", "NEGATIVE"}
