"""Guard the PostgreSQL integration stack against schema drift."""

from __future__ import annotations

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_integration_postgres_mounts_every_canonical_migration() -> None:
    compose = (ROOT / "docker-compose.test.yml").read_text(encoding="utf-8")
    mounted = set(re.findall(r"\./migrations/([^:]+\.sql):", compose))
    canonical = {path.name for path in (ROOT / "migrations").glob("*.sql")}

    assert mounted == canonical


def test_queue_scale_proof_keeps_the_immutable_experiment_replay_range() -> None:
    proof = (ROOT / "scripts" / "queue-scale-proof.sql").read_text(encoding="utf-8")
    assert "replay_range_from,replay_range_to" in proof


def test_production_compose_keeps_internal_services_private() -> None:
    compose = (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")

    for service in ("postgres", "ai", "research"):
        match = re.search(
            rf"(?ms)^  {re.escape(service)}:\n(?:(?!^  [A-Za-z0-9_-]+:\n).)*",
            compose,
        )
        assert match is not None, f"missing production override for {service}"
        assert re.search(r"(?m)^    ports: !reset \[\]$", match.group(0)), (
            f"{service} must not expose a host port in production"
        )


def test_event_outbox_lease_configuration_is_positive_and_has_a_safe_default(
    monkeypatch,
) -> None:
    from app.config import Settings

    monkeypatch.delenv("EVENT_LEASE_SECONDS", raising=False)
    assert Settings.from_env().event_lease_s == 60

    monkeypatch.setenv("EVENT_LEASE_SECONDS", "17")
    assert Settings.from_env().event_lease_s == 17

    monkeypatch.setenv("EVENT_LEASE_SECONDS", "0")
    with pytest.raises(ValueError, match="EVENT_LEASE_SECONDS must be greater than zero"):
        Settings.from_env()
