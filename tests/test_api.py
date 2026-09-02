"""HTTP boundary tests for the internal research service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

TOKEN_HEADERS = {"Authorization": "Bearer development-internal-token"}


class FakeStore:
    def ready(self):
        return {"database": True, "active_score_policy": True}

    def operational_metrics(self):
        return {
            "research_jobs_queued": 2.0,
            "research_outbox_oldest_seconds": 0.0,
            "research_agent_runs_review_required": 1.0,
            "research_sandbox_runs_passed": 1.0,
        }

    def list_leaderboard(self, dataset_version, score_policy_version, limit, sort_by):
        del score_policy_version, limit, sort_by
        return [
            {
                "entry_id": uuid4(),
                "evaluation_id": uuid4(),
                "experiment_id": uuid4(),
                "score": 72.5,
                "rank": 1,
                "score_policy_version": "v1",
                "dataset_version": dataset_version,
                "strategy_id": "ma_cross",
                "strategy_version": "v1",
                "candidate_hash": "a" * 64,
                "total_return_pct": 8.2,
                "win_rate_pct": 55.0,
                "max_drawdown_pct": -4.0,
                "trade_count": 12,
                "profit_factor": 1.4,
                "sharpe_ratio": 0.8,
                "observed_at": datetime(2026, 8, 25, tzinfo=UTC),
            }
        ]

    def list_strategy_drafts(self, owner_id, limit):
        self.listed_strategy_owner = owner_id
        self.listed_strategy_limit = limit
        now = datetime(2026, 8, 31, tzinfo=UTC)
        return [
            {
                "draft_id": uuid4(),
                "owner_id": owner_id,
                "source_type": "text",
                "mode": "dsl",
                "name_hint": "RSI mean reversion",
                "status": "APPROVED",
                "current_revision": 1,
                "source_hash": "a" * 64,
                "spec_hash": "b" * 64,
                "artifact_hash": "c" * 64,
                "sandbox_report_hash": "d" * 64,
                "repair_attempts_used": 1,
                "repair_attempts_max": 3,
                "strategy_spec": None,
                "created_at": now,
                "updated_at": now,
            }
        ]


app.state.store = FakeStore()
app.state.registry_sync_error = None
client = TestClient(app)


def test_health_returns_float64_service() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "research", "numeric": "float64"}
    assert response.headers["X-Request-ID"]


def test_ready_checks_database_policy_and_registry() -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    assert all(response.json()["checks"].values())


def test_metrics_requires_internal_auth_and_exposes_domain_gauges() -> None:
    assert client.get("/metrics").status_code == 401
    response = client.get("/metrics", headers=TOKEN_HEADERS)
    assert response.status_code == 200
    assert "cryptobot_research_jobs_queued 2.000000000" in response.text
    assert "cryptobot_research_agent_runs_review_required 1.000000000" in response.text
    assert "cryptobot_research_sandbox_runs_passed 1.000000000" in response.text


def test_business_routes_require_internal_auth() -> None:
    response = client.get("/api/v1/strategies")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "internal_auth_required"


def test_strategies_return_real_registry_metadata() -> None:
    response = client.get("/api/v1/strategies", headers=TOKEN_HEADERS)
    assert response.status_code == 200
    strategy_ids = {item["strategy_id"] for item in response.json()["strategies"]}
    assert {"ma_cross", "rsi", "bollinger", "support_resistance", "smc", "news_sentiment", "macd", "composite"} <= strategy_ids


def test_strategy_catalog_uses_builtin_warmup_metadata_over_stale_storage() -> None:
    class StaleCatalogStore(FakeStore):
        def list_strategies(self):
            return [{
                "strategy_id": "smc",
                "version": "v1",
                "family": "structure",
                "display_name": "stale SMC",
                "description": "stale catalog row",
                "parameters_schema": {},
                "default_params": {},
                "input_requirements": ["support:20", "resistance:20"],
                "overlay_types": ["market_structure"],
                "warm_up_candles": 0,
                "is_composite": False,
                "code_fingerprint": "a" * 64,
            }]

    previous = app.state.store
    app.state.store = StaleCatalogStore()
    try:
        response = client.get("/api/v1/strategies", headers=TOKEN_HEADERS)
    finally:
        app.state.store = previous

    assert response.status_code == 200
    assert response.json()["strategies"][0]["warm_up_candles"] == 21


def test_chart_overlays_are_computed_from_live_candles() -> None:
    from app.domain.market import Candle

    class ChartStore(FakeStore):
        def list_live_candles(self, provider, symbol, timeframe, limit):
            assert (provider, symbol, timeframe, limit) == ("binance_usdm", "ETHUSDT", "5m", 60)
            start = datetime(2026, 1, 1, tzinfo=UTC)
            return [
                Candle(
                    provider=provider, symbol=symbol, timeframe=timeframe,
                    open_time=start + timedelta(minutes=5 * index),
                    close_time=start + timedelta(minutes=5 * (index + 1)),
                    open=100 + index, high=101 + index, low=99 + index,
                    close=100 + index, volume=1.0,
                )
                for index in range(60)
            ]

        def stream_checkpoint(self, provider, symbol, timeframe):
            assert (provider, symbol, timeframe) == ("binance_usdm", "ETHUSDT", "5m")
            return {"last_closed_at": datetime(2026, 1, 1, 0, 30, tzinfo=UTC), "last_source_sequence": 7, "is_stale": False}

    previous = app.state.store
    app.state.store = ChartStore()
    try:
        response = client.get(
            "/api/v1/markets/chart-overlays?provider=binance_usdm&symbol=ETHUSDT&timeframe=5m&strategy=ma_cross@v1&limit=60",
            headers=TOKEN_HEADERS,
        )
    finally:
        app.state.store = previous

    assert response.status_code == 200
    payload = response.json()
    assert payload["seq"] == 7
    assert payload["is_stale"] is False
    assert payload["series"][0]["name"] == "sma:20"
    assert payload["series"][0]["points"][-1]["v"] == 149.5


def test_chart_overlay_delta_returns_empty_payload_without_live_candles() -> None:
    class EmptyChartStore(FakeStore):
        def list_live_candles(self, provider, symbol, timeframe, limit):
            assert (provider, symbol, timeframe, limit) == ("binance_usdm", "ETHUSDT", "5m", 60)
            return []

    previous = app.state.store
    app.state.store = EmptyChartStore()
    try:
        response = client.get(
            "/api/v1/markets/chart-overlays/delta?provider=binance_usdm&symbol=ETHUSDT&timeframe=5m&strategy=ma_cross@v1&limit=60",
            headers=TOKEN_HEADERS,
        )
    finally:
        app.state.store = previous

    assert response.status_code == 200
    assert response.json() == {"revised_from": None, "series": [], "markers": []}


def test_trade_csv_export_streams_provenance_and_owner_checked_rows() -> None:
    experiment_id = uuid4()
    owner_id = uuid4()

    class CsvStore(FakeStore):
        def get_experiment(self, received_id, received_owner):
            assert (received_id, received_owner) == (experiment_id, owner_id)
            return {
                "candidate_hash": "a" * 64,
                "dataset_version": "fixture:ETHUSDT:5m:v1",
                "execution": {"initial_equity": 100, "fixed_notional": 10, "leverage": 1, "fee_bps": 8, "slippage_bps": 2, "fill_policy": "bbo_limit", "position_policy": "one_net_position", "open_position_at_end": "last_executable_bbo"},
            }

        def list_experiment_trade_page(self, received_id, *, after_sequence, limit):
            assert received_id == experiment_id and limit == 200
            if after_sequence is not None:
                return {"trades": [], "next_cursor": None}
            return {"trades": [{"sequence_no": 1, "symbol": "ETHUSDT", "quote_currency": "USDT", "side": "LONG", "entry_time": datetime(2026, 1, 1, tzinfo=UTC), "entry_price": 100.0, "quantity": 1.0, "entry_notional": 100.0, "fee_paid": 0.08, "spread_cost": 0.1, "slippage_cost": 0.02, "exit_time": datetime(2026, 1, 1, 0, 5, tzinfo=UTC), "exit_price": 101.0, "exit_notional": 101.0, "gross_pnl": 1.0, "net_pnl": 0.8, "pnl_absolute": 0.8, "pnl_percent": 0.8, "exit_reason": "signal", "sl_price": None, "tp_price": None, "signal_t": None}], "next_cursor": None}

    previous = app.state.store
    app.state.store = CsvStore()
    try:
        response = client.get(f"/api/v1/experiments/{experiment_id}/trades?format=csv", headers={**TOKEN_HEADERS, "X-User-ID": str(owner_id)})
    finally:
        app.state.store = previous

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == f'attachment; filename="experiment-{experiment_id}-trades.csv"'
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.text.splitlines()[0].startswith(f"# experiment={experiment_id} candidate_hash={'a' * 64} dataset=fixture:ETHUSDT:5m:v1")
    assert "sequence_no,symbol,quote_currency" in response.text
    assert ",ETHUSDT,USDT,LONG," in response.text


def test_experiment_overlays_include_trade_execution_markers() -> None:
    experiment_id = uuid4()
    owner_id = uuid4()

    class OverlayStore(FakeStore):
        def get_experiment(self, received_id, received_owner):
            assert (received_id, received_owner) == (experiment_id, owner_id)
            return {}

        def list_experiment_overlays(self, received_id):
            assert received_id == experiment_id
            return []

        def list_experiment_execution_markers(self, received_id):
            assert received_id == experiment_id
            return [{
                "sequence_no": 7,
                "entry_time": datetime(2026, 1, 1, tzinfo=UTC),
                "entry_price": 100.0,
                "exit_time": datetime(2026, 1, 1, 0, 5, tzinfo=UTC),
                "exit_price": 101.0,
                "side": "LONG",
                "exit_reason": "take_profit",
                "sl_price": 98.0,
                "tp_price": 104.0,
            }]

    previous = app.state.store
    app.state.store = OverlayStore()
    try:
        response = client.get(
            f"/api/v1/experiments/{experiment_id}/overlays",
            headers={**TOKEN_HEADERS, "X-User-ID": str(owner_id)},
        )
    finally:
        app.state.store = previous

    assert response.status_code == 200
    assert response.json()["execution_markers"] == [
        {"sequence_no": 7, "t": "2026-01-01T00:00:00Z", "overlay_type": "long_entry", "price": 100.0},
        {"sequence_no": 7, "t": "2026-01-01T00:00:00Z", "line_until": "2026-01-01T00:05:00Z", "overlay_type": "stop_loss", "price": 98.0},
        {"sequence_no": 7, "t": "2026-01-01T00:00:00Z", "line_until": "2026-01-01T00:05:00Z", "overlay_type": "take_profit", "price": 104.0},
        {"sequence_no": 7, "t": "2026-01-01T00:05:00Z", "overlay_type": "exit", "price": 101.0, "exit_reason": "take_profit"},
    ]


def test_strategy_draft_list_is_owned_and_bounded() -> None:
    owner_id = uuid4()
    response = client.get(
        "/api/v1/strategy-drafts?limit=3",
        headers={**TOKEN_HEADERS, "X-User-ID": str(owner_id)},
    )

    assert response.status_code == 200
    assert response.json()["drafts"][0]["owner_id"] == str(owner_id)
    assert app.state.store.listed_strategy_owner == owner_id
    assert app.state.store.listed_strategy_limit == 3


def test_strategy_draft_list_loads_all_owned_drafts_by_default() -> None:
    owner_id = uuid4()
    response = client.get(
        "/api/v1/strategy-drafts",
        headers={**TOKEN_HEADERS, "X-User-ID": str(owner_id)},
    )

    assert response.status_code == 200
    assert app.state.store.listed_strategy_owner == owner_id
    assert app.state.store.listed_strategy_limit is None


def test_experiment_history_is_owned_and_loads_without_a_default_limit() -> None:
    owner_id = uuid4()

    class ExperimentHistoryStore(FakeStore):
        def list_experiments(self, received_owner, limit):
            self.received_owner = received_owner
            self.received_limit = limit
            return []

    previous = app.state.store
    history_store = ExperimentHistoryStore()
    app.state.store = history_store
    try:
        response = client.get(
            "/api/v1/experiments",
            headers={**TOKEN_HEADERS, "X-User-ID": str(owner_id)},
        )
    finally:
        app.state.store = previous

    assert response.status_code == 200
    assert response.json() == {"experiments": []}
    assert history_store.received_owner == owner_id
    assert history_store.received_limit is None


def test_discovery_session_history_is_owned_and_bounded() -> None:
    owner_id = uuid4()

    class HistoryStore(FakeStore):
        def list_discovery_runs(self, received_owner, limit):
            assert received_owner == owner_id
            assert limit == 3
            now = datetime(2026, 9, 1, tzinfo=UTC)
            return [{
                "search_run_id": uuid4(), "owner_id": owner_id, "generator_id": "discovery",
                "status": "completed", "generated": 4, "tested": 4, "failed": 0,
                "best_score": 1.2, "current_candidate_hash": None, "stop_reason": "final_test_completed",
                "created_at": now, "updated_at": now, "dataset_version": "fixture:SOLUSDT:1h:v1",
                "content_hash": "a" * 64, "reused": False,
            }]

    previous = app.state.store
    app.state.store = HistoryStore()
    try:
        response = client.get(
            "/api/v1/search-runs?limit=3",
            headers={**TOKEN_HEADERS, "X-User-ID": str(owner_id)},
        )
    finally:
        app.state.store = previous

    assert response.status_code == 200
    assert response.json()["runs"][0]["owner_id"] == str(owner_id)


def test_strategy_draft_command_submits_a_durable_job() -> None:
    owner_id = uuid4()
    now = datetime(2026, 9, 1, tzinfo=UTC)

    class DurableAuthoring:
        def __init__(self) -> None:
            self.request = None
            self.correlation_id = None

        def submit(self, request, correlation_id):
            self.request = request
            self.correlation_id = correlation_id
            return {
                "draft_id": uuid4(), "owner_id": owner_id, "source_type": "text", "mode": "dsl",
                "name_hint": None, "status": "DRAFT_CREATED", "current_revision": 0,
                "source_hash": "a" * 64, "spec_hash": None, "artifact_hash": None,
                "sandbox_report_hash": None, "repair_attempts_used": 0, "repair_attempts_max": 3,
                "strategy_spec": None, "created_at": now, "updated_at": now,
            }

    previous = getattr(app.state, "authoring_service", None)
    authoring = DurableAuthoring()
    app.state.authoring_service = authoring
    try:
        response = client.post(
            "/api/v1/strategy-drafts",
            headers={**TOKEN_HEADERS, "X-Request-ID": "durable-agent-command"},
            json={"owner_id": str(owner_id), "source": {"type": "text", "text": "Use RSI below 30."}},
        )
    finally:
        app.state.authoring_service = previous

    assert response.status_code == 202
    assert response.json()["status"] == "DRAFT_CREATED"
    assert authoring.request.owner_id == owner_id
    assert authoring.correlation_id == "durable-agent-command"


def test_strategy_draft_cancel_uses_the_authenticated_owner() -> None:
    owner_id = uuid4()
    now = datetime(2026, 9, 1, tzinfo=UTC)

    class CancelStore(FakeStore):
        def __init__(self) -> None:
            self.cancelled = None

        def cancel_strategy_draft(self, draft_id, request_owner_id):
            self.cancelled = (draft_id, request_owner_id)
            return {
                "draft_id": draft_id, "owner_id": owner_id, "source_type": "text", "mode": "dsl",
                "name_hint": None, "status": "CANCELLED", "current_revision": 0,
                "source_hash": "a" * 64, "spec_hash": None, "artifact_hash": None,
                "sandbox_report_hash": None, "repair_attempts_used": 0, "repair_attempts_max": 3,
                "strategy_spec": None, "created_at": now, "updated_at": now,
            }

    previous = app.state.store
    store = CancelStore()
    app.state.store = store
    draft_id = uuid4()
    try:
        response = client.post(
            f"/api/v1/strategy-drafts/{draft_id}/actions",
            headers={**TOKEN_HEADERS, "X-User-ID": str(owner_id)},
            json={"action": "cancel"},
        )
    finally:
        app.state.store = previous

    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"
    assert store.cancelled == (draft_id, owner_id)


def test_leaderboard_requires_dataset_version() -> None:
    response = client.get("/api/v1/leaderboard", headers=TOKEN_HEADERS)
    assert response.status_code == 422


def test_leaderboard_returns_persisted_ranking_shape() -> None:
    response = client.get(
        "/api/v1/leaderboard?dataset_version=fixture-v1&limit=10",
        headers=TOKEN_HEADERS,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["entries"][0]["rank"] == 1
    assert body["entries"][0]["dataset_version"] == "fixture-v1"
    assert body["limit_applied"] == 10


def test_request_body_limit_is_enforced_before_validation() -> None:
    response = client.post(
        "/api/v1/experiments",
        headers={**TOKEN_HEADERS, "Content-Length": "2000000"},
        content=b"{}",
    )
    assert response.status_code == 413
    assert response.json()["code"] == "request_too_large"
