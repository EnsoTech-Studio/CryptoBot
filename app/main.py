"""FastAPI backend for the strategy/backtest/leaderboard domain.

Separate from the Go `server/` backend. This service owns: strategies,
experiments (+candles/trades/equity/overlays), search-runs, leaderboard
(+provenance), and admin score-policies. Market data, news, sentiment, auth, and
observability remain in the Go backend.

All numerics are float64 (Python `float`). Domain logic is deferred; domain
endpoints return 501 until the engines are implemented — mirroring the Go
skeleton's `ErrNotImplemented` state.
"""

from __future__ import annotations

from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse

app = FastAPI(
    title="CryptoBot Strategy/Backtest Backend",
    version="0.1.0",
    description="Strategy, backtest, evaluation, search and leaderboard domain (float64).",
)

_NOT_IMPLEMENTED = JSONResponse({"error": "not implemented"}, status_code=501)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "strategy-backtest", "numeric": "float64"}


@app.get("/ready")
def ready() -> dict[str, str]:
    return {"status": "ok"}


# --- strategies ---
@app.get("/api/v1/strategies")
def list_strategies() -> JSONResponse:
    return _NOT_IMPLEMENTED


# --- experiments ---
@app.post("/api/v1/experiments", status_code=202)
def create_experiment() -> JSONResponse:
    return _NOT_IMPLEMENTED


@app.get("/api/v1/experiments/{experiment_id}")
def get_experiment(experiment_id: str) -> JSONResponse:
    return _NOT_IMPLEMENTED


@app.get("/api/v1/experiments/{experiment_id}/candles")
def get_experiment_candles(experiment_id: str) -> JSONResponse:
    return _NOT_IMPLEMENTED


@app.get("/api/v1/experiments/{experiment_id}/trades")
def get_experiment_trades(experiment_id: str) -> JSONResponse:
    return _NOT_IMPLEMENTED


@app.get("/api/v1/experiments/{experiment_id}/equity")
def get_experiment_equity(experiment_id: str) -> JSONResponse:
    return _NOT_IMPLEMENTED


@app.get("/api/v1/experiments/{experiment_id}/overlays")
def get_experiment_overlays(experiment_id: str) -> JSONResponse:
    return _NOT_IMPLEMENTED


# --- search runs ---
@app.post("/api/v1/search-runs", status_code=202)
def create_search_run() -> JSONResponse:
    return _NOT_IMPLEMENTED


@app.get("/api/v1/search-runs/{run_id}")
def get_search_run(run_id: str) -> JSONResponse:
    return _NOT_IMPLEMENTED


@app.post("/api/v1/search-runs/{run_id}/actions", status_code=202)
def apply_search_action(run_id: str) -> JSONResponse:
    return _NOT_IMPLEMENTED


# --- leaderboard ---
@app.get("/api/v1/leaderboard")
def get_leaderboard() -> JSONResponse:
    return _NOT_IMPLEMENTED


@app.get("/api/v1/leaderboard/{entry_id}/provenance")
def get_leaderboard_provenance(entry_id: str) -> JSONResponse:
    return _NOT_IMPLEMENTED


# --- admin score policies ---
@app.post("/api/v1/admin/score-policies", status_code=201)
def create_score_policy() -> JSONResponse:
    return _NOT_IMPLEMENTED


@app.post("/api/v1/admin/score-policies/{version}/activate", status_code=204)
def activate_score_policy(version: str) -> Response:
    return Response(status_code=204)
