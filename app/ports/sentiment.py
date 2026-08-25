from __future__ import annotations

from typing import Protocol

from ..domain.sentiment import Result


class SentimentAnalyzer(Protocol):
    def analyze(self, text: str, request_id: str | None = None) -> Result: ...
