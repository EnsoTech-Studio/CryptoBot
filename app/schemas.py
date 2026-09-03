"""Versioned internal HTTP contracts for the research service."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorOut(ContractModel):
    code: str
    message: str
    field: str | None = None
    request_id: str | None = None


class StrategyOut(ContractModel):
    strategy_id: str
    version: str
    family: str | None = None
    display_name: str
    description: str
    parameters_schema: dict[str, Any]
    default_params: dict[str, Any]
    input_requirements: list[str]
    overlay_types: list[str]
    warm_up_candles: int
    is_composite: bool
    code_fingerprint: str


class StrategySourceIn(ContractModel):
    type: Literal["text", "approved_url", "dsl"]
    text: str | None = Field(default=None, max_length=10_000)
    url: str | None = Field(default=None, max_length=2_000)
    spec: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_source_payload(self) -> "StrategySourceIn":
        supplied = {
            "text": self.text is not None,
            "url": self.url is not None,
            "spec": self.spec is not None,
        }
        expected = {"text": "text", "approved_url": "url", "dsl": "spec"}[self.type]
        if not supplied[expected] or sum(supplied.values()) != 1:
            raise ValueError(f"source type {self.type} requires exactly its matching payload")
        if self.text is not None and not self.text.strip():
            raise ValueError("source text must not be blank")
        return self


class StrategySpecResponse(ContractModel):
    schema_version: str = "strategy-spec/v1"
    strategy_id: str = Field(min_length=1, max_length=120)
    display_name: str = Field(min_length=1, max_length=120)
    family: Literal["trend", "momentum", "volatility", "structure", "information"]
    description: str = Field(min_length=1, max_length=2_000)
    parameters: dict[str, dict[str, Any]]
    indicators: list[dict[str, Any]]
    rules: dict[str, Any]
    warmup_bars: int = Field(ge=1, le=10_000)


class StrategyDraftCreateIn(ContractModel):
    owner_id: UUID
    mode: Literal["dsl", "custom_python"] = "dsl"
    source: StrategySourceIn
    name_hint: str | None = Field(default=None, max_length=120)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=120)

    @model_validator(mode="after")
    def validate_authoring_mode(self) -> "StrategyDraftCreateIn":
        if self.mode == "custom_python" and self.source.type != "text":
            raise ValueError("custom Python requires a text source")
        return self


class StrategyApprovalIn(ContractModel):
    reviewer_id: UUID
    revision: int = Field(gt=0)
    spec_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    sandbox_report_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision: Literal["approve", "reject"]
    reason: str = Field(min_length=1, max_length=2_000)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=120)


class StrategyDraftActionIn(ContractModel):
    action: Literal["cancel"]


class StrategyDraftOut(ContractModel):
    draft_id: UUID
    owner_id: UUID
    source_type: str
    mode: str
    name_hint: str | None = None
    status: str
    current_revision: int
    source_hash: str
    spec_hash: str | None = None
    artifact_hash: str | None = None
    sandbox_report_hash: str | None = None
    repair_attempts_used: int
    repair_attempts_max: int
    strategy_spec: dict[str, Any] | None = None
    model: str | None = None
    model_version: str | None = None
    agent_reasoning: str | None = None
    created_at: datetime
    updated_at: datetime


class ExperimentCreateIn(ContractModel):
    owner_id: UUID
    strategy_id: str = Field(min_length=1, max_length=48)
    strategy_version: str = Field(min_length=1, max_length=24)
    candidate_definition: dict[str, Any] = Field(default_factory=dict)
    candidate_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    dataset_version: str = Field(min_length=1, max_length=120)
    range_from: datetime | None = None
    range_to: datetime | None = None
    bbo_dataset_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    initial_equity: float = Field(default=100.0, gt=0)
    fixed_notional: float = Field(default=10.0, gt=0)
    leverage: float = Field(default=1.0, gt=0)
    fee_bps: int = Field(default=10, ge=0, le=10_000)
    slippage_bps: int = Field(default=0, ge=0, le=10_000)
    fill_policy: Literal["bbo_limit"] = "bbo_limit"
    position_policy: Literal["one_net_position"] = "one_net_position"
    open_position_at_end: Literal["last_executable_bbo"] = "last_executable_bbo"
    stop_loss_pct: float | None = Field(default=None, gt=0, lt=100)
    take_profit_pct: float | None = Field(default=None, gt=0)
    intrabar_priority: Literal["stop_loss_first", "take_profit_first"] = "stop_loss_first"
    evaluator_version: str = Field(default="v1", min_length=1, max_length=24)
    sentiment_model: str = Field(default="gpt-4o-mini", min_length=1, max_length=80)
    sentiment_model_version: str = Field(default="openai-gpt-4o-mini", min_length=1, max_length=80)
    sentiment_window_sec: int = Field(default=3600, ge=60, le=604_800)
    analysis_lag_sec: int = Field(default=300, ge=0, le=86_400)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=120)

    @model_validator(mode="after")
    def validate_replay_range(self) -> "ExperimentCreateIn":
        if (self.range_from is None) != (self.range_to is None):
            raise ValueError("range_from and range_to must be supplied together")
        if (
            self.range_from is not None
            and self.range_to is not None
            and self.range_to <= self.range_from
        ):
            raise ValueError("range_to must be after range_from")
        return self


class AcceptedRunOut(ContractModel):
    run_id: UUID
    experiment_id: UUID
    status: str
    reused: bool = False


class ExperimentMetricsOut(ContractModel):
    total_return_pct: float
    win_rate_pct: float
    max_drawdown_pct: float
    trade_count: int
    wins: int = 0
    losses: int = 0
    net_profit: float = 0
    profit_factor: float | None = None
    sharpe_ratio: float | None = None
    score: float | None = None
    evaluator_version: str


class ExperimentSummaryOut(ContractModel):
    id: UUID
    experiment_id: UUID
    run_id: UUID | None = None
    owner_id: UUID
    candidate_hash: str
    status: str
    dataset_version: str
    range_from: datetime
    range_to: datetime
    provider: str
    symbol: str
    timeframe: str
    strategy_id: str
    strategy_version: str
    evaluator_version: str
    content_hash: str
    bbo_content_hash: str | None = None
    result_hash: str | None = None
    candidate_definition: dict[str, Any]
    strategy_definition: dict[str, Any] | None = None
    execution: dict[str, Any]
    metrics: ExperimentMetricsOut | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    candles_read: int | None = None
    signals_count: int | None = None
    error_code: str | None = None


class CandleOut(ContractModel):
    open_time: datetime
    close_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    trade_count: int | None = None


class TradeOut(ContractModel):
    sequence_no: int
    symbol: str
    quote_currency: str
    side: str
    signal_t: datetime | None = None
    entry_time: datetime
    entry_price: float
    quantity: float
    entry_notional: float
    fee_paid: float
    spread_cost: float
    slippage_cost: float
    exit_time: datetime | None = None
    exit_price: float | None = None
    exit_notional: float | None = None
    gross_pnl: float | None = None
    net_pnl: float | None = None
    pnl_absolute: float | None = None
    pnl_percent: float | None = None
    exit_reason: str | None = None
    sl_price: float | None = None
    tp_price: float | None = None


class TradePageOut(ContractModel):
    trades: list[TradeOut]
    next_cursor: int | None = None


class EquityPointOut(ContractModel):
    point_time: datetime
    equity: float
    drawdown_pct: float | None = None


class OverlayPointOut(ContractModel):
    candle_time: datetime
    signal: str
    confidence: float | None = None
    child_signals: dict[str, Any] | None = None


class ExecutionMarkerOut(ContractModel):
    sequence_no: int
    t: datetime
    line_until: datetime | None = None
    overlay_type: str
    price: float
    action: Literal["BUY", "SELL"] | None = None
    exit_reason: str | None = None


class SearchStopConditions(ContractModel):
    max_candidates: int | None = Field(default=None, strict=True, gt=0, le=500)
    max_duration_sec: int | None = Field(default=None, strict=True, gt=0, le=86_400)
    max_non_improving: int | None = Field(default=None, strict=True, gt=0, le=500)
    max_failure_rate: float | None = Field(default=None, gt=0, le=1)

    @field_validator("max_failure_rate", mode="before")
    @classmethod
    def validate_failure_rate_type(cls, value: Any) -> Any:
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
            raise ValueError("max_failure_rate must be a number")
        return value

    @model_validator(mode="after")
    def require_one_condition(self) -> "SearchStopConditions":
        if not any(
            value is not None
            for value in (
                self.max_candidates,
                self.max_duration_sec,
                self.max_non_improving,
                self.max_failure_rate,
            )
        ):
            raise ValueError("at least one bounded stop condition is required")
        return self


class SearchSpaceInput(ContractModel):
    strategy_ids: list[str] = Field(min_length=1, max_length=20)
    cardinality: list[Annotated[int, Field(strict=True, ge=1, le=5)]] = Field(
        default_factory=lambda: [1], min_length=1, max_length=4
    )
    policies: list[Literal["weighted_vote", "majority_vote"]] = Field(
        default_factory=lambda: ["weighted_vote"], min_length=1, max_length=2
    )
    parameter_grid: dict[str, dict[str, list[Any]]] = Field(default_factory=dict)

    @field_validator("cardinality")
    @classmethod
    def validate_cardinality(cls, values: list[int]) -> list[int]:
        return sorted(set(values))

    @model_validator(mode="after")
    def validate_strategy_references(self) -> "SearchSpaceInput":
        if len(set(self.strategy_ids)) != len(self.strategy_ids):
            raise ValueError("strategy_ids must be unique")
        unknown_grids = set(self.parameter_grid) - set(self.strategy_ids)
        if unknown_grids:
            raise ValueError("parameter_grid references an unknown strategy_id")
        if min(self.cardinality) > len(self.strategy_ids):
            raise ValueError("cardinality exceeds the number of strategies")
        return self


class SearchRunCreateIn(ContractModel):
    owner_id: UUID
    generator_id: Literal["grid", "random", "random_search", "domain_guided", "genetic", "discovery"] = "grid"
    search_space: SearchSpaceInput
    stop_conditions: SearchStopConditions
    dataset_version: str = Field(min_length=1, max_length=120)
    seed: int = 0
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=120)


class SearchRunOut(ContractModel):
    search_run_id: UUID
    owner_id: UUID
    generator_id: str
    status: str
    generated: int
    tested: int
    failed: int
    best_score: float | None = None
    current_candidate_hash: str | None = None
    stop_reason: str | None = None
    created_at: datetime
    updated_at: datetime
    dataset_version: str
    content_hash: str
    reused: bool = False


class SearchActionIn(ContractModel):
    actor_id: UUID
    command_id: UUID
    action: Literal["pause", "resume", "cancel"]


class LeaderboardEntryOut(ContractModel):
    entry_id: UUID
    evaluation_id: UUID
    experiment_id: UUID
    can_open: bool = False
    score: float
    rank: int
    score_policy_version: str
    dataset_version: str
    strategy_id: str
    strategy_version: str
    candidate_hash: str
    total_return_pct: float
    win_rate_pct: float
    max_drawdown_pct: float
    trade_count: int
    profit_factor: float | None = None
    sharpe_ratio: float | None = None
    observed_at: datetime


class ScorePolicyCreateIn(ContractModel):
    version: str = Field(min_length=1, max_length=24)
    min_trades: int = Field(ge=0)
    weights: dict[str, float]
    formula: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_weights(self) -> "ScorePolicyCreateIn":
        allowed = {
            "total_return_pct",
            "win_rate_pct",
            "max_drawdown_pct",
            "profit_factor",
            "sharpe_ratio",
        }
        if not self.weights or not set(self.weights).issubset(allowed):
            raise ValueError("weights contain unsupported metrics")
        if any(value < 0 for value in self.weights.values()):
            raise ValueError("weights must be non-negative")
        if abs(sum(self.weights.values()) - 1.0) > 1e-9:
            raise ValueError("weights must sum to 1.0")
        return self


class NewsItemOut(ContractModel):
    id: UUID
    title: str
    url: str
    published_at: datetime
    source_key: str
    source_name: str
    related_coins: list[str]
    sentiment: dict[str, Any] | None = None


class NewsAggregateOut(ContractModel):
    item_count: int
    analyzed_count: int
    coverage: float
    average_score: float | None = None
    label_counts: dict[str, int]


class NewsSourceOut(ContractModel):
    id: UUID
    source_key: str
    display_name: str
    kind: Literal["rss", "url", "html"]
    allowed_origin: str
    url_template: str
    is_active: bool
    last_collected_at: datetime | None = None


class NewsSourceCreateIn(ContractModel):
    source_key: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,62}[a-z0-9]$")
    display_name: str = Field(min_length=1, max_length=120)
    kind: Literal["rss", "url", "html"] = "rss"
    allowed_origin: str = Field(min_length=9, max_length=255)
    url_template: str = Field(min_length=9, max_length=2_000)


class NewsCollectIn(ContractModel):
    source_id: UUID | None = None


class SentimentBackfillIn(ContractModel):
    limit: int = Field(default=200, ge=1, le=200)
    source_ids: list[UUID] = Field(default_factory=list, max_length=50)
    coins: list[str] = Field(default_factory=list, max_length=20)


class SentimentPredictIn(ContractModel):
    text: str = Field(min_length=1, max_length=10_000)


class SentimentPredictOut(ContractModel):
    label: Literal["POSITIVE", "NEUTRAL", "NEGATIVE"]
    score: float = Field(ge=0, le=1)
    model: str
    model_version: str
    received_at: datetime


class NewsStrategyMix(ContractModel):
    positive: int = Field(ge=0, le=100)
    neutral: int = Field(ge=0, le=100)
    negative: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def percentages_must_sum_to_100_when_present(self) -> "NewsStrategyMix":
        total = self.positive + self.neutral + self.negative
        if total not in {0, 100}:
            raise ValueError("sentiment percentages must sum to 100")
        return self


class NewsStrategyCoverage(ContractModel):
    items_total: int = Field(ge=0, le=10_000)
    items_analyzed: int = Field(ge=0, le=10_000)
    items_unanalyzed: int = Field(ge=0, le=10_000)

    @model_validator(mode="after")
    def counts_must_be_consistent(self) -> "NewsStrategyCoverage":
        if self.items_analyzed + self.items_unanalyzed != self.items_total:
            raise ValueError("coverage counts are inconsistent")
        return self


class NewsStrategyAnalysisIn(ContractModel):
    sentiment_mix: NewsStrategyMix
    coverage: NewsStrategyCoverage
    average_score: float | None = Field(default=None, ge=0, le=1)
    model: Literal["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-5-mini"] = "gpt-4o-mini"


class NewsStrategyAnalysisOut(ContractModel):
    reasoning: str = Field(min_length=1, max_length=2_000)
    result: str = Field(min_length=2, max_length=8_000)
    model: str
    model_version: str
