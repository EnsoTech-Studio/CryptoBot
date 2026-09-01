"""Safe DSL-first strategy authoring orchestration."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

from ..errors import ApplicationError
from ..domain.strategy import DeclarativeStrategy
from ..infrastructure.ai import StrategyDesignUnavailable
from ..infrastructure.news.rss import NewsProviderError, _pinned_https_get
from ..infrastructure.news.security import assert_public_https, sanitize_text
from ..schemas import StrategyApprovalIn, StrategyDraftCreateIn, StrategySpecResponse

_INDICATOR_ALIASES = {
    "bollinger_bands": "bollinger",
    "bollinger bands": "bollinger",
    "support/resistance": "support_resistance",
    "s/r": "support_resistance",
}
_ALLOWED_INDICATORS = {"sma", "ema", "rsi", "bollinger", "macd", "support_resistance"}
_FORBIDDEN = re.compile(r"(?:__import__|subprocess|socket|requests|urllib|eval\s*\(|exec\s*\(|SELECT\s|INSERT\s)", re.I)
_COMPARISON_OPERATORS = {"crosses_above", "crosses_below", "above", "below", "equals"}
_MAX_DESIGN_ATTEMPTS = 3


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def normalize_spec(spec: StrategySpecResponse) -> StrategySpecResponse:
    """Keep accepted indicator aliases executable by the runtime interpreter."""
    indicators = []
    for indicator in spec.indicators:
        item = dict(indicator)
        kind = str(item.get("kind", "")).strip().lower()
        item["kind"] = _INDICATOR_ALIASES.get(kind, kind)
        indicators.append(item)
    return spec.model_copy(update={"indicators": indicators})


def validate_spec(spec: StrategySpecResponse) -> None:
    if spec.schema_version != "strategy-spec/v1":
        raise ApplicationError("invalid_strategy_spec", "unsupported strategy spec version", 422)
    if not spec.strategy_id.startswith("generated.") or len(spec.strategy_id) > 48:
        raise ApplicationError("invalid_strategy_spec", "generated strategy id must use generated.*", 422)
    if not {"long_entry", "short_entry", "exit"}.issubset(spec.rules):
        raise ApplicationError("invalid_strategy_spec", "strategy must define entry and exit rules", 422)
    if not spec.indicators:
        raise ApplicationError("invalid_strategy_spec", "strategy must define an indicator", 422)
    references = {"close"}
    for indicator in spec.indicators:
        kind = str(indicator.get("kind", "")).strip().lower()
        kind = _INDICATOR_ALIASES.get(kind, kind)
        if kind not in _ALLOWED_INDICATORS:
            raise ApplicationError("invalid_strategy_spec", f"indicator {kind!r} is not supported", 422)
        name = str(indicator.get("id") or kind).strip()
        if not name or name in references:
            raise ApplicationError("invalid_strategy_spec", "indicator ids must be unique", 422)
        references.add(name)
        if kind == "support_resistance":
            references.update({f"{name}.support", f"{name}.resistance"})
        elif kind == "macd":
            references.update({f"{name}.signal", f"{name}.hist"})
    encoded = _canonical(spec.model_dump())
    if _FORBIDDEN.search(encoded):
        raise ApplicationError("invalid_strategy_spec", "strategy spec contains a forbidden operation", 422)
    _validate_rules(spec.rules, references)
    if spec.warmup_bars < _minimum_warmup(spec):
        raise ApplicationError("invalid_strategy_spec", "warmup_bars is shorter than an indicator period", 422)


def _minimum_warmup(spec: StrategySpecResponse) -> int:
    minimum = 1
    for indicator in spec.indicators:
        kind = _INDICATOR_ALIASES.get(str(indicator.get("kind", "")).strip().lower(), "")
        periods = [indicator.get("period", 14)]
        if kind == "macd":
            periods = [indicator.get("fast", 12), indicator.get("slow", 26), indicator.get("signal", 9)]
        for value in periods:
            if isinstance(value, str) and value.startswith("$"):
                parameter = spec.parameters.get(value[1:], {})
                value = parameter.get("default") if isinstance(parameter, dict) else None
            if isinstance(value, bool):
                value = None
            try:
                period = int(value)
            except (TypeError, ValueError) as exc:
                raise ApplicationError("invalid_strategy_spec", "indicator periods must be positive integers", 422) from exc
            if period < 1:
                raise ApplicationError("invalid_strategy_spec", "indicator periods must be positive integers", 422)
            minimum = max(minimum, period)
    return minimum


def _validate_rules(rules: dict[str, Any], references: set[str]) -> None:
    for name in ("long_entry", "short_entry"):
        _validate_rule(rules[name], references, entry=True)
    _validate_rule(rules["exit"], references, entry=False)


def _validate_rule(rule: Any, references: set[str], *, entry: bool) -> None:
    if isinstance(rule, list):
        if not rule:
            raise ApplicationError("invalid_strategy_spec", "rule groups cannot be empty", 422)
        for item in rule:
            _validate_rule(item, references, entry=entry)
        return
    if not isinstance(rule, dict):
        raise ApplicationError("invalid_strategy_spec", "rules must use declarative objects", 422)
    op = str(rule.get("op", ""))
    if op in {"and", "all", "or", "any"}:
        items = rule.get("items")
        if not isinstance(items, list) or not items:
            raise ApplicationError("invalid_strategy_spec", "rule groups require at least one item", 422)
        for item in items:
            _validate_rule(item, references, entry=entry)
        return
    if op == "opposite_signal" and not entry:
        return
    if op not in _COMPARISON_OPERATORS:
        raise ApplicationError("invalid_strategy_spec", f"rule operation {op!r} is not supported", 422)
    for side in ("left", "right"):
        value = rule.get(side)
        if not isinstance(value, (str, int, float)) or (isinstance(value, str) and value not in references):
            raise ApplicationError("invalid_strategy_spec", f"rule {side} is not an executable reference", 422)


def compile_dsl(spec: StrategySpecResponse) -> str:
    """Emit deterministic data-only Python; raw model text is never a statement."""
    return "# CryptoBot StrategySpec artifact\nSTRATEGY_SPEC = " + repr(spec.model_dump()) + "\n"


def preflight_dsl(spec: StrategySpecResponse, artifact: str) -> dict[str, Any]:
    """Verify the review artifact without executing model-authored code."""
    try:
        tree = ast.parse(artifact, mode="exec")
        statements = [node for node in tree.body if not isinstance(node, ast.Expr)]
        if len(statements) != 1 or not isinstance(statements[0], ast.Assign):
            raise ValueError("artifact must contain exactly one assignment")
        assignment = statements[0]
        if len(assignment.targets) != 1 or not isinstance(assignment.targets[0], ast.Name):
            raise ValueError("artifact assignment is invalid")
        if assignment.targets[0].id != "STRATEGY_SPEC":
            raise ValueError("artifact has an unexpected assignment target")
        compiled_spec = ast.literal_eval(assignment.value)
    except (SyntaxError, ValueError, TypeError) as exc:
        raise ApplicationError("strategy_preflight_failed", "artifact is not data-only", 422) from exc
    if not isinstance(compiled_spec, dict) or _canonical(compiled_spec) != _canonical(spec.model_dump()):
        raise ApplicationError("strategy_preflight_failed", "artifact does not round-trip the frozen spec", 422)
    try:
        runtime = DeclarativeStrategy(compiled_spec)
        runtime.definition()
        runtime.requirements({})
    except (KeyError, TypeError, ValueError) as exc:
        raise ApplicationError("strategy_preflight_failed", "artifact cannot load in the safe runtime", 422) from exc
    return {
        "status": "passed",
        "policy_version": "dsl-policy-v1",
        "fixture_version": "strategy-contract-v1",
        "checks": ["artifact_ast", "spec_round_trip", "safe_runtime"],
    }


def stabilize_generated_id(spec: StrategySpecResponse, _source_hash: str) -> StrategySpecResponse:
    """Make published IDs deterministic and collision-resistant per immutable spec."""
    slug = re.sub(r"[^a-z0-9]+", "-", spec.strategy_id.removeprefix("generated.").lower()).strip("-")
    fingerprint_input = spec.model_dump()
    fingerprint_input.pop("strategy_id", None)
    suffix = _sha256(_canonical(fingerprint_input))[:8]
    max_slug = 48 - len("generated.") - len(suffix) - 1
    slug = slug[:max_slug] or "strategy"
    return spec.model_copy(update={"strategy_id": f"generated.{slug}-{suffix}"})


class StrategyAuthoringService:
    def __init__(self, store: object, designer: object) -> None:
        self._store = store
        self._designer = designer

    def close(self) -> None:
        close = getattr(self._designer, "close", None)
        if close is not None:
            close()

    def create(self, request: StrategyDraftCreateIn, correlation_id: str | None = None) -> dict[str, Any]:
        if request.mode != "dsl":
            raise ApplicationError(
                "custom_python_requires_review", "custom Python authoring is an advanced review path", 422
            )
        source_text = self._source_text(request)
        source_hash = _sha256(source_text)
        if request.source.type == "dsl":
            spec = StrategySpecResponse.model_validate(request.source.spec)
            designer_model = "user-dsl"
            designer_version = "strategy-spec/v1"
            attempts_used = 1
        else:
            designer_model = "openai/gpt-oss-120b"
            designer_version = "groq"
            design_input = source_text
            for attempts_used in range(1, _MAX_DESIGN_ATTEMPTS + 1):
                try:
                    spec = normalize_spec(stabilize_generated_id(self._designer.design(design_input, correlation_id), source_hash))
                    validate_spec(spec)
                    break
                except StrategyDesignUnavailable as exc:
                    raise ApplicationError("strategy_design_unavailable", str(exc), 503) from exc
                except ApplicationError as exc:
                    if attempts_used == _MAX_DESIGN_ATTEMPTS:
                        raise ApplicationError(
                            "strategy_design_invalid", "designer could not produce an executable strategy spec", 422
                        ) from exc
                    design_input = f"{source_text}\n\nValidation feedback: {exc}. Return a corrected strategy-spec/v1 JSON only."
        if request.source.type == "dsl":
            spec = normalize_spec(stabilize_generated_id(spec, source_hash))
            validate_spec(spec)
        artifact = compile_dsl(spec)
        artifact_hash = _sha256(artifact)
        report = preflight_dsl(spec, artifact)
        report_hash = _sha256(_canonical(report))
        return self._store.create_strategy_draft(
            request=request,
            source_hash=source_hash,
            spec=spec.model_dump(),
            artifact=artifact,
            artifact_hash=artifact_hash,
            report=report,
            report_hash=report_hash,
            model=designer_model,
            model_version=designer_version,
            prompt_hash=_sha256(source_text),
            attempts_used=attempts_used,
            correlation_id=correlation_id,
        )

    def get(self, draft_id: UUID, owner_id: UUID) -> dict[str, Any]:
        return self._store.get_strategy_draft(draft_id, owner_id)

    def approve(self, draft_id: UUID, request: StrategyApprovalIn) -> dict[str, Any]:
        return self._store.approve_strategy_draft(draft_id, request)

    @staticmethod
    def _source_text(request: StrategyDraftCreateIn) -> str:
        source = request.source
        if source.type == "text":
            assert source.text is not None
            return source.text.strip()
        if source.type == "dsl":
            assert source.spec is not None
            return _canonical(source.spec)
        assert source.url is not None
        return _fetch_approved_url(source.url)


def _fetch_approved_url(url: str) -> str:
    parsed = urlsplit(url)
    origin = f"https://{(parsed.hostname or '').rstrip('.').lower()}"
    allowed = {
        item.strip().rstrip("/")
        for item in os.getenv("AUTHORING_ALLOWED_ORIGINS", "").split(",")
        if item.strip()
    }
    if origin not in allowed:
        raise ApplicationError("source_rejected", "URL origin is not on the authoring allowlist", 422)
    try:
        host, addresses = assert_public_https(url, origin)
        status, headers, payload = _pinned_https_get(url, host, addresses)
    except (NewsProviderError, ValueError, OSError) as exc:
        raise ApplicationError("source_rejected", "URL failed outbound security validation", 422) from exc
    if status < 200 or status >= 300:
        raise ApplicationError("source_unavailable", "approved URL returned an unusable response", 422)
    content_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type not in {"text/html", "application/xhtml+xml", "text/plain"}:
        raise ApplicationError("source_rejected", "approved URL is not an HTML document", 422)
    text = sanitize_text(payload.decode("utf-8", "replace"), 20_000)
    if len(text) < 40:
        raise ApplicationError("source_rejected", "approved URL did not contain enough readable content", 422)
    return text
