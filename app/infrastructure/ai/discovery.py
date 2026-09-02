"""HTTP boundary for archive-aware discovery inference."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

import httpx


class DiscoveryLLMUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class DiscoveryLLMResult:
    candidate_definition: dict[str, Any]
    hypothesis: str
    operation: str
    provider: str
    model: str
    model_version: str
    prompt_version: str
    request_hash: str


class DiscoveryLLMHTTPAdapter:
    """Calls the AI service; it never receives DB credentials or queue access."""

    def __init__(self, base_url: str, timeout_s: float = 10.0, client: httpx.Client | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=timeout_s, limits=httpx.Limits(max_connections=4))
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def propose(
        self,
        search_space: dict[str, Any],
        archive: list[dict[str, Any]],
        research: dict[str, Any],
        request_id: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "mode": _mode(archive),
            "search_space": search_space,
            "archive": archive[-20:],
            "research": research,
        }
        request_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()
        try:
            response = self._client.post(
                self._base_url + "/discovery/propose",
                json=payload,
                headers={"X-Request-ID": request_id} if request_id else {},
            )
            response.raise_for_status()
            result = response.json()
            proposal = result["proposal"]
            return {
                "candidate_definition": proposal["candidate_definition"],
                "hypothesis": str(proposal["hypothesis"]).strip(),
                "operation": str(proposal["operation"]).strip(),
                "provider": str(result["provider"]).strip(),
                "model": str(result["model"]).strip(),
                "model_version": str(result["model_version"]).strip(),
                "prompt_version": str(result["prompt_version"]).strip(),
                "request_hash": request_hash,
            }
        except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise DiscoveryLLMUnavailable("discovery inference is unavailable") from exc


def _mode(archive: list[dict[str, Any]]) -> str:
    accepted = [item for item in archive if item.get("accepted")]
    if len(accepted) >= 2:
        return "combine"
    if accepted:
        return "improve"
    return "new"
