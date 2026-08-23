"""Canonical JSON + hashing for immutable snapshot/candidate/result hashes.

Mirrors `server/internal/domain/common/canonical.go`. Canonicalization rules
(float64 backend, rule R1 of `specs/python-research.md`):

- object keys sorted lexicographically (no unordered iteration);
- compact separators, no whitespace;
- `datetime` → ISO-8601 UTC; `UUID` → lowercase hex string;
- dataclasses serialize by field name;
- floats serialize through Python's shortest round-trip `repr` — deterministic
  for identical float64 inputs on any run of the same interpreter version.

The hash is what makes AC-01 ("5 lần chạy cho cùng canonical result hash")
checkable: same facts in, same sha256 out.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
from types import NoneType
from uuid import UUID

_TUPLE_TYPES = (list, tuple)


def _normalize(value: object) -> object:
    if value is None or isinstance(value, (bool, int, str, float, NoneType)):
        return value
    if isinstance(value, datetime):
        return value.astimezone(tz=None).isoformat() if value.tzinfo is None else value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {f.name: _normalize(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, dict):
        return {str(k): _normalize(v) for k, v in value.items()}
    if isinstance(value, _TUPLE_TYPES):
        return [_normalize(v) for v in value]
    raise TypeError(f"cannot canonicalize value of type {type(value).__name__}")


def canonical_json(value: object) -> bytes:
    """Serialize `value` to deterministic canonical JSON bytes."""
    return json.dumps(
        _normalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def hash_canonical_json(value: object) -> str:
    """sha256 hex digest of `canonical_json(value)`."""
    return hashlib.sha256(canonical_json(value)).hexdigest()
