"""Evaluation contracts (float64).

Mirrors `server/internal/domain/evaluation/contract.go`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from ..backtest import EquityPoint, TradeFact
from ..common import Decimal


@dataclass
class EvaluationInput:
    run_id: UUID
    initial_equity: Decimal
    trades: list[TradeFact] = field(default_factory=list)
    equity_points: list[EquityPoint] = field(default_factory=list)


@dataclass
class EvaluationPolicy:
    evaluator_version: str = ""
    periods_per_year: int = 0
    zero_pnl_counts_as_win: bool = False
    stddev_ddof: int = 1
    min_periods_for_sharpe: int = 0
    risk_free_rate: Decimal = 0.0


@dataclass
class Evaluation:
    backtest_run_id: UUID
    evaluator_version: str
    total_return_pct: Decimal
    win_rate_pct: Decimal
    max_drawdown_pct: Decimal
    trade_count: int
    open_trade_count: int
    profit_factor: Decimal | None = None
    sharpe_ratio: Decimal | None = None
    avg_trade_pct: Decimal | None = None


class Evaluator(Protocol):
    def evaluate(self, input_: EvaluationInput, policy: EvaluationPolicy) -> Evaluation: ...
