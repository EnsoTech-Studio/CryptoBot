"""Guard the PostgreSQL integration stack against schema drift."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_integration_postgres_mounts_every_canonical_migration() -> None:
    compose = (ROOT / "docker-compose.test.yml").read_text(encoding="utf-8")
    mounted = set(re.findall(r"\./migrations/([^:]+\.sql):", compose))
    canonical = {path.name for path in (ROOT / "migrations").glob("*.sql")}

    assert mounted == canonical
