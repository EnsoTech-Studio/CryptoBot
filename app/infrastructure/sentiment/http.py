"""Bounded research-to-AI sentiment adapter."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from ...domain.sentiment import NEGATIVE, NEUTRAL, POSITIVE, Result


class SentimentUnavailable(RuntimeError):
    pass


class ContractViolation(RuntimeError):
    pass


class SentimentHTTPAdapter:
    def __init__(
        self,
        base_url: str,
        timeout_s: float = 5.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=timeout_s, limits=httpx.Limits(max_connections=8))
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def analyze(self, text: str, request_id: str | None = None) -> Result:
        return self._analyze(text, "/predict", request_id)

    def analyze_aggregate(self, text: str, request_id: str | None = None) -> Result:
        return self._analyze(text, "/news/aggregate-sentiment", request_id)

    def _analyze(self, text: str, path: str, request_id: str | None) -> Result:
        normalized = text.strip()
        if not normalized or len(normalized) > 10_000:
            raise ContractViolation("sentiment input must contain 1..10000 characters")
        headers = {"X-Request-ID": request_id} if request_id else {}
        try:
            response = self._client.post(
                self._base_url + path,
                json={"text": normalized},
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise SentimentUnavailable("AI inference unavailable") from exc
        if response.status_code < 200 or response.status_code >= 300:
            raise SentimentUnavailable("AI inference unavailable")
        try:
            payload = response.json()
            label = payload["label"]
            score = float(payload["score"])
            model = str(payload["model"]).strip()
            model_version = str(payload["model_version"]).strip()
        except (KeyError, TypeError, ValueError) as exc:
            raise ContractViolation("AI response does not match sentiment contract") from exc
        if label not in {POSITIVE, NEUTRAL, NEGATIVE}:
            raise ContractViolation("AI returned an unsupported sentiment label")
        if not 0.0 <= score <= 1.0 or not model or not model_version:
            raise ContractViolation("AI returned invalid sentiment metadata")
        return Result(
            label=label,
            score=score,
            model=model,
            model_version=model_version,
            analyzed_at=datetime.now(tz=UTC),
        )
