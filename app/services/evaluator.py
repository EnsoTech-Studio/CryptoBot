"""Evaluator — derives metrics from immutable trade/equity facts (float64).

Mirrors `specs/evaluation.md` (§B formulas, §Kịch bản lỗi):

- ``total_return_pct`` from the **final equity point**, never from summed PnL —
  fees, mark-to-market and final-BBO settlement already live in the curve;
- ``win_rate_pct`` over settled trades only; ``pnl_absolute == 0`` is not a win
  under policy v1; ``trade_count == 0`` returns ``0`` instead of dividing;
- ``max_drawdown_pct = min(drawdown_t)`` over the equity curve (in-position
  drawdowns included because the engine marks every event boundary);
- ``profit_factor`` is ``NULL`` when there is no settled loss (never
  ``Infinity``) and ``0`` when every settled trade loses;
- ``sharpe_ratio`` is annualized per-step over consecutive equity returns with
  ``policy.periods_per_year``; ``NULL`` when returns are flat, the sample is
  below ``min_periods_for_sharpe``, or the denominator is zero;
- ``avg_trade_pct`` is the mean settled ``pnl_percent``; ``NULL`` with no
  settled trades.

The evaluator never imports a strategy, never calls a clock, DB or network, and
takes ``initial_equity`` from the immutable input only (AC-07). Missing equity
points are a hard ``inconsistent_backtest_result`` error rather than metrics
computed from guesses.
"""

from __future__ import annotations

import math

from ..domain.backtest import EquityPoint, TradeFact
from ..domain.common import ERR_INCONSISTENT_RESULT, Decimal, DomainError
from ..domain.evaluation import Evaluation, EvaluationInput, EvaluationPolicy


class DeterministicEvaluator:
    def evaluate(self, input_: EvaluationInput, policy: EvaluationPolicy) -> Evaluation:
        if not input_.equity_points:
            raise DomainError(
                ERR_INCONSISTENT_RESULT,
                f"run {input_.run_id} has no equity points to evaluate",
            )
        initial = input_.initial_equity
        if initial <= 0:
            raise DomainError(ERR_INCONSISTENT_RESULT, "initial_equity must be > 0")

        final_equity = input_.equity_points[-1].equity
        settled = [t for t in input_.trades if t.exit_time is not None]
        open_trades = [t for t in input_.trades if t.exit_time is None]

        total_return_pct = (final_equity - initial) / initial * 100
        wins = [t for t in settled if t.pnl_absolute is not None and t.pnl_absolute > 0]
        win_rate_pct = (len(wins) / len(settled) * 100) if settled else 0.0

        max_drawdown_pct = min(
            (p.drawdown_pct for p in input_.equity_points if p.drawdown_pct is not None),
            default=0.0,
        )

        return Evaluation(
            backtest_run_id=input_.run_id,
            evaluator_version=policy.evaluator_version,
            total_return_pct=total_return_pct,
            win_rate_pct=win_rate_pct,
            max_drawdown_pct=max_drawdown_pct,
            trade_count=len(settled),
            open_trade_count=len(open_trades),
            profit_factor=self._profit_factor(settled),
            sharpe_ratio=self._sharpe_ratio(input_.equity_points, policy),
            avg_trade_pct=self._avg_trade_pct(settled),
        )

    @staticmethod
    def _profit_factor(settled: list[TradeFact]) -> Decimal | None:
        pnls = [t.pnl_absolute for t in settled if t.pnl_absolute is not None]
        gross_profit = sum(p for p in pnls if p > 0)
        gross_loss = sum(p for p in pnls if p < 0)
        if gross_loss == 0.0:
            return None  # no settled loss: NULL, not Infinity
        return gross_profit / abs(gross_loss)

    @staticmethod
    def _avg_trade_pct(settled: list[TradeFact]) -> Decimal | None:
        percents = [t.pnl_percent for t in settled if t.pnl_percent is not None]
        if not percents:
            return None
        return sum(percents) / len(percents)

    @staticmethod
    def _sharpe_ratio(points: list[EquityPoint], policy: EvaluationPolicy) -> Decimal | None:
        if policy.periods_per_year <= 0:
            return None  # unknown timeframe: annualization is meaningless, not zero
        min_periods = max(policy.min_periods_for_sharpe, 2)
        returns = [
            points[i].equity / points[i - 1].equity - 1 for i in range(1, len(points))
        ]
        if len(returns) < min_periods:
            return None
        mean = sum(returns) / len(returns)
        if policy.stddev_ddof >= len(returns):
            return None
        variance = sum((r - mean) ** 2 for r in returns) / (
            len(returns) - policy.stddev_ddof
        )
        stddev = math.sqrt(variance)
        if stddev == 0.0:
            return None  # flat equity: undefined, not zero
        periodic_rf = policy.risk_free_rate / policy.periods_per_year if policy.periods_per_year else 0.0
        excess = mean - periodic_rf
        sharpe = excess / stddev
        if policy.periods_per_year > 0:
            sharpe *= math.sqrt(policy.periods_per_year)
        return sharpe
