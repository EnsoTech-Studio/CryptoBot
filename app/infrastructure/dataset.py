"""Fixture dataset loading for `data/formatted/<symbol>/<date>/` replay dirs.

Reads the verification fixture format (`ohlcv.csv` with `T,O,H,L,C,V` epoch-ms
columns and `bbo.csv` with `b,B,a,A,T`), aggregates the raw 1m OHLCV rows into
the requested timeframe, computes the SHA-256 content hashes the evidence
record requires (jira M2-03: "input-file SHA-256 ... evidence"), and builds the
immutable `Candle`/`BBO` lists the engine replays.

Conventions (specs/backtest.md):

- candle `close_time` = `open_time + timeframe_ms - 1` (Binance closed-candle
  boundary); the `CandleClosed` replay event fires at `close_time`;
- BBO rows without an exchange update ID get `source_sequence` = 1-based CSV
  row number — deterministic tie-break inside the event merge key.
"""

from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ..domain.common import ERR_INVALID_BBO_REPLAY, ERR_VALIDATION, DomainError, Timeframe
from ..domain.market import BBO, Candle

_TIMEFRAME_MS = {
    "1m": 60_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "2h": 7_200_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
}

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _utc(epoch_ms: int) -> datetime:
    return _EPOCH + timedelta(milliseconds=epoch_ms)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _epoch_ms(value: datetime) -> int:
    delta = value - _EPOCH
    return delta.days * 86_400_000 + delta.seconds * 1_000 + delta.microseconds // 1_000


def _resample_candles(candles: list[Candle], timeframe: Timeframe) -> list[Candle]:
    """Aggregate ordered raw 1m candles into non-overlapping timeframe bars."""

    if timeframe == "1m":
        return candles

    step_ms = _TIMEFRAME_MS[timeframe]
    aggregated: list[Candle] = []
    current_bucket_ms: int | None = None
    current: Candle | None = None
    for source in candles:
        source_bucket_ms = _epoch_ms(source.open_time) // step_ms * step_ms
        if source_bucket_ms != current_bucket_ms:
            current_bucket_ms = source_bucket_ms
            current = Candle(
                provider=source.provider,
                symbol=source.symbol,
                timeframe=timeframe,
                open_time=_utc(source_bucket_ms),
                close_time=_utc(source_bucket_ms + step_ms - 1),
                open=source.open,
                high=source.high,
                low=source.low,
                close=source.close,
                volume=source.volume,
                trade_count=source.trade_count,
            )
            aggregated.append(current)
            continue

        assert current is not None
        current.high = max(current.high, source.high)
        current.low = min(current.low, source.low)
        current.close = source.close
        current.volume += source.volume
        if current.trade_count is not None and source.trade_count is not None:
            current.trade_count += source.trade_count
        else:
            current.trade_count = None

    return aggregated


@dataclass
class DatasetInfo:
    dataset_version: str
    provider: str
    symbol: str
    timeframe: Timeframe
    range_from: datetime
    range_to: datetime
    candle_count: int
    content_hash: str
    bbo_content_hash: str


def load_fixture_dataset(
    directory: str | Path,
    provider: str = "binance",
    symbol: str = "SOLUSDT",
    timeframe: Timeframe = "1m",
) -> tuple[list[Candle], list[BBO], DatasetInfo]:
    directory = Path(directory)
    ohlcv_path = directory / "ohlcv.csv"
    bbo_path = directory / "bbo.csv"
    if not ohlcv_path.is_file() or not bbo_path.is_file():
        raise DomainError(ERR_VALIDATION, f"fixture dataset {directory} lacks ohlcv.csv/bbo.csv")
    if timeframe not in _TIMEFRAME_MS:
        raise DomainError(ERR_VALIDATION, f"unsupported fixture timeframe {timeframe!r}")
    step_ms = _TIMEFRAME_MS["1m"]

    candles: list[Candle] = []
    with ohlcv_path.open(newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        columns = {name: index for index, name in enumerate(header)}
        required = ("T", "O", "H", "L", "C", "V")
        missing = [name for name in required if name not in columns]
        if missing:
            raise DomainError(ERR_VALIDATION, f"ohlcv.csv missing columns {missing}")
        for row in reader:
            if not row:
                continue
            open_ms = int(row[columns["T"]])
            candles.append(
                Candle(
                    provider=provider,
                    symbol=symbol,
                    timeframe="1m",
                    open_time=_utc(open_ms),
                    close_time=_utc(open_ms + step_ms - 1),
                    open=float(row[columns["O"]]),
                    high=float(row[columns["H"]]),
                    low=float(row[columns["L"]]),
                    close=float(row[columns["C"]]),
                    volume=float(row[columns["V"]]),
                )
            )

    candles = _resample_candles(candles, timeframe)

    quotes: list[BBO] = []
    with bbo_path.open(newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        columns = {name: index for index, name in enumerate(header)}
        required = ("b", "a", "T")
        missing = [name for name in required if name not in columns]
        if missing:
            raise DomainError(ERR_VALIDATION, f"bbo.csv missing columns {missing}")
        for sequence, row in enumerate(reader, start=1):
            if not row:
                continue
            quotes.append(
                BBO(
                    provider=provider,
                    symbol=symbol,
                    event_time=_utc(int(row[columns["T"]])),
                    bid=float(row[columns["b"]]),
                    bid_qty=float(row[columns["B"]]) if "B" in columns else 0.0,
                    ask=float(row[columns["a"]]),
                    ask_qty=float(row[columns["A"]]) if "A" in columns else 0.0,
                    update_id=None,
                    source_sequence=sequence,
                )
            )

    if not candles:
        raise DomainError(ERR_VALIDATION, f"fixture dataset {directory} has no candles")
    previous: datetime | None = None
    for quote in quotes:
        if quote.bid <= 0 or quote.ask <= 0 or quote.bid > quote.ask:
            raise DomainError(
                ERR_INVALID_BBO_REPLAY,
                f"invalid BBO row at {quote.event_time.isoformat()} in {bbo_path}",
            )
        if previous is not None and quote.event_time < previous:
            raise DomainError(ERR_INVALID_BBO_REPLAY, f"BBO rows out of order in {bbo_path}")
        previous = quote.event_time

    info = DatasetInfo(
        dataset_version=f"{provider}:{symbol}:{timeframe}:{candles[0].open_time.date().isoformat()}",
        provider=provider,
        symbol=symbol,
        timeframe=timeframe,
        range_from=candles[0].open_time,
        range_to=candles[-1].close_time,
        candle_count=len(candles),
        content_hash=sha256_file(ohlcv_path),
        bbo_content_hash=sha256_file(bbo_path),
    )
    return candles, quotes, info
