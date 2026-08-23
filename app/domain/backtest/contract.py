"""Backtest engine contracts (float64).

Mirrors `server/internal/domain/backtest/contract.go`. All numerics are Python
`float` (float64). Execution fidelity (BBO-limit crossing, `(eventTime, priority,
sourceSequence)` merge, final bid/ask settlement) follows `specs/backtest.md`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from ..common import (
    Action,
    Decimal,
    ExitReason,
    FillPolicy,
    OpenPositionPolicy,
    PositionPolicy,
    Timeframe,
    TradeSide,
)
from ..market import BBO, Candle
from ..strategy import Reference


@dataclass
class RiskPolicy:
    stop_loss_pct: Decimal | None = None
    take_profit_pct: Decimal | None = None
    intrabar_priority: str = ""


@dataclass
class MarketSnapshot:
    dataset_version: str
    revision_no: int
    provider: str
    symbol: str
    timeframe: Timeframe
    range_from: datetime
    range_to: datetime
    candle_count: int
    content_hash: str
    bbo_content_hash: str | None = None


@dataclass
class ExperimentSnapshot:
    experiment_id: UUID
    owner_id: UUID | None
    strategy: Reference
    candidate_definition: Any | None
    candidate_hash: str
    market: MarketSnapshot
    initial_equity: Decimal
    fixed_notional: Decimal
    leverage: Decimal
    fee_bps: int
    slippage_bps: int
    fill_policy: FillPolicy
    position_policy: PositionPolicy
    open_position_at_end: OpenPositionPolicy
    risk_policy: RiskPolicy | None = None
    evaluator_version: str = ""
    created_at: datetime | None = None


@dataclass
class OrderFact:
    sequence_no: int
    side: TradeSide
    action: Action
    created_at: datetime
    limit_price: Decimal
    status: str


@dataclass
class TradeFact:
    sequence_no: int
    side: TradeSide
    entry_time: datetime
    entry_price: Decimal
    quantity: Decimal
    fee_paid: Decimal
    slippage_cost: Decimal
    signal_t: datetime | None = None
    exit_time: datetime | None = None
    exit_price: Decimal | None = None
    pnl_absolute: Decimal | None = None
    pnl_percent: Decimal | None = None
    exit_reason: ExitReason | None = None
    # SL/TP levels frozen at entry (design.md trades DDL CHECK: a stop_loss
    # exit requires sl_price, a take_profit exit requires tp_price)
    sl_price: Decimal | None = None
    tp_price: Decimal | None = None


@dataclass
class SignalRecord:
    candle_time: datetime
    action: Action
    price: Decimal | None = None
    notional: Decimal | None = None
    confidence: Decimal | None = None
    child_signals: Any | None = None


@dataclass
class EquityPoint:
    point_time: datetime
    equity: Decimal
    drawdown_pct: Decimal | None = None


@dataclass
class Result:
    trades: list[TradeFact] = field(default_factory=list)
    signals: list[SignalRecord] = field(default_factory=list)
    orders: list[OrderFact] = field(default_factory=list)
    equity_points: list[EquityPoint] = field(default_factory=list)
    candles_read: int = 0
    warm_up_candles: int = 0
    duration_ms: int = 0


BacktestResult = Result


class BacktestEngine(Protocol):
    def run(self, snapshot: ExperimentSnapshot, candles: list[Candle], bbo: list[BBO]) -> Result: ...
