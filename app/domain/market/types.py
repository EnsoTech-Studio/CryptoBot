"""Market value objects (float64).

Mirrors `server/internal/domain/market/types.go`. `Candle`/`BBO` are shared value
objects consumed by the backtest engine; realtime market data transport remains
owned by the Go backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..common import Decimal, Timeframe


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
    """Causal candle window — strategy may only read up to the current index."""

    def __init__(self, candles: list[Candle], index: int) -> None:
        raise NotImplementedError

    def at(self, index: int) -> Candle:
        raise NotImplementedError

    def __len__(self) -> int:
        raise NotImplementedError

    @property
    def index(self) -> int:
        raise NotImplementedError
