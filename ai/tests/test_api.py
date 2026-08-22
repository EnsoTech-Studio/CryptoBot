from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import main


client = TestClient(main.app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["service"] == "ai"


def test_health_remains_available_when_predictor_fails(monkeypatch) -> None:
    def unavailable(_: str) -> None:
        raise RuntimeError("model offline")

    monkeypatch.setattr(main.predictor, "predict", unavailable)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_predict_rejects_blank_text() -> None:
    response = client.post("/predict", json={"text": "   "})

    assert response.status_code == 422


def test_predict_rejects_oversized_text() -> None:
    response = client.post("/predict", json={"text": "a" * 10_001})

    assert response.status_code == 422


def test_predict_returns_sentiment_result() -> None:
    response = client.post("/predict", json={"text": "market sentiment is positive"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["model"] == "sentiment-v1"
    assert payload["model_version"] == "2026-08-01"
    assert payload["label"] in {"POSITIVE", "NEUTRAL", "NEGATIVE"}


def test_predict_returns_configured_model_version(monkeypatch) -> None:
    monkeypatch.setenv("SENTIMENT_MODEL_VERSION", "test-2026-08-16")

    response = client.post("/predict", json={"text": "market sentiment is positive"})

    assert response.status_code == 200
    assert response.json()["model_version"] == "test-2026-08-16"


def test_predict_reports_model_failure_without_fallback(monkeypatch) -> None:
    def unavailable(_: str) -> None:
        raise RuntimeError("model offline")

    monkeypatch.setattr(main.predictor, "predict", unavailable)
    failing_client = TestClient(main.app, raise_server_exceptions=False)

    response = failing_client.post("/predict", json={"text": "market is bullish"})

    assert response.status_code == 503
    assert response.json() == {"detail": {"code": "sentiment_unavailable"}}


def test_predict_rejects_malformed_model_output(monkeypatch) -> None:
    monkeypatch.setattr(
        main.predictor,
        "predict",
        lambda _: SimpleNamespace(
            label="MIXED",
            score=0.5,
            model="sentiment-v1",
            model_version="2026-08-01",
        ),
    )
    failing_client = TestClient(main.app, raise_server_exceptions=False)

    response = failing_client.post("/predict", json={"text": "market is bullish"})

    assert response.status_code == 503
    assert response.json() == {"detail": {"code": "sentiment_unavailable"}}


def test_predict_rejects_missing_model_metadata(monkeypatch) -> None:
    monkeypatch.setattr(
        main.predictor,
        "predict",
        lambda _: SimpleNamespace(
            label="POSITIVE",
            score=0.5,
            model="sentiment-v1",
        ),
    )
    failing_client = TestClient(main.app, raise_server_exceptions=False)

    response = failing_client.post("/predict", json={"text": "market is bullish"})

    assert response.status_code == 503
    assert response.json() == {"detail": {"code": "sentiment_unavailable"}}


def test_predict_rejects_model_output_that_errors_on_access(monkeypatch) -> None:
    class BrokenPrediction:
        @property
        def label(self) -> str:
            raise RuntimeError("model output is unreadable")

    monkeypatch.setattr(main.predictor, "predict", lambda _: BrokenPrediction())
    failing_client = TestClient(main.app, raise_server_exceptions=False)

    response = failing_client.post("/predict", json={"text": "market is bullish"})

    assert response.status_code == 503
    assert response.json() == {"detail": {"code": "sentiment_unavailable"}}


@pytest.mark.parametrize(
    ("model", "model_version"),
    [("   ", "2026-08-01"), ("sentiment-v1", "\t")],
)
def test_predict_rejects_blank_model_metadata(
    monkeypatch, model: str, model_version: str
) -> None:
    monkeypatch.setattr(
        main.predictor,
        "predict",
        lambda _: SimpleNamespace(
            label="POSITIVE",
            score=0.5,
            model=model,
            model_version=model_version,
        ),
    )
    failing_client = TestClient(main.app, raise_server_exceptions=False)

    response = failing_client.post("/predict", json={"text": "market is bullish"})

    assert response.status_code == 503
    assert response.json() == {"detail": {"code": "sentiment_unavailable"}}


@pytest.mark.parametrize("score", [-0.01, 1.01])
def test_predict_rejects_out_of_range_confidence(monkeypatch, score: float) -> None:
    monkeypatch.setattr(
        main.predictor,
        "predict",
        lambda _: SimpleNamespace(
            label="POSITIVE",
            score=score,
            model="sentiment-v1",
            model_version="2026-08-01",
        ),
    )
    failing_client = TestClient(main.app, raise_server_exceptions=False)

    response = failing_client.post("/predict", json={"text": "market is bullish"})

    assert response.status_code == 503
    assert response.json() == {"detail": {"code": "sentiment_unavailable"}}
