from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import main
from app.services.predictor import NewsExtraction, NewsStrategyAnalysis, Prediction


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


def test_strategy_spec_includes_the_model_provenance(monkeypatch) -> None:
    monkeypatch.setattr(
        main.predictor,
        "design",
        lambda _: {
            "schema_version": "strategy-spec/v1",
            "strategy_id": "generated.rsi",
            "display_name": "RSI",
            "family": "momentum",
            "description": "Causal RSI strategy.",
            "parameters": {},
            "indicators": [{"id": "rsi14", "kind": "rsi", "period": 14}],
            "rules": {"long_entry": {}, "short_entry": {}, "exit": {"op": "opposite_signal"}},
            "warmup_bars": 14,
        },
    )
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("OPENAI_MODEL_VERSION", "openai-test")
    monkeypatch.setenv("SENTIMENT_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setenv("SENTIMENT_MODEL_VERSION", "groq-2026-09-01")

    response = client.post("/strategy/spec", json={"text": "Use RSI."})

    assert response.status_code == 200
    assert response.json()["model"] == "gpt-4o-mini"
    assert response.json()["model_version"] == "openai-test"
    assert response.json()["spec"]["strategy_id"] == "generated.rsi"


def test_news_extract_returns_structured_source_excerpt(monkeypatch) -> None:
    monkeypatch.setattr(
        main.predictor,
        "extract_news",
        lambda _: NewsExtraction("Bitcoin market update", "Bitcoin liquidity improved after spot demand increased.", "openai/gpt-oss-120b", "test"),
    )

    response = client.post("/news/extract", json={"text": "Bitcoin market update. Bitcoin liquidity improved after spot demand increased."})

    assert response.status_code == 200
    assert response.json()["body"].startswith("Bitcoin liquidity")


def test_news_aggregate_sentiment_uses_its_dedicated_llm_operation(monkeypatch) -> None:
    monkeypatch.setattr(main.predictor, "predict_aggregate", lambda _: Prediction(
        "POSITIVE", 0.78, "openai/gpt-oss-120b", "groq-test"
    ))

    response = client.post("/news/aggregate-sentiment", json={"text": "BTC demand improved. ETH liquidity improved."})

    assert response.status_code == 200
    assert response.json()["label"] == "POSITIVE"
    assert response.json()["score"] == 0.78


def test_news_strategy_analysis_returns_reasoning_and_model(monkeypatch) -> None:
    monkeypatch.setattr(main.predictor, "analyze_news_strategy", lambda payload, model_override=None: NewsStrategyAnalysis(
        "1. Đọc sentiment thật.",
        "{\"decision\":\"BULLISH_NEWS_FILTER\"}",
        model_override or "gpt-4o-mini",
        "openai-gpt-4o-mini",
    ))

    response = client.post("/news/strategy-analysis", json={
        "sentiment_mix": {"positive": 60, "neutral": 30, "negative": 10},
        "coverage": {"items_total": 10, "items_analyzed": 8, "items_unanalyzed": 2},
        "average_score": 0.72,
        "model": "gpt-4o-mini",
    })

    assert response.status_code == 200
    assert response.json()["reasoning"].startswith("1.")
    assert response.json()["model"] == "gpt-4o-mini"


def test_predict_rejects_oversized_text() -> None:
    response = client.post("/predict", json={"text": "a" * 10_001})

    assert response.status_code == 422


def test_predict_returns_sentiment_result(monkeypatch) -> None:
    monkeypatch.setattr(main.predictor, "predict", lambda _: Prediction(
        "POSITIVE", 0.84, "openai/gpt-oss-120b", "groq-test"
    ))
    response = client.post("/predict", json={"text": "market sentiment is positive"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["model"] == "openai/gpt-oss-120b"
    assert payload["model_version"] == "groq-test"
    assert payload["label"] in {"POSITIVE", "NEUTRAL", "NEGATIVE"}


def test_predict_returns_configured_model_version(monkeypatch) -> None:
    monkeypatch.setenv("SENTIMENT_MODEL_VERSION", "test-2026-08-16")
    monkeypatch.setattr(main.predictor, "predict", lambda _: Prediction(
        "POSITIVE", 0.84, "openai/gpt-oss-120b", "test-2026-08-16"
    ))

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
