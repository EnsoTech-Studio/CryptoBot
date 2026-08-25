"""Typed runtime configuration for the internal research service."""

from __future__ import annotations

import os
from dataclasses import dataclass


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
    sentiment_model: str
    sentiment_model_version: str

    @classmethod
    def from_env(cls) -> "Settings":
        lease = _positive_float("WORKER_LEASE_SECONDS", 120.0)
        heartbeat = _positive_float("WORKER_HEARTBEAT_SECONDS", 30.0)
        if heartbeat >= lease:
            raise ValueError("WORKER_HEARTBEAT_SECONDS must be smaller than WORKER_LEASE_SECONDS")
        return cls(
            database_url=_env(
                "DATABASE_URL",
                "postgres://cryptobot:cryptobot@localhost:5432/cryptobot?sslmode=disable",
            ),
            internal_service_token=_env("INTERNAL_SERVICE_TOKEN", "development-internal-token"),
            ai_service_url=_env("AI_SERVICE_URL", "http://localhost:8000").rstrip("/"),
            ai_timeout_s=_positive_float("AI_REQUEST_TIMEOUT_SECONDS", 10.0),
            max_request_bytes=_positive_int("MAX_REQUEST_BYTES", 1_048_576),
            max_page_size=_positive_int("MAX_PAGE_SIZE", 100),
            worker_lease_s=lease,
            worker_heartbeat_s=heartbeat,
            sentiment_model=_env("SENTIMENT_MODEL", "sentiment-v1"),
            sentiment_model_version=_env("SENTIMENT_MODEL_VERSION", "2026-08-01"),
        )
