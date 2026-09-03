from __future__ import annotations

from app.config import Settings


def test_openai_key_promotes_sentiment_identity_over_legacy_groq_env(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.setenv("SENTIMENT_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setenv("SENTIMENT_MODEL_VERSION", "groq-2026-08-31")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL_VERSION", raising=False)

    settings = Settings.from_env()

    assert settings.sentiment_model == "gpt-4o-mini"
    assert settings.sentiment_model_version == "openai-gpt-4o-mini"


def test_openai_model_can_be_configured_once_for_research_and_ai(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-test-mini")
    monkeypatch.setenv("OPENAI_MODEL_VERSION", "openai-test")
    monkeypatch.setenv("SENTIMENT_MODEL", "sentiment-v1")
    monkeypatch.setenv("SENTIMENT_MODEL_VERSION", "2026-08-01")

    settings = Settings.from_env()

    assert settings.sentiment_model == "gpt-test-mini"
    assert settings.sentiment_model_version == "openai-test"
