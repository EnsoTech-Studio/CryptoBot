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


def test_queue_scale_proof_keeps_the_immutable_experiment_replay_range() -> None:
    proof = (ROOT / "scripts" / "queue-scale-proof.sql").read_text(encoding="utf-8")
    assert "replay_range_from,replay_range_to" in proof
