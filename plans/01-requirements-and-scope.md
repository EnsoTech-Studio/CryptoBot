# 01 -- Requirements and scope

> ⚠️ **ARCHIVED — superseded by [`blueprint/`](../blueprint/README.md).** Bản nháp đầu, chưa xác thực. Không sửa, không dùng làm nguồn. Xem [`plans/README.md`](README.md) để biết quyết định nào đã thay đổi.


## Product statement

Crypto Strategy Lab lets a user inspect Binance market data, combine independent analysis strategies, simulate them on historical candles, compare the results, and improve the search without rewriting the system. The project is assessed primarily as **software architecture**, not as proof that a trading rule earns money. [PDF pp. 2, 43, 53--54]

## Mandatory MVP

| Area | Minimum deliverable | Architectural implication |
|---|---|---|
| Market | Binance historical candles and realtime updates | Hide Binance behind a normalized market-data adapter. |
| Dashboard | Up to four independent timeframes; each chart renders candlesticks, volume, enabled MA/Bollinger/Support-Resistance overlays, and backtest Buy/Sell, entry/exit, stop-loss, and take-profit markers when available | Each panel owns its subscription and query state; one panel change must not reload the others. |
| Strategies | At least four individual strategies: MA, RSI, Bollinger Bands, Support/Resistance | Strategies use one contract and have no direct UI, provider, or database dependency. |
| Combination | Generate composite strategies | Combination policy is a replaceable component, not `if/else` combinations. |
| Backtest | Simulate trades on historical data | Backtesting receives an immutable experiment snapshot and returns a reproducible result. |
| Evaluation | Return, win rate, maximum drawdown, number of trades | Evaluation is separate from strategy execution. |
| Search | At least Random Search | Search creates candidates; it must not know how a backtest is executed. |
| Ranking | Top-K leaderboard | Rank snapshots by an explicit, versioned scoring policy. |
| Visualization | Signals, entry, and exit shown on a chart | Result overlays are derived from recorded signals/trades. |
| News | Collect -> store -> sentiment analysis pipeline | News providers and the sentiment model have separate adapters. |
| Documentation | README, architecture document, ADRs, demo | Keep this `plans/` set as the report backbone. |

Sources: [PDF pp. 40--41, 49--52].

## Success criteria

- A user can open `ETHUSDT` in four timeframes, each independently changeable.
- A user can choose or register MA, RSI, Bollinger, and Support/Resistance strategies.
- The system can generate at least one composite candidate, backtest it, calculate the four required metrics, and rank it in Top-K.
- Strategy selection, search progress, leaderboard updates, and chart overlays are visible without a full-page reload.
- News ingestion, storage, and sentiment classification work as a pipeline; market charts keep working if that pipeline fails.
- An experiment records strategy version, parameter values, candle dataset/timeframe, execution assumptions, and evaluator version so the result can be reproduced.

## Deliberate non-goals for the MVP

- No real-money trading, exchange API-key storage, order execution, custody, or investment advice.
- No need for genetic search, multiple exchanges, multiple assets, Kafka, Redis, CQRS, or event sourcing unless the team can show the architectural problem each one solves.
- No requirement to fully implement SMC or Wyckoff; the architecture must merely admit them as plugins.

This follows the brief: complex technology earns no credit unless it solves an identified architecture problem. [PDF pp. 12, 19, 42--43]

## Architectural drivers

| Driver | Scenario to prove | Design response |
|---|---|---|
| Modifiability | Add `MACDStrategy` | Implement the strategy contract; add registry metadata; no change to engine, backtester, UI, or database schema. |
| Replaceability | Change Random Search to Domain-Guided Search | Replace `CandidateGenerator`; downstream only accepts candidate specifications. |
| Provider independence | Add OKX after Binance | Add an adapter implementing the market-data port; normalized API and frontend stay unchanged. |
| Realtime | Binance sends new candle data | Ingest once, publish normalized updates to subscribed dashboard panels through backend WebSocket. |
| Scalability | 100 -> 100,000 backtests | Move accepted candidate jobs from in-process execution to a queue and horizontally scaled workers without changing the experiment contract. |
| Reliability | Binance or News provider disconnects | Reconnect/backfill market candles; isolate failed news jobs; degrade only the affected feature. |
| Reproducibility | Inspect a leaderboard result | Persist immutable strategy, dataset, assumption, evaluator, and result versions. |
| Observability | Search seems stalled | Show run state, candidate counts, latency, error count, current candidate, and Top-1. |

Sources: [PDF pp. 32--37, 39, 43--47].

## Constraints from the starting repository

The existing scaffold already has a browser -> Go API -> Python FastAPI request path and Docker Compose health checks. It currently exposes only a text-prediction stub. The target design retains these three deployables, converts the Python service into the domain/application service, and adds persistence plus asynchronous work only where the requirements need them.

## Definition of done

The project is ready for its final demo when the scenario in [06](06-decisions-and-roadmap.md#demo-script) can be performed from a fresh Docker Compose start and every result shown on screen links to a recorded experiment snapshot.
