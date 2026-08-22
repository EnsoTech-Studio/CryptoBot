"""Package-owned bootstrap seam for MA/RSI/Bollinger/SR/sentiment plugins (stub).

Mirrors `server/internal/domain/strategy/plugins/catalog.go`.
"""

from __future__ import annotations

from ..registry import Registry


def register_all(registry: Registry) -> None:
    raise NotImplementedError
