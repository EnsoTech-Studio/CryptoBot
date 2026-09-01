"""Internal adapter for structured strategy design inference."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json

import httpx

from ...schemas import StrategySpecResponse


class StrategyDesignUnavailable(RuntimeError):
    pass


class NewsExtractionUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class NewsExtraction:
    title: str
    body: str
    model: str
    model_version: str


class NewsExtractionHTTPAdapter:
    def __init__(
        self,
        base_url: str,
        timeout_s: float = 10.0,
        client: httpx.Client | None = None,
        model: str = "",
        model_version: str = "",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=timeout_s, limits=httpx.Limits(max_connections=4))
        self._owns_client = client is None
        self._model = model.strip()
        self._model_version = model_version.strip()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def extract(self, document_text: str, request_id: str | None = None) -> NewsExtraction:
        if not document_text.strip() or len(document_text) > 20_000:
            raise NewsExtractionUnavailable("sanitized document is outside extraction bounds")
        headers = {"X-Request-ID": request_id} if request_id else {}
        try:
            response = self._client.post(self._base_url + "/news/extract", json={"text": document_text}, headers=headers)
            response.raise_for_status()
            payload = response.json()
            result = NewsExtraction(
                title=str(payload["title"]).strip(), body=str(payload["body"]).strip(),
                model=str(payload["model"]).strip(), model_version=str(payload["model_version"]).strip(),
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise NewsExtractionUnavailable("news extraction inference is unavailable") from exc
        if not result.title or len(result.body) < 40 or not result.model or not result.model_version:
            raise NewsExtractionUnavailable("news extraction response is invalid")
        if self._model and (result.model != self._model or result.model_version != self._model_version):
            raise NewsExtractionUnavailable("news extraction model identity differs from configured cache policy")
        return result

    def cache_key(self, document_text: str) -> str | None:
        if not self._model or not self._model_version:
            return None
        payload = {
            "document_hash": sha256(document_text.encode("utf-8")).hexdigest(),
            "method": "llm-fallback/v1",
            "model": self._model,
            "model_version": self._model_version,
            "prompt_version": "news-extract/v1",
            "schema_version": "news-extraction/v1",
            "quality_policy_version": "html-quality/v1",
        }
        return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


class StrategyDesignHTTPAdapter:
    def __init__(self, base_url: str, timeout_s: float = 10.0) -> None:
        self._client = httpx.Client(timeout=timeout_s, limits=httpx.Limits(max_connections=4))
        self._base_url = base_url.rstrip("/")

    def close(self) -> None:
        self._client.close()

    def design(self, text: str, request_id: str | None = None) -> StrategySpecResponse:
        headers = {"X-Request-ID": request_id} if request_id else {}
        try:
            response = self._client.post(
                self._base_url + "/strategy/spec", json={"text": text}, headers=headers
            )
            response.raise_for_status()
            return StrategySpecResponse.model_validate(response.json())
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise StrategyDesignUnavailable("strategy design inference is unavailable") from exc
