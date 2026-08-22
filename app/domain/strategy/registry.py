"""Strategy registry (stub).

Mirrors `server/internal/domain/strategy/registry.go`.
"""

from __future__ import annotations

from collections.abc import Callable

from .contract import Definition, Strategy

Factory = Callable[[], Strategy]


class Registry:
    def __init__(self) -> None:
        self._factories: dict[tuple[str, str], Factory] = {}

    def register(self, factory: Factory) -> None:
        raise NotImplementedError

    def resolve(self, strategy_id: str, version: str) -> Strategy:
        raise NotImplementedError

    def list(self) -> list[Definition]:
        return []
