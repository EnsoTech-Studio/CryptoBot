"""Run an isolated queue -> worker -> engine -> PostgreSQL throughput benchmark.

This harness deliberately requires an explicit confirmation flag because it
creates immutable experiments and result facts. Point it only at a disposable
database created from this repository's migrations; it does not delete rows
afterward, so the report remains independently inspectable.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb


ROOT = Path(__file__).resolve().parents[1]
CONFIRMATION = "I_UNDERSTAND_THIS_WRITES_TO_AN_ISOLATED_DATABASE"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--jobs", type=int, required=True)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--candles", type=int, default=60)
    parser.add_argument("--timeout-seconds", type=float, default=900.0)
    parser.add_argument("--confirm-isolated", default="")
    args = parser.parse_args()
    if args.confirm_isolated != CONFIRMATION:
        parser.error(
            "pass --confirm-isolated " + CONFIRMATION + " for a disposable database"
        )
    if args.jobs < 1 or args.workers < 1 or args.candles < 50 or args.timeout_seconds <= 0:
        parser.error("--jobs/--workers must be positive, --candles >= 50, and timeout > 0")
    return args


def seed_workload(
    connection: psycopg.Connection[object], marker: str, jobs: int, workers: int, candles: int
) -> None:
    provider = f"bench{marker[-12:]}"
    dataset_version = f"throughput:{marker}"
    started_at = datetime(2026, 1, 1, tzinfo=UTC)
    end_at = started_at + timedelta(minutes=candles) - timedelta(milliseconds=1)
    candidate = {"strategy_id": "ma_cross", "version": "v1", "parameters": {"fast": 2, "slow": 3}}

    with connection.cursor() as cur:
        cur.execute(
            "INSERT INTO strategy_definitions(strategy_id,display_name,family) "
            "VALUES ('ma_cross','Moving Average Cross','trend') ON CONFLICT DO NOTHING"
        )
        cur.execute(
            "INSERT INTO strategy_versions(strategy_id,version,parameters_schema,default_params,"
            "input_requirements,overlay_types,code_fingerprint) "
            "VALUES ('ma_cross','v1','{}','{}','[]','[]',%s) ON CONFLICT DO NOTHING",
            ("m" * 64,),
        )
        cur.execute("SELECT id FROM strategy_versions WHERE strategy_id='ma_cross' AND version='v1'")
        strategy_version_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO market_pairs(symbol,base,quote,provider) VALUES ('BTCUSDT','BTC','USDT',%s)",
            (provider,),
        )
        cur.execute(
            "INSERT INTO market_datasets(dataset_version,provider,symbol,timeframe,range_from,range_to,"
            "revision_no,candle_count,content_hash,bbo_content_hash) "
            "VALUES (%s,%s,'BTCUSDT','1m',%s,%s,1,%s,%s,%s) RETURNING id",
            (dataset_version, provider, started_at, end_at, candles, "c" * 64, "q" * 64),
        )
        dataset_id = cur.fetchone()[0]
        candle_rows = []
        quote_rows = []
        for index in range(candles):
            open_time = started_at + timedelta(minutes=index)
            close_time = open_time + timedelta(minutes=1) - timedelta(milliseconds=1)
            close = 100.0 + (2.0 if index % 2 else -1.0) + index * 0.01
            candle_rows.append((dataset_id, open_time, close_time, close - 0.2, close + 0.3, close - 0.4, close, 10.0, 1))
            quote_rows.extend(
                [
                    (dataset_id, open_time + timedelta(seconds=10), index * 2 + 1, close - 0.06, 100.0, close + 0.06, 100.0, index * 2 + 1),
                    (dataset_id, open_time + timedelta(seconds=50), index * 2 + 2, close - 0.04, 100.0, close + 0.04, 100.0, index * 2 + 2),
                ]
            )
        cur.executemany(
            "INSERT INTO market_dataset_candles(market_dataset_id,open_time,close_time,open,high,low,close,volume,trade_count) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            candle_rows,
        )
        cur.executemany(
            "INSERT INTO market_dataset_bbo(market_dataset_id,event_time,source_sequence,bid,bid_qty,ask,ask_qty,update_id) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            quote_rows,
        )
        owner_count = max(workers, 1)
        cur.execute(
            "INSERT INTO users(email,password_hash,display_name,role) "
            "SELECT format('throughput-%%s-%%s@invalid.local',%s::text,serial),'benchmark','Throughput Benchmark','RESEARCHER' "
            "FROM generate_series(1,%s) serial RETURNING id",
            (marker, owner_count),
        )
        owner_ids = [row[0] for row in cur.fetchall()]
        cur.execute(
            "WITH seeded AS ("
            " INSERT INTO experiments(owner_id,strategy_version_id,candidate_definition,candidate_hash,market_dataset_id,"
            " bbo_dataset_hash,evaluator_version,replay_range_from,replay_range_to,correlation_id)"
            " SELECT (%s::uuid[])[1 + ((serial - 1) %% %s)],%s,%s,%s,%s,%s,'v1',%s,%s,%s"
            " FROM generate_series(1,%s) serial RETURNING id"
            ") INSERT INTO backtest_jobs(experiment_id,status,priority)"
            " SELECT id,'queued',100 FROM seeded",
            (owner_ids, owner_count, strategy_version_id, Jsonb(candidate), "h" * 64, dataset_id, "q" * 64, started_at, end_at, marker, jobs),
        )
    connection.commit()


def start_workers(database_url: str, count: int) -> list[subprocess.Popen[bytes]]:
    processes: list[subprocess.Popen[bytes]] = []
    for index in range(count):
        environment = {
            **os.environ,
            "DATABASE_URL": database_url,
            "WORKER_ID": f"throughput-worker-{index + 1}",
            "POLL_INTERVAL_S": "0.01",
            "WORKER_LEASE_SECONDS": "120",
            "WORKER_HEARTBEAT_SECONDS": "30",
            "EVENT_CONSUMERS": "",
        }
        processes.append(
            subprocess.Popen(
                [sys.executable, "-m", "app.worker", "queue"],
                cwd=ROOT,
                env=environment,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        )
    return processes


def stop_workers(processes: list[subprocess.Popen[bytes]]) -> None:
    for process in processes:
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
    for process in processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def status(connection: psycopg.Connection[object], marker: str) -> dict[str, int]:
    with connection.cursor() as cur:
        cur.execute(
            "SELECT status,count(*) FROM backtest_jobs j JOIN experiments e ON e.id=j.experiment_id "
            "WHERE e.correlation_id=%s GROUP BY status",
            (marker,),
        )
        return {row[0]: row[1] for row in cur.fetchall()}


def report(connection: psycopg.Connection[object], marker: str, jobs: int, workers: int, elapsed_s: float) -> dict[str, object]:
    with connection.cursor() as cur:
        cur.execute(
            "SELECT percentile_cont(0.50) WITHIN GROUP (ORDER BY extract(epoch FROM completed_at-enqueued_at)*1000),"
            " percentile_cont(0.95) WITHIN GROUP (ORDER BY extract(epoch FROM completed_at-enqueued_at)*1000) "
            "FROM backtest_jobs j JOIN experiments e ON e.id=j.experiment_id "
            "WHERE e.correlation_id=%s AND j.status='completed'",
            (marker,),
        )
        p50_ms, p95_ms = cur.fetchone()
        cur.execute(
            "SELECT count(*) FROM run_signals s JOIN backtest_runs r ON r.id=s.backtest_run_id "
            "JOIN experiments e ON e.id=r.experiment_id WHERE e.correlation_id=%s",
            (marker,),
        )
        signals = cur.fetchone()[0]
        cur.execute(
            "SELECT count(*) FROM equity_points p JOIN backtest_runs r ON r.id=p.backtest_run_id "
            "JOIN experiments e ON e.id=r.experiment_id WHERE e.correlation_id=%s",
            (marker,),
        )
        equity_points = cur.fetchone()[0]
    return {
        "scope": "isolated PostgreSQL queue -> worker processes -> deterministic engine -> persisted results; excludes Go/API and event evaluation",
        "marker": marker,
        "jobs": jobs,
        "workers": workers,
        "elapsed_seconds": round(elapsed_s, 3),
        "completed_jobs_per_second": round(jobs / elapsed_s, 3),
        "job_latency_p50_ms": None if p50_ms is None else round(float(p50_ms), 3),
        "job_latency_p95_ms": None if p95_ms is None else round(float(p95_ms), 3),
        "persisted_signals": signals,
        "persisted_equity_points": equity_points,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    }


def main() -> int:
    args = parse_args()
    marker = f"bench-{uuid4().hex}"
    connection = psycopg.connect(args.database_url, autocommit=False)
    processes: list[subprocess.Popen[bytes]] = []
    try:
        seed_workload(connection, marker, args.jobs, args.workers, args.candles)
        started = time.perf_counter()
        processes = start_workers(args.database_url, args.workers)
        deadline = started + args.timeout_seconds
        counts: dict[str, int] = {}
        while time.perf_counter() < deadline:
            counts = status(connection, marker)
            if counts.get("completed", 0) == args.jobs:
                elapsed = time.perf_counter() - started
                print(json.dumps(report(connection, marker, args.jobs, args.workers, elapsed), indent=2, sort_keys=True))
                return 0
            if counts.get("failed", 0) or counts.get("cancelled", 0):
                break
            time.sleep(0.1)
        print(json.dumps({"marker": marker, "counts": counts, "error": "benchmark_timeout_or_failed"}, indent=2, sort_keys=True))
        return 1
    finally:
        stop_workers(processes)
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
