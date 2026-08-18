"""Backtest worker entrypoint (stub).

Mirrors `server/cmd/worker/main.go`. Consumes `backtest_jobs` (via
`FOR UPDATE SKIP LOCKED` + lease), runs `BacktestEngine`, publishes
`BacktestCompleted`. Deferred — raises `NotImplementedError`.
"""

from __future__ import annotations


def main() -> None:
    raise NotImplementedError


if __name__ == "__main__":
    main()
