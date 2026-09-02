"""Checksum-verified PostgreSQL migration runner.

Normal API and worker processes never execute DDL. A dedicated startup command
runs this module before either runtime starts (native development or full-stack
Compose).
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sys
import time

import psycopg
from psycopg import sql


_LOCK_NAME = "cryptobot-schema-migrations-v1"


def _ensure_runtime_logins(connection: psycopg.Connection[object]) -> None:
    roles = (
        (
            os.getenv("RESEARCH_DATABASE_USER", "research_service").strip(),
            os.getenv("RESEARCH_DATABASE_PASSWORD", "").strip(),
            "research_runtime",
        ),
        (
            os.getenv("API_DATABASE_USER", "api_service").strip(),
            os.getenv("API_DATABASE_PASSWORD", "").strip(),
            "api_runtime",
        ),
    )
    for role_name, password, membership in roles:
        if not role_name or not password:
            continue
        exists = connection.execute(
            "SELECT 1 FROM pg_roles WHERE rolname=%s", (role_name,)
        ).fetchone()
        if exists is None:
            connection.execute(
                sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                    sql.Identifier(role_name), sql.Literal(password)
                )
            )
        else:
            connection.execute(
                sql.SQL("ALTER ROLE {} LOGIN PASSWORD {}").format(
                    sql.Identifier(role_name), sql.Literal(password)
                )
            )
        connection.execute(
            sql.SQL("GRANT {} TO {}").format(
                sql.Identifier(membership), sql.Identifier(role_name)
            )
        )


def _migration_dir() -> Path:
    configured = os.getenv("MIGRATIONS_DIR", "").strip()
    return Path(configured) if configured else Path(__file__).resolve().parents[1] / "migrations"


def _connect_with_retry(database_url: str) -> psycopg.Connection[object]:
    attempts = max(1, int(os.getenv("MIGRATION_CONNECT_RETRIES", "8")))
    delay = max(0.1, float(os.getenv("MIGRATION_CONNECT_RETRY_DELAY_SECONDS", "2")))
    last_error: psycopg.OperationalError | None = None
    for attempt in range(attempts):
        try:
            return psycopg.connect(
                database_url,
                autocommit=False,
                connect_timeout=5,
                prepare_threshold=None,
            )
        except psycopg.OperationalError as exc:
            last_error = exc
            if attempt == attempts - 1:
                break
            wait_seconds = min(delay * (2 ** attempt), 15.0)
            print(
                f"database connection failed; retrying in {wait_seconds:.1f}s "
                f"({attempt + 1}/{attempts})",
                file=sys.stderr,
            )
            time.sleep(wait_seconds)
    assert last_error is not None
    raise last_error


def migrate() -> list[str]:
    database_url = os.getenv("MIGRATION_DATABASE_URL", os.getenv("DATABASE_URL", "")).strip()
    if not database_url:
        raise RuntimeError("MIGRATION_DATABASE_URL or DATABASE_URL is required")

    migration_dir = _migration_dir()
    files = sorted(migration_dir.glob("*.sql"))
    if not files:
        raise RuntimeError(f"no SQL migrations found in {migration_dir}")

    applied: list[str] = []
    with _connect_with_retry(database_url) as connection:
        connection.execute("SELECT pg_advisory_lock(hashtext(%s))", (_LOCK_NAME,))
        try:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS public.schema_migrations (
                    version TEXT PRIMARY KEY,
                    checksum CHAR(64) NOT NULL,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            connection.commit()

            for path in files:
                payload = path.read_bytes()
                checksum = hashlib.sha256(payload).hexdigest()
                existing = connection.execute(
                    "SELECT checksum FROM public.schema_migrations WHERE version = %s",
                    (path.name,),
                ).fetchone()
                if existing:
                    if existing[0].strip() != checksum:
                        raise RuntimeError(f"applied migration changed: {path.name}")
                    connection.commit()
                    if path.name == "003_integrity_and_roles.sql":
                        _ensure_runtime_logins(connection)
                        connection.commit()
                    continue

                try:
                    connection.execute(payload.decode("utf-8-sig"))
                    connection.execute(
                        "INSERT INTO public.schema_migrations(version, checksum) VALUES (%s, %s)",
                        (path.name, checksum),
                    )
                    connection.commit()
                    if path.name == "003_integrity_and_roles.sql":
                        _ensure_runtime_logins(connection)
                        connection.commit()
                except Exception:
                    connection.rollback()
                    raise
                applied.append(path.name)
        finally:
            connection.execute("SELECT pg_advisory_unlock(hashtext(%s))", (_LOCK_NAME,))
            connection.commit()
    return applied


def main() -> int:
    applied = migrate()
    print("migrations applied:", ", ".join(applied) if applied else "none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
