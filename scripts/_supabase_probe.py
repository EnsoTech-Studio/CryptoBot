"""Temporary probe: report Supabase schema-migration state."""

from __future__ import annotations

import sys
from pathlib import Path

import psycopg


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def main() -> int:
    env = load_env(Path(".env"))
    files = sorted(p.name for p in Path("migrations").glob("*.sql"))
    with psycopg.connect(env["MIGRATION_DATABASE_URL"], connect_timeout=10) as conn:
        exists = conn.execute(
            "SELECT to_regclass('public.schema_migrations') IS NOT NULL"
        ).fetchone()[0]
        applied: list[str] = []
        if exists:
            applied = [
                r[0]
                for r in conn.execute(
                    "SELECT version FROM public.schema_migrations ORDER BY version"
                ).fetchall()
            ]
        roles = [
            r[0]
            for r in conn.execute(
                "SELECT rolname FROM pg_roles WHERE rolname IN"
                " ('api_runtime','research_runtime','api_reader','research_service','api_service')"
                " ORDER BY rolname"
            ).fetchall()
        ]
        counts = {}
        for table in ("users", "market_pairs", "market_datasets", "strategies", "candles"):
            reg = conn.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{table}",)).fetchone()[0]
            if reg:
                counts[table] = conn.execute(f"SELECT count(*) FROM public.{table}").fetchone()[0]
            else:
                counts[table] = "missing"

    print(f"schema_migrations table: {'present' if exists else 'absent'}")
    print(f"migration files on disk : {len(files)}")
    print(f"applied in database     : {len(applied)}")
    pending = [f for f in files if f not in applied]
    print(f"pending                 : {pending if pending else 'none'}")
    unknown = [a for a in applied if a not in files]
    if unknown:
        print(f"applied but missing on disk: {unknown}")
    print(f"roles present           : {roles}")
    print(f"row counts              : {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
