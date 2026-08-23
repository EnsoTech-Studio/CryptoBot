"""Market value objects (float64).

Mirrors `server/internal/domain/market/types.go`. `Candle`/`BBO` are shared value
objects consumed by the backtest engine; realtime market data transport remains
owned by the Go backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..common import Decimal, LookAheadError, Timeframe


@dataclass
class MarketKey:
    provider: str
    symbol: str
    timeframe: Timeframe


@dataclass
class SubscriptionKey:
    market: MarketKey
    strategy_id: str | None = None
    strategy_version: str | None = None
    config_hash: str | None = None


@dataclass
class Candle:
    provider: str
    symbol: str
    timeframe: Timeframe
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    trade_count: int | None = None


@dataclass
class KlineUpdate:
    market: MarketKey
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    trade_count: int | None = None
    final: bool = False


@dataclass
class BBO:
    provider: str
    symbol: str
    event_time: datetime
    bid: Decimal
    bid_qty: Decimal
    ask: Decimal
    ask_qty: Decimal
    update_id: int | None = None
    source_sequence: int = 0


@dataclass
class CandleQuery:
    market: MarketKey
    range_from: datetime
    range_to: datetime
    limit: int


StreamKey = MarketKey


class CausalCandles:
    """Causal candle window — strategy may only read up to the current index.

    Rule R2 of `specs/python-research.md`: reading any candle past the cursor of
    the just-closed candle raises `LookAheadError` immediately (no silent
    look-ahead). The window length is `index + 1` — exactly the candles the
    strategy is allowed to see.
    """

    def __init__(self, candles: list[Candle], index: int) -> None:
        if index < 0 or index >= len(candles):
            raise ValueError(f"causal cursor {index} outside candles [0, {len(candles) - 1}]")
        self._candles = candles
        self._index = index

    def at(self, index: int) -> Candle:
        if index < 0 or index > self._index:
            raise LookAheadError(
                f"candle index {index} is outside the causal window [0, {self._index}]"
            )
        return self._candles[index]

    def __len__(self) -> int:
        return self._index + 1

    def __getitem__(self, index: int) -> Candle:
        return self.at(index)

    @property
    def index(self) -> int:
        return self._index
