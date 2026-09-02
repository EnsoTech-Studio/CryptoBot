"""Typed boundary for model-authored discovery proposals."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class DiscoveryProposal:
    candidate_definition: dict[str, Any]
    hypothesis: str
    operation: Literal["new", "improve", "combine"]
    provider: str
    model: str
    model_version: str
    prompt_version: str
    request_hash: str
    archive_size: int = 0
    research_context: dict[str, Any] = field(default_factory=dict)
