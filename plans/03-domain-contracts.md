# 03 -- Domain contracts

## Ubiquitous language

| Term | Meaning |
|---|---|
| Candle | Normalized OHLCV observation for one symbol, timeframe, and close timestamp. |
| Strategy | Versioned rule that maps an analysis context to a signal. |
| Signal | `BUY`, `SELL`, or `HOLD`, with optional confidence and visual evidence. |
| Composite strategy | A strategy that combines child signals by a declared policy and weights. |
| Candidate | A proposed, immutable strategy specification supplied by a search algorithm. |
| Experiment | Reproducible instruction set for one historical evaluation. |
| Backtest run | Execution of an experiment, with lifecycle state, trades, equity points, and diagnostics. |
| Evaluation | Calculation of metrics and an overall score from a completed run. |
| Leaderboard entry | A ranked immutable evaluation snapshot, not a mutable strategy record. |

## Stable domain interfaces

Language syntax is illustrative; the contracts and dependency direction are the design commitment.

```text
MarketDataProvider
  list_candles(symbol, timeframe, from, to) -> Candle[]
  stream_candles(subscriptions, publish) -> Subscription

Strategy
  definition() -> StrategyDefinition
  analyze(context: AnalysisContext) -> Signal

SignalCombiner
  combine(children: Signal[], policy: CombinationPolicy) -> Signal

CandidateGenerator
  generate(search_space, limit, seed) -> CandidateStrategy[]

BacktestEngine
  run(experiment: ExperimentSnapshot, candles: Candle[]) -> BacktestResult

Evaluator
  evaluate(result: BacktestResult, policy: EvaluationPolicy) -> Evaluation

NewsProvider
  collect(source: ApprovedNewsSource, query, since) -> NewsItem[]

SentimentAnalyzer
  analyze(news: NewsItem) -> Sentiment
```

## News-ingestion security contract

`ApprovedNewsSource` is server configuration, not a browser-supplied URL. Each source has an allowlisted HTTPS origin and bounded query template. Before fetching, and after every redirect/DNS resolution, the adapter rejects non-HTTPS schemes, non-standard ports, loopback/private/link-local/reserved IP ranges, and origins outside the allowlist. It also enforces redirect, response-size, timeout, and content-type limits, then parses content in an isolated worker. A user may select a configured source ID; they cannot make the crawler fetch an arbitrary address.

## Sentiment contract

`Sentiment` is a stable value, not an opaque model response:

```json
{
  "label": "POSITIVE",
  "score": 0.82,
  "model": "sentiment-v1",
  "model_version": "2026-08-01",
  "analyzed_at": "2026-08-09T00:00:00Z"
}
```

`label` is exactly one of `POSITIVE`, `NEUTRAL`, or `NEGATIVE`. `score` is a confidence in the closed interval `[0,1]`; it is not a trading return. The same fields flow from model adapter to persistence, news API, and optional `NewsSentimentStrategy` context. [PDF pp. 29--31]

## Strategy contract and plugin metadata

```json
{
  "strategy_id": "rsi",
  "version": "1.0.0",
  "family": "momentum",
  "parameters_schema": {
    "period": {"type": "integer", "minimum": 2, "default": 14},
    "buy_threshold": {"type": "number", "default": 30},
    "sell_threshold": {"type": "number", "default": 70}
  },
  "input_requirements": ["candles.close"],
  "overlay_types": ["rsi", "buy_signal", "sell_signal"]
}
```

The registry exposes metadata to the API/UI. A strategy implementation only receives normalized data and its validated parameter set. To add MACD, implement the contract and register metadata; no controller switch statement and no storage change are allowed. [PDF pp. 12--13, 44--45]

## Chart overlay contract

Chart overlays are calculated by the Python domain service; the browser only renders them. The initial, bounded query is:

```text
GET /api/v1/markets/chart-overlays?symbol=BTCUSDT&timeframe=5m&strategy=rsi@1.0.0&config_hash=sha256:4d1...
```

It returns a panel-scoped payload with candles, volume, and only the live technical/signal series selected by the user: `moving_average`, `rsi`, `bollinger_bands`, `support_zone`, `resistance_zone`, `buy_signal`, and `sell_signal`. Each item has a timestamp, type, values, and the producing strategy configuration. The result is bounded to the chart's candle window.

`config_hash` is calculated from the strategy ID, version, and canonical validated parameter snapshot; it distinguishes RSI(14,30,70), RSI(21,30,70), and composite configurations. The matching realtime subscription publishes `ChartOverlayUpdated` after `CandleClosed`, carrying the same `(symbol, timeframe, strategy/version, config_hash)` key and the delta for that panel. The API accepts only registered strategy versions and validated parameters, so a frontend never calculates an indicator or infers a trading signal.

Execution markers (`entry`, `exit`, `stop_loss`, and `take_profit`) are not live strategy overlays. They belong only to an immutable experiment's `GET /api/v1/experiments/{id}/overlays` response, because they require recorded fill policy, position state, and execution assumptions.

## Composite strategies

A composite snapshot contains child strategy snapshots and an explicit policy:

```json
{
  "type": "weighted_vote",
  "threshold": 0.3,
  "children": [
    {"strategy_id": "ma_cross", "version": "1.0.0", "parameters": {"fast": 20, "slow": 50}, "weight": 0.2},
    {"strategy_id": "rsi", "version": "1.0.0", "parameters": {"period": 14, "buy_threshold": 30, "sell_threshold": 70}, "weight": 0.3},
    {"strategy_id": "support_resistance", "version": "1.0.0", "parameters": {"window": 80}, "weight": 0.5}
  ]
}
```

`BUY=+1`, `HOLD=0`, and `SELL=-1` is one policy; majority vote is another. Persist the selected policy rather than hard-coding it. [PDF pp. 14--16]

## Experiment snapshot

Every submitted run gets a content-addressable or UUID identity and stores the complete input:

```json
{
  "experiment_id": "exp_01J...",
  "strategy": {"strategy_id": "composite", "version": "1.0.0", "parameters": {}},
  "candidate_definition": "<immutable composite snapshot>",
  "market": {"provider": "binance", "dataset_version": "binance-btcusdt-5m-2026-08-01", "symbol": "BTCUSDT", "timeframe": "5m", "from": "2026-01-01T00:00:00Z", "to": "2026-03-01T00:00:00Z"},
  "execution": {"initial_capital": "10000.00", "fee_bps": 10, "slippage_bps": 5, "fill_policy": "next_candle_open", "position_policy": "long_only"},
  "evaluator_version": "1.0.0",
  "created_at": "2026-08-09T00:00:00Z"
}
```

A strategy version is never overwritten. A changed parameter default or algorithm produces a new version. This is essential for leaderboard provenance. [PDF pp. 38--39, 44]

## Public API resources

The Go API owns the public contract and maps it to internal calls.

| Resource | Purpose |
|---|---|
| `GET /api/v1/markets/candles` | Bounded historical candle query for a chart panel. |
| `GET /api/v1/markets/chart-overlays` | Bounded server-calculated live technical/signal overlays for a selected, canonicalized strategy configuration hash. |
| `GET /api/v1/markets/stream` | WebSocket/SSE subscription to normalized candle and configuration-hashed `ChartOverlayUpdated` deltas; MVP is anonymous, rate-limited, and bounded by subscription count. |
| `GET /api/v1/strategies` | Registry metadata, schemas, and supported overlays. |
| `POST /api/v1/experiments` | Authenticated: validate and create an immutable backtest experiment owned by the principal. |
| `GET /api/v1/experiments/{id}` | Owner-authorized run state, result summary, and safe diagnostic status. |
| `GET /api/v1/experiments/{id}/trades` | Owner-authorized, paginated trade facts. |
| `GET /api/v1/experiments/{id}/overlays` | Owner-authorized bounded chart payload: candles, volume, enabled technical overlays, signals, entries/exits, stop-loss, and take-profit markers. |
| `POST /api/v1/search-runs` | Authenticated: start a bounded candidate generation/backtest/ranking loop under the principal quota. |
| `GET /api/v1/search-runs/{id}` | Owner-authorized search progress, stop condition, failure count, current candidate, and lifecycle state. |
| `POST /api/v1/search-runs/{id}/actions` | Owner-authorized, idempotent `{ "action": "pause" | "resume" | "cancel" }` control command. |
| `GET /api/v1/leaderboard` | Top-K entries with declared sorting/scoring policy. |
| `GET /api/v1/news` | Normalized news and recorded sentiment. |
| `POST /api/v1/ai/predict` | Authenticated and per-principal rate-limited compatibility endpoint; validates nonblank text up to 10,000 characters before model invocation. |

## Validation and error envelope

At the public boundary, validate symbol, supported timeframe, date range/candle count, strategy parameters, combination cardinality, and numerical bounds. Use a stable response envelope for errors:

```json
{
  "error": {
    "code": "unsupported_timeframe",
    "message": "Timeframe must be one of 1m, 5m, 15m, 30m, 1h, 2h, 4h, or 1d.",
    "request_id": "req_01J..."
  }
}
```

Never forward raw upstream bodies, stack traces, provider credentials, or model internals. Long work returns a `run_id`; it is not held behind an arbitrary HTTP timeout.

## Event vocabulary

```text
CandleClosed
ChartOverlayUpdated
StrategyGenerated
BacktestQueued
BacktestStarted
BacktestCompleted
BacktestFailed
StrategyEvaluated
LeaderboardUpdated
NewsCollected
SentimentAnalyzed
```

Each event includes `event_id`, `occurred_at`, `correlation_id`, `schema_version`, and the owning aggregate ID. Event consumers must be idempotent; duplicate `BacktestCompleted` must not create duplicate leaderboard entries. [PDF pp. 35--37]
