"""Fail CI when service-ownership boundaries regress."""

from __future__ import annotations

import ast
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
violations: list[str] = []


def source_files(directory: str, suffixes: set[str]) -> list[Path]:
    return [
        path
        for path in (ROOT / directory).rglob("*")
        if path.is_file() and path.suffix in suffixes and "node_modules" not in path.parts
    ]


for retired in (ROOT / "server/internal/lab", ROOT / "server/cmd/worker"):
    if retired.exists() and any(retired.rglob("*.go")):
        violations.append(f"retired Go runtime still exists: {retired.relative_to(ROOT)}")

for path in source_files("server", {".go"}):
    text = path.read_text(encoding="utf-8")
    if "ErrNotImplemented" in text:
        violations.append(f"Go placeholder remains: {path.relative_to(ROOT)}")
    forbidden_domains = (
        "/domain/backtest",
        "/domain/evaluation",
        "/domain/ranking",
        "/domain/strategy",
        "/infrastructure/news",
        "/infrastructure/ai",
    )
    if any(domain in text for domain in forbidden_domains):
        violations.append(f"Go imports research-owned domain: {path.relative_to(ROOT)}")

for path in source_files("web", {".ts", ".tsx", ".js", ".jsx"}):
    text = path.read_text(encoding="utf-8").lower()
    forbidden = (
        "localhost:8000",
        "localhost:8001",
        "research:8001",
        "ai:8000",
        "fapi.binance.com",
        "fstream.binance.com",
    )
    if any(token in text for token in forbidden):
        violations.append(f"browser bypasses Go edge: {path.relative_to(ROOT)}")


# docker-compose.stack.yml is intentionally useful for local full-stack
# rehearsal, while docker-compose.prod.yml is the deployment boundary. Keep
# data, research, and inference ports private in that production overlay.
production_compose = (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
for internal_service in ("postgres", "ai", "research"):
    service_block = re.search(
        rf"(?ms)^  {re.escape(internal_service)}:\n(?:(?!^  [A-Za-z0-9_-]+:\n).)*",
        production_compose,
    )
    if service_block is None or not re.search(r"(?m)^    ports: !reset \[\]$", service_block.group(0)):
        violations.append(f"production exposes internal service port: {internal_service}")

for path in source_files("app", {".py"}):
    text = path.read_text(encoding="utf-8")
    if "status_code=501" in text or "ERR_NOT_IMPLEMENTED" in text:
        violations.append(f"research placeholder remains: {path.relative_to(ROOT)}")
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        violations.append(f"invalid Python syntax: {path.relative_to(ROOT)}: {exc}")
        continue
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        if any(name.split(".", 1)[0] in {"binance", "ccxt"} for name in names):
            violations.append(f"research imports exchange adapter: {path.relative_to(ROOT)}")

if violations:
    raise SystemExit("architecture ownership violations:\n- " + "\n- ".join(sorted(set(violations))))

print("architecture ownership scan passed")
