"""Trusted, version-controlled LLM system prompts."""

from __future__ import annotations

from pathlib import Path

import yaml


_PROMPT_DIR = Path(__file__).resolve().parents[2] / "config" / "prompts"
_PROMPTS = {
    "news_sentiment",
    "news_aggregate_sentiment",
    "news_extraction",
    "news_strategy_analysis",
    "strategy_design",
    "strategy_python_repair",
}


def load_system_prompt(name: str) -> str:
    if name not in _PROMPTS:
        raise ValueError(f"unknown system prompt: {name}")
    path = _PROMPT_DIR / f"{name}.yaml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"system prompt file is invalid: {name}")
    value = str(payload.get("system", "")).strip()
    if not value:
        raise RuntimeError(f"system prompt is empty: {name}")
    return value
