"""Internal FastAPI service for canonical research-domain behavior."""

from __future__ import annotations

import csv
import hashlib
import inspect
import json
import logging
import threading
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from io import StringIO
from typing import Annotated, Any
from uuid import UUID, uuid4

import psycopg
from fastapi import Depends, FastAPI, Header, Query, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse

from .config import Settings
from .domain.common import ERR_UNKNOWN_STRATEGY, DomainError, hash_canonical_json
from .domain.strategy import Definition
from .domain.strategy.plugins import default_registry
from .errors import ApplicationError
from .infrastructure.ai import NewsExtractionHTTPAdapter, StrategyDesignHTTPAdapter
from .infrastructure.postgres.store import Store
from .infrastructure.news import HtmlNewsProvider, RssNewsProvider, SsrfBlocked, assert_public_https
from .infrastructure.sentiment import (
    ContractViolation,
    SentimentHTTPAdapter,
    SentimentUnavailable,
)
from .internal_auth import require_internal_service
from .schemas import (
    AcceptedRunOut,
    CandleOut,
    EquityPointOut,
    ExecutionMarkerOut,
    ExperimentCreateIn,
    ExperimentSummaryOut,
    LeaderboardEntryOut,
    NewsAggregateOut,
    NewsCollectIn,
    NewsItemOut,
    NewsSourceCreateIn,
    ScorePolicyCreateIn,
    SearchActionIn,
    SearchRunCreateIn,
    SearchRunOut,
    SentimentBackfillIn,
    SentimentPredictIn,
    SentimentPredictOut,
    StrategyOut,
    StrategyDraftActionIn,
    StrategyApprovalIn,
    StrategyDraftCreateIn,
    StrategyDraftOut,
    TradePageOut,
)
from .services.news import NewsService
from .services.authoring import StrategyAuthoringService
from .services.chart_overlays import build_chart_overlay_delta, build_chart_overlays

_registry = default_registry()


def _definition_payload(definition: Definition) -> dict[str, Any]:
    strategy = _registry.resolve(definition.strategy_id, definition.version)
    source = inspect.getsource(type(strategy)).encode("utf-8")
    metadata = {
        "strategy_id": definition.strategy_id,
        "version": definition.version,
        "family": definition.family,
        "parameters_schema": definition.parameters_schema or {},
        "input_requirements": definition.input_requirements,
        "overlay_types": definition.overlay_types,
    }
    fingerprint = hashlib.sha256(source + hash_canonical_json(metadata).encode("ascii")).hexdigest()
    warm_up = definition.warm_up_candles({}) if callable(definition.warm_up_candles) else 0
    return {
        **metadata,
        "display_name": definition.display_name,
        "description": definition.description,
        "warm_up_candles": int(warm_up or 0),
        "is_composite": definition.is_composite,
        "code_fingerprint": fingerprint,
        "default_params": {},
    }


_strategy_payloads = [_definition_payload(item) for item in _registry.list()]
_builtin_warmups = {
    (item["strategy_id"], item["version"]): item["warm_up_candles"]
    for item in _strategy_payloads
}


@asynccontextmanager
async def lifespan(application: FastAPI):
    try:
        store = Store(Settings.from_env().database_url)
        store.sync_strategies(_strategy_payloads)
        application.state.store = store
        application.state.registry_sync_error = None
    except Exception as exc:  # readiness exposes failure; health remains live
        application.state.registry_sync_error = type(exc).__name__
    yield
    service = getattr(application.state, "news_service", None)
    if service is not None:
        service.close()
    service = getattr(application.state, "authoring_service", None)
    if service is not None:
        service.close()


app = FastAPI(
    title="CryptoBot Research Service",
    version="1.0.0",
    description="Internal strategy, backtest, evaluation, search, ranking, news and sentiment API.",
    lifespan=lifespan,
)
_logger = logging.getLogger("cryptobot.research")
_logger.setLevel(logging.INFO)
_metrics_lock = threading.Lock()
_request_counts: dict[tuple[str, str, int], int] = {}
_request_duration_seconds: dict[tuple[str, str], float] = {}


def _store(request: Request) -> Store:
    store = getattr(request.app.state, "store", None)
    if store is None:
        store = Store(Settings.from_env().database_url)
        request.app.state.store = store
    return store


def _news_service(request: Request) -> NewsService:
    service = getattr(request.app.state, "news_service", None)
    if service is None:
        settings = Settings.from_env()
        analyzer = SentimentHTTPAdapter(settings.ai_service_url, settings.ai_timeout_s)
        service = NewsService(
            _store(request), {"rss": RssNewsProvider(), "url": HtmlNewsProvider()}, analyzer,
            NewsExtractionHTTPAdapter(
                settings.ai_service_url, settings.ai_timeout_s,
                model=settings.sentiment_model, model_version=settings.sentiment_model_version,
            ),
        )
        request.app.state.news_service = service
    return service


def _authoring_service(request: Request) -> StrategyAuthoringService:
    service = getattr(request.app.state, "authoring_service", None)
    if service is None:
        settings = Settings.from_env()
        service = StrategyAuthoringService(
            _store(request),
            StrategyDesignHTTPAdapter(settings.ai_service_url, settings.ai_timeout_s),
        )
        request.app.state.authoring_service = service
    return service


def _owner_id(x_user_id: Annotated[str | None, Header()] = None) -> UUID:
    try:
        return UUID(x_user_id or "")
    except ValueError as exc:
        raise ApplicationError("user_context_required", "valid X-User-ID header required", 401) from exc


def _admin_role(x_user_role: Annotated[str | None, Header()] = None) -> None:
    if x_user_role != "ADMIN":
        raise ApplicationError("forbidden", "ADMIN role required", 403)


Internal = Annotated[None, Depends(require_internal_service)]
OwnerID = Annotated[UUID, Depends(_owner_id)]
Admin = Annotated[None, Depends(_admin_role)]


@app.middleware("http")
async def request_boundary(request: Request, call_next: Any) -> Response:
    started = time.perf_counter()
    request_id = request.headers.get("X-Request-ID", "").strip()[:128] or str(uuid4())
    request.state.request_id = request_id
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            too_large = int(content_length) > Settings.from_env().max_request_bytes
        except ValueError:
            too_large = True
        if too_large:
            return JSONResponse(
                status_code=413,
                content={
                    "code": "request_too_large",
                    "message": "request body exceeds configured limit",
                    "request_id": request_id,
                },
                headers={"X-Request-ID": request_id},
            )
    response_status = 500
    try:
        response = await call_next(request)
        response_status = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        duration = time.perf_counter() - started
        route = getattr(request.scope.get("route"), "path", request.url.path)
        with _metrics_lock:
            count_key = (request.method, route, response_status)
            _request_counts[count_key] = _request_counts.get(count_key, 0) + 1
            duration_key = (request.method, route)
            _request_duration_seconds[duration_key] = (
                _request_duration_seconds.get(duration_key, 0.0) + duration
            )
        _logger.info(
            json.dumps(
                {
                    "timestamp": datetime.now(tz=UTC).isoformat(),
                    "level": "info" if response_status < 500 else "error",
                    "service": "research",
                    "operation": route,
                    "method": request.method,
                    "status": response_status,
                    "duration_ms": round(duration * 1000, 3),
                    "request_id": request_id,
                    "correlation_id": request.headers.get("X-Correlation-ID") or request_id,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )


@app.exception_handler(ApplicationError)
async def application_error(request: Request, exc: ApplicationError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "field": exc.field,
            "request_id": request.state.request_id,
        },
    )


@app.exception_handler(psycopg.Error)
async def database_error(request: Request, exc: psycopg.Error) -> JSONResponse:
    _logger.error(
        "database operation failed error_type=%s sqlstate=%s request_id=%s",
        type(exc).__name__,
        exc.sqlstate,
        request.state.request_id,
    )
    return JSONResponse(
        status_code=503,
        content={
            "code": "database_unavailable",
            "message": "research persistence is temporarily unavailable",
            "request_id": request.state.request_id,
        },
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "research", "numeric": "float64"}


@app.get("/ready")
def ready(request: Request) -> JSONResponse:
    try:
        checks = _store(request).ready()
        checks["strategy_registry"] = getattr(request.app.state, "registry_sync_error", None) is None
        ready_now = all(checks.values())
    except Exception:  # noqa: BLE001 - readiness must return a bounded response
        checks = {"database": False, "active_score_policy": False, "strategy_registry": False}
        ready_now = False
    return JSONResponse(
        status_code=200 if ready_now else 503,
        content={"status": "ready" if ready_now else "not_ready", "checks": checks},
    )


@app.get("/metrics", response_class=PlainTextResponse)
def metrics(request: Request, _auth: Internal) -> str:
    lines = [
        "# TYPE cryptobot_research_http_requests_total counter",
        "# TYPE cryptobot_research_http_request_duration_seconds_total counter",
    ]
    with _metrics_lock:
        counts = dict(_request_counts)
        durations = dict(_request_duration_seconds)
    for (method, route, response_status), value in sorted(counts.items()):
        lines.append(
            "cryptobot_research_http_requests_total"
            f'{{method="{method}",route="{route}",status="{response_status}"}} {value}'
        )
    for (method, route), value in sorted(durations.items()):
        lines.append(
            "cryptobot_research_http_request_duration_seconds_total"
            f'{{method="{method}",route="{route}"}} {value:.9f}'
        )
    for name, value in sorted(_store(request).operational_metrics().items()):
        lines.append(f"cryptobot_{name} {value:.9f}")
    return "\n".join(lines) + "\n"


@app.get("/api/v1/strategies", response_model=dict[str, list[StrategyOut]])
def list_strategies(_auth: Internal, request: Request) -> dict[str, list[dict[str, Any]]]:
    try:
        strategies = _store(request).list_strategies()
        return {
            "strategies": [
                {
                    **strategy,
                    "warm_up_candles": _builtin_warmups.get(
                        (strategy["strategy_id"], strategy["version"]),
                        strategy["warm_up_candles"],
                    ),
                }
                for strategy in strategies
            ]
        }
    except Exception:
        return {"strategies": _strategy_payloads}


@app.get("/api/v1/markets/chart-overlays")
def chart_overlays(
    _auth: Internal,
    request: Request,
    provider: Annotated[str, Query(min_length=1)] = "binance_usdm",
    symbol: Annotated[str, Query(min_length=1)] = "ETHUSDT",
    timeframe: Annotated[str, Query(min_length=1)] = "5m",
    strategy: Annotated[str, Query(min_length=3)] = "ma_cross@v1",
    limit: Annotated[int, Query(ge=1, le=1_000)] = 1_000,
) -> dict[str, Any]:
    try:
        strategy_id, version = strategy.rsplit("@", 1)
        if not strategy_id or not version:
            raise ValueError
    except ValueError as exc:
        raise ApplicationError("invalid_strategy", "strategy must be strategy_id@version", 422, "strategy") from exc

    store = _store(request)
    try:
        payload = build_chart_overlays(
            store.list_live_candles(provider, symbol, timeframe, limit), strategy_id, version
        )
    except DomainError as exc:
        raise ApplicationError(
            "unknown_strategy_version" if exc.code == ERR_UNKNOWN_STRATEGY else "invalid_strategy",
            "strategy is not available" if exc.code == ERR_UNKNOWN_STRATEGY else exc.message,
            404 if exc.code == ERR_UNKNOWN_STRATEGY else 422,
            "strategy",
        ) from exc
    checkpoint = store.stream_checkpoint(provider, symbol, timeframe)
    return {
        **payload,
        "seq": checkpoint["last_source_sequence"] or 0,
        "last_closed_at": checkpoint["last_closed_at"],
        "is_stale": checkpoint["is_stale"],
    }


@app.get("/api/v1/markets/chart-overlays/delta")
def chart_overlay_delta(
    _auth: Internal,
    request: Request,
    provider: Annotated[str, Query(min_length=1)] = "binance_usdm",
    symbol: Annotated[str, Query(min_length=1)] = "ETHUSDT",
    timeframe: Annotated[str, Query(min_length=1)] = "5m",
    strategy: Annotated[str, Query(min_length=3)] = "ma_cross@v1",
    limit: Annotated[int, Query(ge=1, le=1_000)] = 1_000,
) -> dict[str, Any]:
    try:
        strategy_id, version = strategy.rsplit("@", 1)
        if not strategy_id or not version:
            raise ValueError
    except ValueError as exc:
        raise ApplicationError("invalid_strategy", "strategy must be strategy_id@version", 422, "strategy") from exc

    try:
        return build_chart_overlay_delta(
            _store(request).list_live_candles(provider, symbol, timeframe, limit), strategy_id, version
        )
    except DomainError as exc:
        raise ApplicationError(
            "unknown_strategy_version" if exc.code == ERR_UNKNOWN_STRATEGY else "invalid_strategy",
            "strategy is not available" if exc.code == ERR_UNKNOWN_STRATEGY else exc.message,
            404 if exc.code == ERR_UNKNOWN_STRATEGY else 422,
            "strategy",
        ) from exc


@app.post("/api/v1/strategy-drafts", response_model=StrategyDraftOut, status_code=202)
def create_strategy_draft(
    body: StrategyDraftCreateIn, _auth: Internal, request: Request
) -> JSONResponse:
    result = _authoring_service(request).submit(body, request.state.request_id)
    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content=jsonable_encoder(result))


@app.get("/api/v1/strategy-drafts", response_model=dict[str, list[StrategyDraftOut]])
def list_strategy_drafts(
    _auth: Internal,
    owner_id: OwnerID,
    request: Request,
    limit: Annotated[int, Query(ge=1, le=20)] = 10,
) -> dict[str, list[dict[str, Any]]]:
    return {"drafts": _store(request).list_strategy_drafts(owner_id, limit)}


@app.get("/api/v1/strategy-drafts/{draft_id}", response_model=StrategyDraftOut)
def get_strategy_draft(
    draft_id: UUID, _auth: Internal, owner_id: OwnerID, request: Request
) -> dict[str, Any]:
    return _authoring_service(request).get(draft_id, owner_id)


@app.post("/api/v1/strategy-drafts/{draft_id}/approval", response_model=StrategyDraftOut)
def approve_strategy_draft(
    draft_id: UUID, body: StrategyApprovalIn, _auth: Internal, request: Request
) -> dict[str, Any]:
    return _authoring_service(request).approve(draft_id, body)


@app.post("/api/v1/strategy-drafts/{draft_id}/actions", response_model=StrategyDraftOut)
def act_on_strategy_draft(
    draft_id: UUID, body: StrategyDraftActionIn, _auth: Internal, owner_id: OwnerID, request: Request
) -> dict[str, Any]:
    assert body.action == "cancel"
    return _store(request).cancel_strategy_draft(draft_id, owner_id)


@app.post("/api/v1/experiments", response_model=AcceptedRunOut)
def create_experiment(
    body: ExperimentCreateIn, _auth: Internal, request: Request
) -> JSONResponse:
    result = _store(request).create_experiment(body, request.state.request_id)
    return JSONResponse(
        status_code=status.HTTP_200_OK if result["reused"] else status.HTTP_202_ACCEPTED,
        content=jsonable_encoder(result),
    )


@app.get("/api/v1/experiments/{experiment_id}", response_model=ExperimentSummaryOut)
def get_experiment(
    experiment_id: UUID, _auth: Internal, owner_id: OwnerID, request: Request
) -> dict[str, Any]:
    return _store(request).get_experiment(experiment_id, owner_id)


@app.get("/api/v1/experiments/{experiment_id}/candles", response_model=dict[str, list[CandleOut]])
def get_experiment_candles(
    experiment_id: UUID, _auth: Internal, owner_id: OwnerID, request: Request
) -> dict[str, Any]:
    store = _store(request)
    store.get_experiment(experiment_id, owner_id)
    return {"candles": store.list_experiment_candles(experiment_id)}


@app.get("/api/v1/experiments/{experiment_id}/trades", response_model=TradePageOut)
def get_experiment_trades(
    experiment_id: UUID,
    _auth: Internal,
    owner_id: OwnerID,
    request: Request,
    after_sequence: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    format: Annotated[str | None, Query(pattern="^(csv)?$")] = None,
) -> dict[str, Any]:
    store = _store(request)
    experiment = store.get_experiment(experiment_id, owner_id)
    if format == "csv":
        return StreamingResponse(
            _trade_csv(store, experiment_id, experiment),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="experiment-{experiment_id}-trades.csv"',
                "X-Content-Type-Options": "nosniff",
            },
        )
    return store.list_experiment_trade_page(experiment_id, after_sequence=after_sequence, limit=limit)


def _trade_csv(store: Store, experiment_id: UUID, experiment: dict[str, Any]):
    execution = experiment["execution"]
    provenance = " ".join(
        f"{key}={value}"
        for key, value in {
            "experiment": experiment_id,
            "candidate_hash": experiment["candidate_hash"],
            "dataset": experiment["dataset_version"],
            "initial_equity": execution["initial_equity"],
            "fixed_notional": execution["fixed_notional"],
            "leverage": execution["leverage"],
            "fill_policy": execution["fill_policy"],
            "position_policy": execution["position_policy"],
            "open_position_at_end": execution["open_position_at_end"],
            "fee_bps": execution["fee_bps"],
            "slippage_bps": execution["slippage_bps"],
            "risk_policy": json.dumps({key: execution.get(key) for key in ("stop_loss_pct", "take_profit_pct", "intrabar_priority")}, separators=(",", ":")),
        }.items()
    )
    yield f"# {provenance}\n"
    columns = [
        "sequence_no", "symbol", "quote_currency", "side", "signal_t", "entry_time", "entry_price", "quantity",
        "entry_notional", "fee_paid", "spread_cost", "slippage_cost", "exit_time", "exit_price", "exit_notional",
        "gross_pnl", "net_pnl", "pnl_absolute", "pnl_percent", "exit_reason", "sl_price", "tp_price",
    ]
    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(columns)
    yield output.getvalue()
    after_sequence: int | None = None
    while True:
        page = store.list_experiment_trade_page(experiment_id, after_sequence=after_sequence, limit=200)
        for trade in page["trades"]:
            output.seek(0)
            output.truncate(0)
            writer.writerow([
                value.isoformat() if isinstance(value, datetime) else value
                for value in (trade.get(column) for column in columns)
            ])
            yield output.getvalue()
        after_sequence = page["next_cursor"]
        if after_sequence is None:
            return


@app.get("/api/v1/experiments/{experiment_id}/equity", response_model=dict[str, list[EquityPointOut]])
def get_experiment_equity(
    experiment_id: UUID, _auth: Internal, owner_id: OwnerID, request: Request
) -> dict[str, Any]:
    store = _store(request)
    store.get_experiment(experiment_id, owner_id)
    return {"equity": store.list_experiment_equity(experiment_id)}


@app.get("/api/v1/experiments/{experiment_id}/overlays")
def get_experiment_overlays(
    experiment_id: UUID, _auth: Internal, owner_id: OwnerID, request: Request
) -> dict[str, Any]:
    store = _store(request)
    store.get_experiment(experiment_id, owner_id)
    execution_markers = []
    for trade in store.list_experiment_execution_markers(experiment_id):
        entry_type = "long_entry" if str(trade["side"]).upper().startswith("LONG") else "short_entry"
        execution_markers.append({
            "sequence_no": trade["sequence_no"], "t": trade["entry_time"],
            "overlay_type": entry_type, "price": trade["entry_price"],
        })
        for overlay_type, price in (("stop_loss", trade["sl_price"]), ("take_profit", trade["tp_price"])):
            if price is not None:
                execution_markers.append({
                    "sequence_no": trade["sequence_no"], "t": trade["entry_time"],
                    "line_until": trade["exit_time"], "overlay_type": overlay_type, "price": price,
                })
        if trade["exit_time"] is not None and trade["exit_price"] is not None:
            execution_markers.append({
                "sequence_no": trade["sequence_no"], "t": trade["exit_time"],
                "overlay_type": "exit", "price": trade["exit_price"], "exit_reason": trade["exit_reason"],
            })
    return {
        "overlays": store.list_experiment_overlays(experiment_id),
        "execution_markers": [
            ExecutionMarkerOut.model_validate(marker).model_dump(mode="json", exclude_none=True)
            for marker in execution_markers
        ],
    }


@app.post("/api/v1/search-runs", response_model=SearchRunOut)
def create_search_run(
    body: SearchRunCreateIn, _auth: Internal, request: Request
) -> JSONResponse:
    result = _store(request).create_search_run(body, request.state.request_id)
    return JSONResponse(
        status_code=200 if result["reused"] else 202,
        content=jsonable_encoder(result),
    )


@app.get("/api/v1/search-runs/{run_id}", response_model=SearchRunOut)
def get_search_run(
    run_id: UUID, _auth: Internal, owner_id: OwnerID, request: Request
) -> dict[str, Any]:
    return _store(request).get_search_run(run_id, owner_id)


@app.post("/api/v1/search-runs/{run_id}/actions")
def apply_search_action(
    run_id: UUID, body: SearchActionIn, _auth: Internal, request: Request
) -> dict[str, Any]:
    return _store(request).apply_search_action(run_id, body)


@app.get("/api/v1/leaderboard", response_model=dict[str, Any])
def get_leaderboard(
    dataset_version: Annotated[str, Query(min_length=1)],
    _auth: Internal,
    request: Request,
    score_policy_version: str | None = None,
    sort_by: str = "score",
    limit: Annotated[int, Query(ge=1)] = 10,
) -> dict[str, Any]:
    applied_limit = min(limit, Settings.from_env().max_page_size)
    entries = _store(request).list_leaderboard(
        dataset_version, score_policy_version, applied_limit, sort_by
    )
    return {
        "entries": [LeaderboardEntryOut.model_validate(item) for item in entries],
        "limit_applied": applied_limit,
    }


@app.get("/api/v1/leaderboard/{entry_id}/provenance")
def get_leaderboard_provenance(
    entry_id: UUID, _auth: Internal, request: Request
) -> dict[str, Any]:
    return _store(request).get_provenance(entry_id)


@app.post("/api/v1/admin/score-policies", status_code=201)
def create_score_policy(
    body: ScorePolicyCreateIn, _auth: Internal, _admin: Admin, request: Request
) -> dict[str, Any]:
    return _store(request).create_score_policy(body)


@app.post("/api/v1/admin/score-policies/{version}/activate", status_code=204)
def activate_score_policy(
    version: str, _auth: Internal, _admin: Admin, request: Request
) -> Response:
    _store(request).activate_score_policy(version)
    return Response(status_code=204)


@app.get("/api/v1/news", response_model=dict[str, list[NewsItemOut]])
def get_news(
    _auth: Internal,
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    coin: str | None = None,
) -> dict[str, Any]:
    return {"items": _store(request).list_news(limit, coin)}


@app.get("/api/v1/news/aggregate", response_model=NewsAggregateOut)
def get_news_aggregate(
    _auth: Internal, request: Request, coin: str | None = None
) -> dict[str, Any]:
    return _store(request).news_aggregate(coin)


@app.post("/api/v1/admin/news-sources", status_code=201)
def create_news_source(
    body: NewsSourceCreateIn, _auth: Internal, _admin: Admin, request: Request
) -> dict[str, Any]:
    try:
        assert_public_https(body.url_template, body.allowed_origin)
    except SsrfBlocked as exc:
        raise ApplicationError(
            "news_source_blocked", "news source failed outbound security validation", 422
        ) from exc
    return _store(request).create_news_source(**body.model_dump())


@app.post("/api/v1/admin/news/collect")
def collect_news(
    body: NewsCollectIn, _auth: Internal, _admin: Admin, request: Request
) -> dict[str, Any]:
    results = _news_service(request).collect_all(body.source_id, request.state.request_id)
    if body.source_id is not None and not results:
        raise ApplicationError("news_source_not_found", "news source was not found", 404)
    return {"results": [item.__dict__ for item in results]}


@app.post("/api/v1/admin/sentiment/backfill")
def backfill_sentiment(
    body: SentimentBackfillIn, _auth: Internal, _admin: Admin, request: Request
) -> dict[str, Any]:
    settings = Settings.from_env()
    result = _news_service(request).analyze_pending(
        model=settings.sentiment_model,
        model_version=settings.sentiment_model_version,
        limit=body.limit,
        correlation_id=request.state.request_id,
    )
    return result.__dict__


@app.post("/api/v1/sentiment/predict", response_model=SentimentPredictOut)
def predict_sentiment(
    body: SentimentPredictIn, _auth: Internal, request: Request
) -> dict[str, Any]:
    settings = Settings.from_env()
    analyzer = SentimentHTTPAdapter(settings.ai_service_url, settings.ai_timeout_s)
    try:
        result = analyzer.analyze(body.text, request.state.request_id)
    except SentimentUnavailable as exc:
        raise ApplicationError(
            "sentiment_unavailable", "sentiment inference is temporarily unavailable", 503
        ) from exc
    except ContractViolation as exc:
        raise ApplicationError(
            "sentiment_contract_violation", "sentiment inference returned invalid data", 502
        ) from exc
    finally:
        analyzer.close()
    return {
        "label": result.label,
        "score": result.score,
        "model": result.model,
        "model_version": result.model_version,
        "received_at": result.analyzed_at,
    }
