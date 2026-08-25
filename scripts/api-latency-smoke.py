"""Measure bounded public API latency using only the Python standard library."""

from __future__ import annotations

import argparse
import json
import math
import time
import urllib.error
import urllib.request


def percentile(values: list[float], quantile: float) -> float:
    index = max(0, math.ceil(len(values) * quantile) - 1)
    return sorted(values)[index]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:18081/ready")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--max-p95-ms", type=float, default=1000.0)
    args = parser.parse_args()
    if args.requests < 1:
        parser.error("--requests must be positive")

    durations: list[float] = []
    errors: list[str] = []
    for _ in range(args.requests):
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(args.url, timeout=args.timeout) as response:
                response.read()
                if response.status >= 400:
                    errors.append(f"http_{response.status}")
        except (OSError, urllib.error.URLError) as exc:
            errors.append(type(exc).__name__)
        durations.append((time.perf_counter() - started) * 1000)

    report = {
        "url": args.url,
        "requests": args.requests,
        "errors": len(errors),
        "min_ms": round(min(durations), 3),
        "p50_ms": round(percentile(durations, 0.50), 3),
        "p95_ms": round(percentile(durations, 0.95), 3),
        "p99_ms": round(percentile(durations, 0.99), 3),
        "max_ms": round(max(durations), 3),
        "max_p95_ms": args.max_p95_ms,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not errors and report["p95_ms"] <= args.max_p95_ms else 1


if __name__ == "__main__":
    raise SystemExit(main())
