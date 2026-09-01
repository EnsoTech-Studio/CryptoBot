"""Canonical BBO-limit backtest engine (float64, deterministic).

Implements the full execution fidelity of `specs/backtest.md` (rules R1–R3 of
`specs/python-research.md`):

- **Event merge** by `(eventTime, priority, sourceSequence)` — BBO priority 0 is
  always applied before `CandleClosed` priority 1 at the same event time, so an
  intent created by a signal can only cross quotes from the replay *future* of
  that decision (AC-02, no look-ahead).
- **BBO LIMIT crossing** on the executable side only: BUY fills when
  `ask <= limit`, SELL fills when `bid >= limit`; the fill price is the
  executable side (AC-03). Candle closes are never used as fills.
- **One-net position state machine** FLAT/PENDING_LONG/PENDING_SHORT/LONG/
  PENDING_EXIT: flat BUY opens LONG, flat SELL opens SHORT, opposite signal
  creates a LIMIT exit, same-side signals are recorded but never add to the
  position (AC-05).
- **Fixed notional sizing** `quantity = fixed_notional / limit_price`, fee
  `fill_price * quantity * fee_bps / 10_000` on both entry and exit, adverse
  slippage optional (AC-04/AC-10).
- **Risk policy seam**: SL/TP levels are frozen at entry and triggered only by
  executable BBO sides; simultaneous triggers resolve by `intrabar_priority`
  (default `stop_loss_first`).
- **End of sample**: `last_executable_bbo` settles an open LONG at the final
  bid and an open SHORT at the final ask with `exit_reason=end_of_sample`;
  missing prior/final BBO raises `missing_prior_bbo`/`missing_final_bbo`
  deterministically instead of guessing (AC-06/AC-07).
- **Equity curve**: mark-to-market after every merged event boundary using the
  latest executable quote; drawdown relative to the running peak (which starts
  at `initial_equity`).

The engine is a pure function of `(snapshot, candles, bbo)`: no wall clock, no
random, no network, no DB, no shared mutable state. `duration_ms` is diagnostics
only and is excluded from `canonical_result_hash`. Equity falling to <= 0 stops
the replay early (liquidation); facts recorded so far stay valid and the open
position still settles at the final executable quote when one exists.

Semantics chosen where the spec leaves freedom (documented for review):

- a signal while an *entry* is still pending is recorded but does not stack or
  replace the pending entry (one active entry);
- a repeated opposite signal while an exit is pending replaces the pending exit
  (the old order is `CANCELLED`, a fresh LIMIT exit is created) — every opposite
  signal creates a LIMIT exit and only one order may be active;
- `run_signals` records non-HOLD signals only (they are the BUY/SELL markers);
- risk triggers are evaluated on each quote **before** pending-order crossing,
  and a triggered SL/TP cancels any pending strategy exit — risk limits win
  within one event boundary.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from ..domain.backtest import (
    EquityPoint,
    ExperimentSnapshot,
    OrderFact,
    Result,
    SignalRecord,
    TradeFact,
)
from ..domain.common import (
    ACTION_BUY,
    ACTION_SELL,
    ERR_DATASET_TOO_LARGE,
    ERR_INSUFFICIENT_CANDLES,
    ERR_INVALID_BBO_REPLAY,
    ERR_INVALID_SIGNAL,
    ERR_MISSING_FINAL_BBO,
    ERR_MISSING_PRIOR_BBO,
    ERR_STRATEGY_EXCEPTION,
    ERR_VALIDATION,
    EXIT_END_OF_SAMPLE,
    EXIT_SIGNAL,
    EXIT_STOP_LOSS,
    EXIT_TAKE_PROFIT,
    FILL_POLICY_BBO_LIMIT,
    OPEN_POSITION_DISCARD,
    OPEN_POSITION_LAST_EXECUTABLE_BBO,
    OPEN_POSITION_MARK_UNREALIZED,
    POSITION_POLICY_ONE_NET,
    TRADE_SIDE_LONG,
    TRADE_SIDE_SHORT,
    Decimal,
    DomainError,
    TradeSide,
)
from ..domain.common.canonical import canonical_json
from ..domain.indicator import DeterministicLibrary, IndicatorView, Library
from ..domain.market import BBO, Candle, CausalCandles
from ..domain.sentiment import NewsSentimentWindow
from ..domain.strategy import (
    AnalysisContext,
    ChildDefinition,
    CombinationPolicy,
    CompositeDefinition,
    Reference,
    Registry,
    ResolvedSignal,
    Signal,
)
from ..domain.strategy.composite import MajorityVoteCombiner, WeightedVoteCombiner

MAX_CANDLES = 20_000  # specs/backtest.md — hiệu năng bound
_BPS = 10_000.0
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)

_COMBINERS = {"weighted_vote": WeightedVoteCombiner, "majority_vote": MajorityVoteCombiner}


def _ms(moment: datetime) -> int:
    """Exact milliseconds since epoch — integer arithmetic, never float."""
    return (moment - _EPOCH) // timedelta(milliseconds=1)


def json_key(params: dict[str, Any]) -> str:
    """Canonical params key for duplicate-child detection (key order ignored)."""
    return json.dumps(params, sort_keys=True)


# ----------------------------------------------------------------------------
# replay plan
# ----------------------------------------------------------------------------


@dataclass
class _ResolvedChild:
    reference: Reference
    params: dict[str, Any]
    weight: Decimal
    strategy: Any


@dataclass
class _Plan:
    """Strategy plan resolved once per run: simple or composite."""

    params: dict[str, Any]
    requirements: list[str]
    warm_up: int
    strategy: Any = None  # simple strategy
    children: list[_ResolvedChild] | None = None  # composite children
    combiner: Any = None
    combination: CombinationPolicy | None = None

    def is_composite(self) -> bool:
        return self.children is not None


# ----------------------------------------------------------------------------
# merged replay events
# ----------------------------------------------------------------------------


def merged_events(candles: list[Candle], bbo: list[BBO]):
    """Yield ``(event_ms, event_time, kind, payload)`` in causal order.

    Sort key is ``(eventTime, priority, sourceSequence)`` with BBO priority 0
    before `CandleClosed` priority 1. Both inputs are pre-validated monotonic,
    so this two-pointer merge is deterministic without unordered sorting.
    Payload is the `BBO` for quote events and ``(index, candle)`` for close
    events.
    """
    i = j = 0
    n_candles, n_bbo = len(candles), len(bbo)
    while i < n_candles and j < n_bbo:
        candle, quote = candles[i], bbo[j]
        candle_ms, quote_ms = _ms(candle.close_time), _ms(quote.event_time)
        if quote_ms <= candle_ms:  # BBO priority 0 wins ties (AC-02)
            yield quote_ms, quote.event_time, "bbo", quote
            j += 1
        else:
            yield candle_ms, candle.close_time, "candle", (i, candle)
            i += 1
    while i < n_candles:
        yield (
            _ms(candles[i].close_time),
            candles[i].close_time,
            "candle",
            (i, candles[i]),
        )
        i += 1
    while j < n_bbo:
        yield _ms(bbo[j].event_time), bbo[j].event_time, "bbo", bbo[j]
        j += 1


# ----------------------------------------------------------------------------
# position simulator (fill-policy seam)
# ----------------------------------------------------------------------------


@dataclass
class _Position:
    sequence_no: int
    side: TradeSide
    quantity: Decimal
    entry_time: datetime
    entry_price: Decimal
    entry_fee: Decimal
    entry_slippage: Decimal
    signal_t: datetime | None
    sl_price: Decimal | None = None
    tp_price: Decimal | None = None


@dataclass
class _PendingOrder:
    sequence_no: int
    kind: str  # 'entry' | 'exit'
    action: str  # BUY | SELL
    position_side: TradeSide  # side this order opens (entry) or closes (exit)
    limit_price: Decimal
    quantity: Decimal
    created_at: datetime
    signal_t: datetime | None


class _PositionSimulator:
    """One-net position state machine + BBO-limit crossing + equity marks."""

    def __init__(self, snapshot: ExperimentSnapshot) -> None:
        self._snapshot = snapshot
        self.cash = snapshot.initial_equity
        self.position: _Position | None = None
        self.pending: _PendingOrder | None = None
        self.has_quote = False
        self.bid: Decimal = 0.0
        self.ask: Decimal = 0.0
        self.quote_time: datetime | None = None
        self.trades: list[TradeFact] = []
        self.orders: list[OrderFact] = []
        self._order_seq = 0
        self._trade_seq = 0
        self._peak = snapshot.initial_equity

    # -- quote application ----------------------------------------------------

    def apply_quote(self, quote: BBO) -> None:
        self.bid, self.ask = quote.bid, quote.ask
        self.quote_time = quote.event_time
        self.has_quote = True
        if self.position is not None:
            self._check_risk_triggers()
        if self.pending is not None:
            self._try_cross()

    # -- signal intents ---------------------------------------------------------

    def on_signal(self, action: str, limit_price: Decimal, at: datetime) -> None:
        if self.position is None and self.pending is None:
            side = TRADE_SIDE_LONG if action == ACTION_BUY else TRADE_SIDE_SHORT
            self._new_order("entry", action, side, limit_price, at)
            return
        if self.position is None:
            return  # entry already pending: one active entry, signal only recorded
        opposite = (self.position.side == TRADE_SIDE_LONG and action == ACTION_SELL) or (
            self.position.side == TRADE_SIDE_SHORT and action == ACTION_BUY
        )
        if not opposite:
            return  # same-side signal: recorded, never adds to the position (AC-05)
        if self.pending is not None:
            # repeated opposite signal: replace the pending exit limit
            self._emit_order(self.pending, "CANCELLED")
        # an exit closes the whole open position: its quantity is the position
        # quantity, never fixed_notional / exit_limit
        self._new_order(
            "exit", action, self.position.side, limit_price, at, self.position.quantity
        )

    def _new_order(
        self,
        kind: str,
        action: str,
        position_side: TradeSide,
        limit_price: Decimal,
        at: datetime,
        quantity: Decimal | None = None,
    ) -> None:
        self._order_seq += 1
        self.pending = _PendingOrder(
            sequence_no=self._order_seq,
            kind=kind,
            action=action,
            position_side=position_side,
            limit_price=limit_price,
            quantity=(
                quantity if quantity is not None else self._snapshot.fixed_notional / limit_price
            ),
            created_at=at,
            signal_t=at,
        )

    def _emit_order(self, order: _PendingOrder, status: str) -> None:
        self.orders.append(
            OrderFact(
                sequence_no=order.sequence_no,
                side=order.position_side,
                action=order.action,
                created_at=order.created_at,
                limit_price=order.limit_price,
                status=status,
            )
        )

    # -- fills -------------------------------------------------------------------

    def _try_cross(self) -> None:
        order = self.pending
        assert order is not None
        if order.action == ACTION_BUY and self.ask <= order.limit_price:
            self._fill(order, self.ask)
        elif order.action == ACTION_SELL and self.bid >= order.limit_price:
            self._fill(order, self.bid)

    def _fill(self, order: _PendingOrder, raw_price: Decimal) -> None:
        self.pending = None
        effective, fee, slippage_cost = self._execution_costs(
            raw_price, order.action, order.quantity
        )
        if order.kind == "entry":
            self._open_position(order, effective, fee, slippage_cost)
        else:
            self._close_position(effective, fee, slippage_cost, EXIT_SIGNAL)
        self._emit_order(order, "FILLED")

    def _execution_costs(
        self, raw_price: Decimal, action: str, quantity: Decimal
    ) -> tuple[Decimal, Decimal, Decimal]:
        adverse = raw_price * (self._snapshot.slippage_bps / _BPS)
        effective = raw_price + adverse if action == ACTION_BUY else raw_price - adverse
        fee = effective * quantity * (self._snapshot.fee_bps / _BPS)
        return effective, fee, abs(adverse) * quantity

    def _open_position(
        self,
        order: _PendingOrder,
        effective: Decimal,
        fee: Decimal,
        slippage_cost: Decimal,
    ) -> None:
        if order.position_side == TRADE_SIDE_LONG:
            self.cash -= effective * order.quantity + fee
        else:
            self.cash += effective * order.quantity - fee
        risk = self._snapshot.risk_policy
        sl_price = tp_price = None
        if risk is not None:
            if risk.stop_loss_pct is not None:
                sl_price = (
                    effective * (1 - risk.stop_loss_pct / 100)
                    if order.position_side == TRADE_SIDE_LONG
                    else effective * (1 + risk.stop_loss_pct / 100)
                )
            if risk.take_profit_pct is not None:
                tp_price = (
                    effective * (1 + risk.take_profit_pct / 100)
                    if order.position_side == TRADE_SIDE_LONG
                    else effective * (1 - risk.take_profit_pct / 100)
                )
        self._trade_seq += 1
        self.position = _Position(
            sequence_no=self._trade_seq,
            side=order.position_side,
            quantity=order.quantity,
            entry_time=self.quote_time or order.created_at,
            entry_price=effective,
            entry_fee=fee,
            entry_slippage=slippage_cost,
            signal_t=order.signal_t,
            sl_price=sl_price,
            tp_price=tp_price,
        )
        self.trades.append(
            TradeFact(
                sequence_no=self._trade_seq,
                side=order.position_side,
                entry_time=self.position.entry_time,
                entry_price=effective,
                quantity=order.quantity,
                fee_paid=fee,
                slippage_cost=slippage_cost,
                signal_t=order.signal_t,
                sl_price=sl_price,
                tp_price=tp_price,
            )
        )

    def _close_position(
        self,
        exit_price: Decimal,
        exit_fee: Decimal,
        exit_slippage: Decimal,
        exit_reason: str,
    ) -> None:
        position = self.position
        assert position is not None
        if position.side == TRADE_SIDE_LONG:
            self.cash += exit_price * position.quantity - exit_fee
        else:
            self.cash -= exit_price * position.quantity + exit_fee
        direction = 1.0 if position.side == TRADE_SIDE_LONG else -1.0
        pnl_abs = (
            direction * (exit_price - position.entry_price) * position.quantity
            - position.entry_fee
            - exit_fee
        )
        pnl_pct = pnl_abs / (position.entry_price * position.quantity) * 100
        fact = self.trades[position.sequence_no - 1]
        fact.exit_time = self.quote_time
        fact.exit_price = exit_price
        fact.fee_paid = position.entry_fee + exit_fee
        fact.slippage_cost = position.entry_slippage + exit_slippage
        fact.pnl_absolute = pnl_abs
        fact.pnl_percent = pnl_pct
        fact.exit_reason = exit_reason
        self.position = None

    # -- risk triggers -------------------------------------------------------------

    def _check_risk_triggers(self) -> None:
        position = self.position
        if position is None or (position.sl_price is None and position.tp_price is None):
            return
        if position.side == TRADE_SIDE_LONG:
            sl_hit = position.sl_price is not None and self.bid <= position.sl_price
            tp_hit = position.tp_price is not None and self.bid >= position.tp_price
            exit_price = self.bid
        else:
            sl_hit = position.sl_price is not None and self.ask >= position.sl_price
            tp_hit = position.tp_price is not None and self.ask <= position.tp_price
            exit_price = self.ask
        if not sl_hit and not tp_hit:
            return
        risk = self._snapshot.risk_policy
        priority = (risk.intrabar_priority if risk is not None else "") or "stop_loss_first"
        if sl_hit and (not tp_hit or priority == "stop_loss_first"):
            reason = EXIT_STOP_LOSS
        else:
            reason = EXIT_TAKE_PROFIT
        if self.pending is not None:
            self._emit_order(self.pending, "CANCELLED")
            self.pending = None
        action = ACTION_SELL if position.side == TRADE_SIDE_LONG else ACTION_BUY
        effective, fee, slippage_cost = self._execution_costs(
            exit_price, action, position.quantity
        )
        self._close_position(effective, fee, slippage_cost, reason)

    # -- equity & settlement ----------------------------------------------------------

    def mark_equity(self, event_time: datetime, points: list[EquityPoint]) -> bool:
        """Append the mark for an event boundary; True => liquidated (equity <= 0).

        `equity_points` PK is `(run, point_time)` and the merge rule makes
        same-timestamp boundaries deliberate (BBO at the exact candle-close
        ms), so a mark at an already-marked timestamp replaces the previous
        mark — the latest state at a boundary is the mark of record.
        """
        if not self.has_quote:
            raise DomainError(
                ERR_MISSING_PRIOR_BBO,
                f"no executable BBO before the mark at {event_time.isoformat()}",
            )
        equity = self.cash
        if self.position is not None:
            if self.position.side == TRADE_SIDE_LONG:
                equity += self.bid * self.position.quantity
            else:
                equity -= self.ask * self.position.quantity
        self._peak = max(self._peak, equity)
        drawdown = (equity - self._peak) / self._peak * 100
        point = EquityPoint(point_time=event_time, equity=equity, drawdown_pct=drawdown)
        if points and points[-1].point_time == event_time:
            points[-1] = point
        else:
            points.append(point)
        return equity <= 0

    def settle(self, points: list[EquityPoint]) -> None:
        if self.pending is not None:
            self._emit_order(
                self.pending, "EXPIRED" if self.pending.kind == "entry" else "CANCELLED"
            )
            self.pending = None
        if self.position is None:
            return
        policy = self._snapshot.open_position_at_end
        if policy == OPEN_POSITION_MARK_UNREALIZED:
            return  # trade stays open (exit_time NULL); last mark is the unrealized value
        if policy == OPEN_POSITION_DISCARD:
            self.trades.pop(self.position.sequence_no - 1)
            self.position = None
            return
        if not self.has_quote:
            raise DomainError(
                ERR_MISSING_FINAL_BBO,
                "open position at end of replay but no executable BBO for settlement",
            )
        exit_price = self.bid if self.position.side == TRADE_SIDE_LONG else self.ask
        action = ACTION_SELL if self.position.side == TRADE_SIDE_LONG else ACTION_BUY
        effective, fee, slippage_cost = self._execution_costs(
            exit_price, action, self.position.quantity
        )
        self._close_position(effective, fee, slippage_cost, EXIT_END_OF_SAMPLE)
        # replace the pre-settlement mark at the final event time with the
        # realized-cash mark (keeps equity point timestamps unique)
        if points:
            settled_at = points[-1].point_time
            points.pop()
            drawdown = (self.cash - self._peak) / self._peak * 100
            points.append(
                EquityPoint(point_time=settled_at, equity=self.cash, drawdown_pct=drawdown)
            )


# ----------------------------------------------------------------------------
# engine
# ----------------------------------------------------------------------------


class DeterministicEngine:
    """`BacktestEngine` implementation — see module docstring for semantics."""

    def __init__(self, registry: Registry | None = None, library: Library | None = None) -> None:
        if registry is None:
            from ..domain.strategy.plugins.catalog import default_registry

            registry = default_registry()
        self._registry = registry
        self._library = library if library is not None else DeterministicLibrary()

    def with_runtime_spec(self, spec: dict[str, Any]) -> "DeterministicEngine":
        from ..domain.strategy.generated import DeclarativeStrategy
        from ..domain.strategy.plugins.catalog import default_registry

        registry = default_registry()
        registry.register(lambda: DeclarativeStrategy(spec))
        return DeterministicEngine(registry, self._library)

    def run(
        self,
        snapshot: ExperimentSnapshot,
        candles: list[Candle],
        bbo: list[BBO],
        sentiment_windows: list[NewsSentimentWindow | None] | None = None,
    ) -> Result:
        started = time.perf_counter()
        plan = self._resolve_plan(snapshot)
        self._validate(snapshot, candles, bbo, plan.warm_up)
        if sentiment_windows is not None and len(sentiment_windows) != len(candles):
            raise DomainError(ERR_VALIDATION, "sentiment window series must align with candles")
        series = self._library.precompute([c.close for c in candles], plan.requirements)

        sim = _PositionSimulator(snapshot)
        equity_points: list[EquityPoint] = []
        signals: list[SignalRecord] = []
        market = snapshot.market

        for _, event_time, kind, payload in merged_events(candles, bbo):
            if kind == "bbo":
                sim.apply_quote(payload)
            else:
                index, candle = payload
                self._on_candle_closed(
                    snapshot,
                    plan,
                    series,
                    candles,
                    sentiment_windows,
                    index,
                    candle,
                    market,
                    sim,
                    signals,
                )
            if sim.mark_equity(event_time, equity_points):
                break  # liquidated: facts so far stay valid, settle below

        sim.settle(equity_points)

        return Result(
            trades=sim.trades,
            signals=signals,
            orders=sim.orders,
            equity_points=equity_points,
            candles_read=len(candles),
            warm_up_candles=plan.warm_up,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )

    # -- resolution -----------------------------------------------------------

    def _resolve_plan(self, snapshot: ExperimentSnapshot) -> _Plan:
        candidate = snapshot.candidate_definition
        if isinstance(candidate, CompositeDefinition):
            children: list[_ResolvedChild] = []
            requirements: set[str] = set()
            warm_up = 0
            self._validate_composite(candidate)
            seen: set[tuple] = set()
            for child in candidate.children:
                if not isinstance(child, ChildDefinition):
                    raise DomainError(
                        ERR_VALIDATION, "composite children must be ChildDefinition entries"
                    )
                key = (child.strategy_id, child.version, json_key(child.parameters or {}))
                if key in seen:
                    raise DomainError(ERR_VALIDATION, f"duplicate exact child {key[0]}@{key[1]}")
                seen.add(key)
                strategy = self._registry.resolve(child.strategy_id, child.version)
                if strategy.definition().is_composite:
                    raise DomainError(ERR_VALIDATION, "nested composite children are not allowed")
                params = dict(child.parameters or {})
                requirements.update(self._safe_requirements(strategy, params))
                warm_up = max(warm_up, self._safe_warm_up(strategy, params))
                children.append(
                    _ResolvedChild(
                        reference=Reference(child.strategy_id, child.version),
                        params=params,
                        weight=child.weight,
                        strategy=strategy,
                    )
                )
            policy = candidate.combination
            combiner_cls = _COMBINERS.get(policy.policy)
            if combiner_cls is None:
                raise DomainError(ERR_VALIDATION, f"unknown combination policy {policy.policy!r}")
            return _Plan(
                params={},
                requirements=sorted(requirements),
                warm_up=warm_up,
                children=children,
                combiner=combiner_cls(),
                combination=policy,
            )
        params = dict(candidate) if isinstance(candidate, dict) else {}
        strategy = self._registry.resolve(snapshot.strategy.strategy_id, snapshot.strategy.version)
        return _Plan(
            params=params,
            requirements=self._safe_requirements(strategy, params),
            warm_up=self._safe_warm_up(strategy, params),
            strategy=strategy,
        )

    @staticmethod
    def _validate_composite(candidate: CompositeDefinition) -> None:
        """Snapshot-schema validation per `specs/composite-strategy.md`."""
        if not 2 <= len(candidate.children) <= 5:
            raise DomainError(
                ERR_VALIDATION, f"composite requires 2-5 children, got {len(candidate.children)}"
            )
        total = 0.0
        for child in candidate.children:
            if child.weight is None or child.weight < 0:
                raise DomainError(ERR_VALIDATION, "child weight must be >= 0")
            total += child.weight
        if total <= 0:
            raise DomainError(ERR_VALIDATION, "total child weight must be > 0")
        threshold = candidate.combination.threshold
        if threshold is None or not 0 <= threshold <= 1:
            raise DomainError(ERR_VALIDATION, f"threshold {threshold!r} outside [0,1]")

    @staticmethod
    def _safe_requirements(strategy: Any, params: dict[str, Any]) -> list[str]:
        # plugin parameter validation (e.g. fast/slow < 1) must surface as a
        # deterministic ERR_VALIDATION, not as a retryable crash
        try:
            return DeterministicEngine._requirements_of(strategy, params)
        except DomainError:
            raise
        except Exception as exc:
            raise DomainError(ERR_VALIDATION, f"invalid parameters: {exc}") from exc

    @staticmethod
    def _safe_warm_up(strategy: Any, params: dict[str, Any]) -> int:
        try:
            return DeterministicEngine._warm_up_of(strategy, params)
        except DomainError:
            raise
        except Exception as exc:
            raise DomainError(ERR_VALIDATION, f"invalid parameters: {exc}") from exc

    @staticmethod
    def _requirements_of(strategy: Any, params: dict[str, Any]) -> list[str]:
        dynamic = getattr(strategy, "requirements", None)
        if callable(dynamic):
            return list(dynamic(params))
        return list(strategy.definition().input_requirements)

    @staticmethod
    def _warm_up_of(strategy: Any, params: dict[str, Any]) -> int:
        warm_up = strategy.definition().warm_up_candles
        if callable(warm_up):
            return int(warm_up(params))
        if isinstance(warm_up, int):
            return warm_up
        return 0

    # -- validation --------------------------------------------------------------

    @staticmethod
    def _validate(
        snapshot: ExperimentSnapshot,
        candles: list[Candle],
        bbo: list[BBO],
        warm_up: int,
    ) -> None:
        if snapshot.initial_equity <= 0:
            raise DomainError(ERR_VALIDATION, "initial_equity must be > 0")
        if snapshot.fixed_notional <= 0:
            raise DomainError(ERR_VALIDATION, "fixed_notional must be > 0")
        if snapshot.fee_bps < 0 or snapshot.slippage_bps < 0:
            raise DomainError(ERR_VALIDATION, "fee_bps/slippage_bps must be >= 0")
        if snapshot.leverage != 1.0:
            raise DomainError(ERR_VALIDATION, "only leverage 1x is supported")
        if snapshot.fill_policy != FILL_POLICY_BBO_LIMIT:
            raise DomainError(ERR_VALIDATION, f"unsupported fill_policy {snapshot.fill_policy!r}")
        if snapshot.position_policy != POSITION_POLICY_ONE_NET:
            raise DomainError(
                ERR_VALIDATION, f"unsupported position_policy {snapshot.position_policy!r}"
            )
        if snapshot.open_position_at_end not in (
            OPEN_POSITION_LAST_EXECUTABLE_BBO,
            OPEN_POSITION_DISCARD,
            OPEN_POSITION_MARK_UNREALIZED,
        ):
            raise DomainError(
                ERR_VALIDATION,
                f"unsupported open_position_at_end {snapshot.open_position_at_end!r}",
            )
        if len(candles) > MAX_CANDLES:
            raise DomainError(
                ERR_DATASET_TOO_LARGE,
                f"dataset of {len(candles)} candles exceeds the {MAX_CANDLES}-candle limit",
            )
        if len(candles) < max(warm_up, 1):
            raise DomainError(
                ERR_INSUFFICIENT_CANDLES,
                f"{len(candles)} candles are below the warm-up requirement of {warm_up}",
            )
        previous_open: datetime | None = None
        for candle in candles:
            if previous_open is not None and candle.open_time <= previous_open:
                raise DomainError(
                    ERR_INVALID_BBO_REPLAY, "candles must have unique increasing open_time"
                )
            previous_open = candle.open_time
        previous_key: tuple[int, int] | None = None
        for quote in bbo:
            if quote.bid <= 0 or quote.ask <= 0 or quote.bid > quote.ask:
                raise DomainError(
                    ERR_INVALID_BBO_REPLAY,
                    f"BBO at {quote.event_time.isoformat()} has invalid bid/ask",
                )
            key = (_ms(quote.event_time), quote.source_sequence)
            if previous_key is not None and key <= previous_key:
                raise DomainError(ERR_INVALID_BBO_REPLAY, "BBO replay must be monotonic")
            previous_key = key

    # -- signal handling ------------------------------------------------------------

    def _on_candle_closed(
        self,
        snapshot: ExperimentSnapshot,
        plan: _Plan,
        series: dict[str, list[Decimal]],
        candles: list[Candle],
        sentiment_windows: list[NewsSentimentWindow | None] | None,
        index: int,
        candle: Candle,
        market: Any,
        sim: _PositionSimulator,
        signals: list[SignalRecord],
    ) -> None:
        if index < plan.warm_up:
            return
        try:
            signal, child_payload = self._analyze(
                plan, series, candles, sentiment_windows, index, candle, market
            )
        except DomainError:
            raise
        except Exception as exc:
            raise DomainError(
                ERR_STRATEGY_EXCEPTION,
                f"strategy raised {type(exc).__name__}: {exc}",
                cause=exc,
            ) from exc

        if signal.action not in (ACTION_BUY, ACTION_SELL):
            return  # HOLD: no run_signals row, no order
        if signal.price is None or signal.price <= 0:
            raise DomainError(
                ERR_INVALID_SIGNAL,
                f"{signal.action} signal without a positive price at candle {index}",
            )
        signals.append(
            SignalRecord(
                candle_time=candle.close_time,
                action=signal.action,
                price=signal.price,
                notional=snapshot.fixed_notional,
                confidence=signal.confidence,
                child_signals=child_payload,
            )
        )
        sim.on_signal(signal.action, signal.price, candle.close_time)

    def _analyze(
        self,
        plan: _Plan,
        series: dict[str, list[Decimal]],
        candles: list[Candle],
        sentiment_windows: list[NewsSentimentWindow | None] | None,
        index: int,
        candle: Candle,
        market: Any,
    ) -> tuple[Signal, Any]:
        context = AnalysisContext(
            provider=market.provider,
            symbol=market.symbol,
            timeframe=market.timeframe,
            candles=CausalCandles(candles, index),
            index=index,
            indicators=IndicatorView(series, index),
            news_sentiment=None if sentiment_windows is None else sentiment_windows[index],
            params=plan.params,
        )
        if plan.is_composite():
            resolved: list[ResolvedSignal] = []
            for child in plan.children:
                context.params = child.params
                child_signal = child.strategy.analyze(context)
                resolved.append(
                    ResolvedSignal(
                        strategy_id=child.reference.strategy_id,
                        version=child.reference.version,
                        signal=child_signal,
                        weight=child.weight,
                    )
                )
            context.params = plan.params
            combined = plan.combiner.combine(resolved, plan.combination)
            # child_signals evidence per specs/composite-strategy.md §Evidence:
            # child action/confidence/price/weight + composite score/action so
            # the combination is reproducible from the stored row (AC-09)
            score = (
                combined.evidence.get("score")
                if isinstance(combined.evidence, dict) and "score" in combined.evidence
                else combined.confidence
            )
            payload = {
                "children": [
                    {
                        "strategy_id": r.strategy_id,
                        "version": r.version,
                        "action": r.signal.action,
                        "confidence": r.signal.confidence,
                        "price": r.signal.price,
                        "weight": r.weight,
                    }
                    for r in resolved
                ],
                "score": score,
                "action": combined.action,
            }
            return combined, payload
        return plan.strategy.analyze(context), None


# ----------------------------------------------------------------------------
# canonical result hash (AC-01)
# ----------------------------------------------------------------------------


def canonical_result_hash(result: Result) -> str:
    """Deterministic sha256 over the canonical result.

    `duration_ms` is excluded — wall-clock diagnostics must not break the
    byte-identical replay requirement.
    """
    digest = hashlib.sha256()
    digest.update(f"v1|{result.candles_read}|{result.warm_up_candles}".encode())
    for prefix, items in (
        (b"t", result.trades),
        (b"s", result.signals),
        (b"o", result.orders),
    ):
        for item in items:
            digest.update(b"|")
            digest.update(prefix)
            digest.update(canonical_json(item))
    for point in result.equity_points:
        digest.update(b"|e")
        digest.update(canonical_json(point))
    return digest.hexdigest()
