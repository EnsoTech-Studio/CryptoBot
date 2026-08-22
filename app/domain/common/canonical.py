"""Canonical JSON + hashing for immutable snapshot/candidate hashes.

Mirrors `server/internal/domain/common/canonical.go`. Production canonicalization
is intentionally deferred; both helpers raise `NotImplementedError`.
"""

from __future__ import annotations

from typing import Any


def canonical_json(value: Any) -> bytes:
    raise NotImplementedError


def hash_canonical_json(value: Any) -> str:
    raise NotImplementedError
