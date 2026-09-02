"""Filesystem boundary for generated strategy artifacts."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID, uuid4


def persist_generated_artifact(draft_id: UUID, revision: int, artifact: str) -> Path:
    """Store an artifact outside source/plugin directories with a private mode."""
    root = Path(os.getenv("GENERATED_STRATEGY_DIR", ".runtime/generated-strategies")).resolve()
    directory = (root / str(draft_id)).resolve()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    os.chmod(directory, 0o700)
    if root not in directory.parents:
        raise ValueError("generated artifact path escaped its safe root")
    target = directory / f"revision-{revision}.py"
    temporary = directory / f".{target.name}.{uuid4().hex}.tmp"
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            descriptor = -1
            handle.write(artifact)
        os.replace(temporary, target)
    finally:
        if descriptor != -1:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)
    return target
