#!/usr/bin/env python3
"""Import a checked-in BBO fixture as an immutable replay dataset.

The browser only runs experiments against a frozen PostgreSQL dataset.  This
tool bridges the checked-in ``data/formatted/<symbol>/<date>`` verification
fixture to that same contract, without adding a development-only API route.
It is idempotent: an existing version is validated and reused; mismatched
immutable facts fail loudly instead of being overwritten.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
from typing import Iterable

import psycopg


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.infrastructure.dataset import DatasetInfo, load_fixture_dataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.environ.get("MIGRATION_DATABASE_URL"))
    parser.add_argument("--dataset", type=Path, default=ROOT / "data/formatted/sol/2026-03-04")
    parser.add_argument("--provider", default="binance_usdm")
    parser.add_argument("--symbol", default="SOLUSDT")
    parser.add_argument(
        "--timeframe",
        action="append",
        required=True,
        choices=("1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d"),
        help="Replay timeframe to expose; repeat for multiple immutable snapshots.",
    )
    args = parser.parse_args()
    if not args.database_url:
        parser.error("pass --database-url or set MIGRATION_DATABASE_URL")
    return args


def fixture_version(info: DatasetInfo) -> str:
    return f"fixture:{info.dataset_version}:v1"


def import_fixture(
    connection: psycopg.Connection[object], *, directory: Path, provider: str, symbol: str, timeframe: str,
) -> tuple[str, int, int]:
    candles, quotes, info = load_fixture_dataset(directory, provider=provider, symbol=symbol, timeframe=timeframe)
    version = fixture_version(info)
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO market_pairs(provider, symbol, base, quote)
            VALUES (%s, %s, %s, 'USDT')
            ON CONFLICT(provider, symbol) DO NOTHING
            """,
            (provider, symbol, symbol.removesuffix("USDT")),
        )
        cursor.execute(
            """
            INSERT INTO market_datasets(
                dataset_version, provider, symbol, timeframe, range_from, range_to,
                revision_no, candle_count, content_hash, bbo_content_hash
            ) VALUES (%s, %s, %s, %s, %s, %s, 1, %s, %s, %s)
            ON CONFLICT(dataset_version) DO NOTHING
            RETURNING id
            """,
            (
                version, provider, symbol, timeframe, info.range_from, info.range_to,
                info.candle_count, info.content_hash, info.bbo_content_hash,
            ),
        )
        row = cursor.fetchone()
        if row is None:
            cursor.execute(
                """
                SELECT id, candle_count, content_hash, bbo_content_hash
                FROM market_datasets WHERE dataset_version=%s
                """,
                (version,),
            )
            dataset_id, candle_count, content_hash, bbo_content_hash = cursor.fetchone()
            if (candle_count, content_hash, bbo_content_hash) != (
                info.candle_count, info.content_hash, info.bbo_content_hash,
            ):
                raise RuntimeError(f"immutable dataset version collision: {version}")
            return version, candle_count, quote_count(connection, dataset_id)

        dataset_id = row[0]
        copy_rows(
            cursor,
            """
            COPY market_dataset_candles(
                market_dataset_id, open_time, close_time, open, high, low, close, volume, trade_count
            ) FROM STDIN
            """,
            (
                (dataset_id, candle.open_time, candle.close_time, candle.open, candle.high, candle.low,
                 candle.close, candle.volume, candle.trade_count)
                for candle in candles
            ),
        )
        copy_rows(
            cursor,
            """
            COPY market_dataset_bbo(
                market_dataset_id, event_time, source_sequence, bid, bid_qty, ask, ask_qty, update_id
            ) FROM STDIN
            """,
            (
                (dataset_id, quote.event_time, quote.source_sequence, quote.bid, quote.bid_qty,
                 quote.ask, quote.ask_qty, quote.update_id)
                for quote in quotes
            ),
        )
    return version, len(candles), len(quotes)


def copy_rows(cursor: psycopg.Cursor[object], statement: str, rows: Iterable[tuple[object, ...]]) -> None:
    with cursor.copy(statement) as copy:
        for row in rows:
            copy.write_row(row)


def quote_count(connection: psycopg.Connection[object], dataset_id: object) -> int:
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM market_dataset_bbo WHERE market_dataset_id=%s", (dataset_id,))
        return int(cursor.fetchone()[0])


def main() -> int:
    args = parse_args()
    with psycopg.connect(args.database_url) as connection:
        for timeframe in dict.fromkeys(args.timeframe):
            version, candles, quotes = import_fixture(
                connection,
                directory=args.dataset,
                provider=args.provider,
                symbol=args.symbol.upper(),
                timeframe=timeframe,
            )
            print(f"{version}: {candles} candles, {quotes} BBO rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
