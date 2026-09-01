# Seed seam

Runtime seed data is intentionally absent. The backend must not manufacture
market, sentiment, or backtest fixtures at startup.

For the manual news/LLM demonstration, run `uv run python -m scripts.news_llm_demo`
from the repository root after the AI service is running. It upserts three inactive
demo sources, routes their mock HTML through the normal Groq extraction and
sentiment paths, and prints the aggregate LLM insight. It never runs on startup.

