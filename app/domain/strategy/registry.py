"""Strategy registry.

Mirrors `server/internal/domain/strategy/registry.go`. Adding a strategy is one
plugin file calling `register_all` (0 core edits) — the extension seam required
by `specs/python-research.md`. `resolve` builds a fresh instance per run so
strategies stay stateless between replays.
"""

from __future__ import annotations

from collections.abc import Callable

from ..common import ERR_UNKNOWN_STRATEGY, ERR_VALIDATION, DomainError
from .contract import Definition, Strategy

Factory = Callable[[], Strategy]


class Registry:
    def __init__(self) -> None:
        self._factories: dict[tuple[str, str], Factory] = {}
        self._definitions: dict[tuple[str, str], Definition] = {}

    def register(self, factory: Factory) -> None:
        definition = factory().definition()
        key = (definition.strategy_id, definition.version)
        if key in self._factories:
            raise DomainError(
                ERR_VALIDATION,
                f"strategy {definition.strategy_id}@{definition.version} already registered",
            )
        self._factories[key] = factory
        self._definitions[key] = definition

    def resolve(self, strategy_id: str, version: str) -> Strategy:
        factory = self._factories.get((strategy_id, version))
        if factory is None:
            raise DomainError(ERR_UNKNOWN_STRATEGY, f"strategy {strategy_id}@{version} is not registered")
        return factory()

    def list(self) -> list[Definition]:
        return [self._definitions[key] for key in sorted(self._definitions)]
