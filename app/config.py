"""Typed runtime configuration for the internal research service."""

from __future__ import annotations

import os
from dataclasses import dataclass

OPENAI_DEFAULT_MODEL = "gpt-4o-mini"
OPENAI_DEFAULT_MODEL_VERSION = "openai-gpt-4o-mini"
LEGACY_GROQ_SENTIMENT_MODELS = {"sentiment-v1", "openai/gpt-oss-120b", "gpt-oss-120b"}


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name, "").strip()
    return value or default


def _positive_float(name: str, default: float) -> float:
    raw = _env(name)
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _positive_int(name: str, default: int) -> int:
    raw = _env(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _boolean(name: str, default: bool = False) -> bool:
    raw = _env(name, "true" if default else "false").lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean")


def _openai_inference_enabled() -> bool:
    provider = _env("AI_PROVIDER").lower()
    return provider == "openai" or bool(_env("OPENAI_API_KEY"))


def _openai_model_default() -> str:
    return (
        _env("OPENAI_MODEL")
        or _env("MODEL_CHEAP")
        or OPENAI_DEFAULT_MODEL
    ).removeprefix("openai/")


def _sentiment_model() -> str:
    configured = _env("SENTIMENT_MODEL")
    if _openai_inference_enabled():
        if not configured or configured in LEGACY_GROQ_SENTIMENT_MODELS:
            return _openai_model_default()
        return configured.removeprefix("openai/")
    return configured or "sentiment-v1"


def _sentiment_model_version() -> str:
    configured = _env("SENTIMENT_MODEL_VERSION")
    if _openai_inference_enabled():
        explicit = _env("OPENAI_MODEL_VERSION")
        if explicit:
            return explicit
        if configured and not configured.startswith("groq-") and configured != "2026-08-01":
            return configured
        return OPENAI_DEFAULT_MODEL_VERSION
    return configured or "2026-08-01"


@dataclass(frozen=True)
class Settings:
    database_url: str
    internal_service_token: str
    ai_service_url: str
    ai_timeout_s: float
    max_request_bytes: int
    max_page_size: int
    worker_lease_s: float
    worker_heartbeat_s: float
    event_lease_s: int
    sentiment_model: str
    sentiment_model_version: str
    discovery_demo_mode: bool

    @classmethod
    def from_env(cls) -> "Settings":
        lease = _positive_float("WORKER_LEASE_SECONDS", 120.0)
        heartbeat = _positive_float("WORKER_HEARTBEAT_SECONDS", 30.0)
        if heartbeat >= lease:
            raise ValueError("WORKER_HEARTBEAT_SECONDS must be smaller than WORKER_LEASE_SECONDS")
        postgres_port = _env("POSTGRES_PORT", "5432")
        return cls(
            database_url=_env(
                "DATABASE_URL",
                f"postgres://cryptobot:cryptobot@127.0.0.1:{postgres_port}/cryptobot?sslmode=disable",
            ),
            internal_service_token=_env("INTERNAL_SERVICE_TOKEN", "development-internal-token"),
            ai_service_url=_env("AI_SERVICE_URL", "http://localhost:8000").rstrip("/"),
            ai_timeout_s=_positive_float("AI_REQUEST_TIMEOUT_SECONDS", 10.0),
            max_request_bytes=_positive_int("MAX_REQUEST_BYTES", 1_048_576),
            max_page_size=_positive_int("MAX_PAGE_SIZE", 100),
            worker_lease_s=lease,
            worker_heartbeat_s=heartbeat,
            event_lease_s=_positive_int("EVENT_LEASE_SECONDS", 60),
            sentiment_model=_sentiment_model(),
            sentiment_model_version=_sentiment_model_version(),
            discovery_demo_mode=_boolean("DISCOVERY_DEMO_MODE"),
        )
