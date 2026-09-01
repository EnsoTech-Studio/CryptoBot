from dataclasses import dataclass
import json
import os
import re
from collections.abc import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .prompts import load_system_prompt


@dataclass
class Prediction:
    label: str
    score: float
    model: str
    model_version: str


@dataclass
class NewsExtraction:
    title: str
    body: str
    model: str
    model_version: str


Requester = Callable[[Request, float], bytes]


def _request(request: Request, timeout: float) -> bytes:
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 — URL is configured server-side
        return response.read(1 << 20)


class Predictor:
    """Groq-backed sentiment adapter.

    The AI service owns inference only. It returns a strict, small JSON
    contract; research validates it again before persistence. There is no
    keyword fallback because fabricated sentiment is worse than an honest
    unavailable result.
    """

    def __init__(self, requester: Requester = _request) -> None:
        self._requester = requester

    @property
    def model(self) -> str:
        configured = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()
        return "openai/" + configured if configured == "gpt-oss-120b" else configured

    @property
    def model_version(self) -> str:
        return os.getenv("SENTIMENT_MODEL_VERSION", "groq-2026-08-31").strip()

    def _complete_json(
        self,
        *,
        messages: list[dict[str, str]],
        name: str,
        schema: dict[str, object],
        max_tokens: int,
    ) -> dict[str, object]:
        api_key = os.getenv("GROQ_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not configured")
        base_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
        payload = {
            "model": self.model,
            "temperature": 0,
            "max_completion_tokens": max_tokens,
            "messages": messages,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": name, "strict": True, "schema": schema},
            },
        }
        request = Request(
            f"{base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "CryptoBot-AI/1.0",
            },
            method="POST",
        )
        try:
            raw = self._requester(request, float(os.getenv("GROQ_TIMEOUT_SECONDS", "10")))
            response = json.loads(raw)
            content = response["choices"][0]["message"]["content"]
            result = json.loads(content)
            if not isinstance(result, dict):
                raise ValueError("structured response must be an object")
            return result
        except (HTTPError, URLError, TimeoutError, OSError, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("Groq structured inference failed") from exc

    def predict(self, text: str) -> Prediction:
        return self._predict_sentiment(text, prompt_name="news_sentiment", operation="crypto_sentiment")

    def predict_aggregate(self, text: str) -> Prediction:
        return self._predict_sentiment(
            text, prompt_name="news_aggregate_sentiment", operation="crypto_news_aggregate_sentiment"
        )

    def _predict_sentiment(self, text: str, *, prompt_name: str, operation: str) -> Prediction:
        normalized = text.strip()
        if not normalized or len(normalized) > 10_000:
            raise RuntimeError("sentiment text must contain 1..10000 characters")
        result = self._complete_json(
            messages=[
                {"role": "system", "content": load_system_prompt(prompt_name)},
                {"role": "user", "content": normalized},
            ],
            name=operation,
            schema={
                "type": "object",
                "properties": {
                    "label": {"type": "string", "enum": ["POSITIVE", "NEUTRAL", "NEGATIVE"]},
                    "score": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["label", "score"],
                "additionalProperties": False,
            },
            max_tokens=200,
        )
        try:
            label = result["label"]
            score = float(result["score"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("Groq returned an invalid sentiment contract") from exc
        if label not in {"POSITIVE", "NEUTRAL", "NEGATIVE"} or not 0 <= score <= 1:
            raise RuntimeError("Groq returned an invalid sentiment contract")
        return Prediction(label, score, self.model, self.model_version)

    def design(self, text: str) -> dict[str, object]:
        normalized = text.strip()
        if not normalized or len(normalized) > 10_000:
            raise RuntimeError("strategy source must contain 1..10000 characters")
        envelope = self._complete_json(
            messages=[
                {"role": "system", "content": load_system_prompt("strategy_design")},
                {"role": "user", "content": normalized},
            ],
            name="strategy_spec",
            schema={
                "type": "object",
                "properties": {
                    "spec_json": {"type": "string", "minLength": 2, "maxLength": 10_000},
                },
                "required": ["spec_json"],
                "additionalProperties": False,
            },
            max_tokens=1_200,
        )
        raw_spec = envelope.get("spec_json")
        if not isinstance(raw_spec, str):
            raise RuntimeError("Groq returned an invalid strategy envelope")
        try:
            parsed_spec = json.loads(raw_spec)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Groq returned an invalid strategy JSON") from exc
        if not isinstance(parsed_spec, dict):
            raise RuntimeError("Groq returned an invalid strategy JSON")
        return _canonicalize_strategy_spec(parsed_spec)

    def repair_python(self, artifact: str, error_code: str) -> str:
        if not artifact.strip() or len(artifact) > 20_000 or not error_code.strip():
            raise RuntimeError("strategy repair input is outside bounds")
        result = self._complete_json(
            messages=[
                {"role": "system", "content": load_system_prompt("strategy_python_repair")},
                {"role": "user", "content": json.dumps({"artifact": artifact, "error_code": error_code})},
            ],
            name="strategy_python_repair",
            schema={
                "type": "object",
                "properties": {"artifact": {"type": "string", "minLength": 1, "maxLength": 20_000}},
                "required": ["artifact"],
                "additionalProperties": False,
            },
            max_tokens=4_000,
        )
        repaired = result.get("artifact")
        if not isinstance(repaired, str) or not repaired.strip() or len(repaired) > 20_000:
            raise RuntimeError("Groq returned an invalid strategy repair contract")
        return repaired.strip()

    def extract_news(self, text: str) -> NewsExtraction:
        normalized = text.strip()
        if not normalized or len(normalized) > 20_000:
            raise RuntimeError("sanitized document must contain 1..20000 characters")
        result = self._complete_json(
            messages=[
                {"role": "system", "content": load_system_prompt("news_extraction")},
                {"role": "user", "content": normalized},
            ],
            name="news_extraction",
            schema={
                "type": "object",
                "properties": {"title": {"type": "string"}, "body": {"type": "string"}},
                "required": ["title", "body"],
                "additionalProperties": False,
            },
            max_tokens=1_200,
        )
        title, body = result.get("title"), result.get("body")
        if not isinstance(title, str) or not isinstance(body, str) or not title.strip() or len(body.strip()) < 40:
            raise RuntimeError("Groq returned an invalid news extraction contract")
        return NewsExtraction(title.strip(), body.strip(), self.model, self.model_version)


def _canonicalize_strategy_spec(result: dict[str, object]) -> dict[str, object]:
    """Normalize harmless model-shape drift into the versioned DSL contract."""
    parameters = result.get("parameters")
    normalized_parameters = {
        str(name): value if isinstance(value, dict) else {"default": value}
        for name, value in parameters.items()
    } if isinstance(parameters, dict) else {}
    raw_indicators = result.get("indicators")
    if isinstance(raw_indicators, dict):
        raw_indicators = [
            {**definition, "id": identifier}
            for identifier, definition in raw_indicators.items()
            if isinstance(definition, dict)
        ]
    if not isinstance(raw_indicators, list) or not raw_indicators:
        raise ValueError("strategy response has no indicators")
    indicators: list[dict[str, object]] = []
    periods: list[int] = []
    for raw in raw_indicators:
        if not isinstance(raw, dict):
            raise ValueError("strategy indicator is not an object")
        kind = str(raw.get("kind") or raw.get("type") or "").strip().lower().replace(" ", "_")
        if kind == "bollinger_bands":
            kind = "bollinger"
        if kind in {"support/resistance", "s/r"}:
            kind = "support_resistance"
        if kind not in {"sma", "ema", "rsi", "bollinger", "macd", "support_resistance"}:
            raise ValueError("strategy response contains an unsupported indicator")
        params = raw.get("params") if isinstance(raw.get("params"), dict) else raw
        item: dict[str, object] = {"id": str(raw.get("id") or raw.get("name") or raw.get("alias") or kind), "kind": kind}
        if isinstance(params, dict):
            for key in ("period", "deviation", "fast", "slow", "signal", "band"):
                if key in params and isinstance(params[key], (int, float, str)):
                    item[key] = params[key]
            period = params.get("period")
            if isinstance(period, (int, float)):
                periods.append(int(period))
        if "period" not in item:
            for parameter_name in (f"{item['id']}_period", f"{item['id']}_length"):
                if parameter_name in normalized_parameters:
                    item["period"] = "$" + parameter_name
                    default = normalized_parameters[parameter_name].get("default")
                    if isinstance(default, (int, float)):
                        periods.append(int(default))
                    break
        indicators.append(item)
    raw_rules = result.get("rules") if isinstance(result.get("rules"), dict) else result
    entry = result.get("entry")
    if not isinstance(entry, dict):
        entry = raw_rules.get("entry") if isinstance(raw_rules.get("entry"), dict) else {}
    long_rule = raw_rules.get("long_entry")
    short_rule = raw_rules.get("short_entry")
    if long_rule is None:
        long_rule = entry.get("long")
    if short_rule is None:
        short_rule = entry.get("short")
    rules = {
        "long_entry": _legacy_rule(long_rule),
        "short_entry": _legacy_rule(short_rule),
        "exit": {"op": "opposite_signal"},
    }
    strategy_id = str(result.get("strategy_id") or result.get("name") or "generated.strategy")
    strategy_id = re.sub(r"[^a-zA-Z0-9._-]+", "-", strategy_id)
    if not strategy_id.startswith("generated."):
        strategy_id = "generated." + strategy_id.removeprefix("generated_")
    family = _family_for(indicators)
    suggested_warmup = result.get("warmup_bars")
    warmup_bars = suggested_warmup if isinstance(suggested_warmup, int) and not isinstance(suggested_warmup, bool) else 1
    return {
        "schema_version": "strategy-spec/v1",
        "strategy_id": strategy_id,
        "display_name": str(result.get("display_name") or result.get("name") or strategy_id.removeprefix("generated.")),
        "family": family,
        "description": str(result.get("description") or "Generated declarative strategy."),
        "parameters": normalized_parameters,
        "indicators": indicators,
        "rules": rules,
        "warmup_bars": max(*(periods or [1]), warmup_bars),
    }


def _legacy_rule(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        raw_operation = str(value.get("op") or value.get("type") or value.get("condition") or "").lower()
        operation = {
            "crossover": "crosses_above", "crossunder": "crosses_below",
            "lt": "below", "less_than": "below", "<": "below",
            "gt": "above", "greater_than": "above", ">": "above",
        }.get(raw_operation, raw_operation)
        left, right = value.get("left"), value.get("right")
        if isinstance(left, dict) and isinstance(left.get("indicator"), str):
            left = left["indicator"]
        if isinstance(right, dict) and isinstance(right.get("indicator"), str):
            right = right["indicator"]
        if isinstance(left, dict) and isinstance(left.get("value"), (str, int, float)):
            left = left["value"]
        if isinstance(right, dict) and isinstance(right.get("value"), (str, int, float)):
            right = right["value"]
        if operation in {"crosses_above", "crosses_below", "above", "below", "equals"} and isinstance(left, (str, int, float)) and isinstance(right, (str, int, float)):
            return {"op": operation, "left": left, "right": right}
        condition = str(value.get("condition", ""))
    else:
        condition = str(value or "")
    match = re.search(r"\b(crossover|crossunder)\s*\(\s*([A-Za-z0-9_.-]+)\s*,\s*([A-Za-z0-9_.-]+)\s*\)", condition, re.I)
    if match:
        operation = "crosses_above" if match.group(1).lower() == "crossover" else "crosses_below"
        return {"op": operation, "left": match.group(2).removesuffix(".value"), "right": match.group(3).removesuffix(".value")}
    raise ValueError("unsupported legacy condition")


def _family_for(indicators: list[dict[str, object]]) -> str:
    kinds = {str(item.get("kind")) for item in indicators}
    if kinds & {"sma", "ema"}:
        return "trend"
    if "bollinger" in kinds:
        return "volatility"
    if "support_resistance" in kinds:
        return "structure"
    return "momentum"


predictor = Predictor()
