# Crypto Strategy Lab

Full-stack implementation for the Crypto Strategy Lab blueprint. The app follows the unified product boundary in `blueprint/`: the browser renders normalized DTOs only and talks exclusively to the Go API; Go owns realtime market data (candle/BBO normalization, WSS reconnect/backfill), the edge/API, auth/RBAC and quota; the Python platform (`research`) owns the strategy runtime, backtest, search, ranking, and news extraction/tagging + AI/sentiment orchestration; `ai` is the sentiment inference adapter. See the transitional note under Architecture for how today's code maps to that target.

## Run

Requirements:

- Docker Desktop with Docker Compose v2
- Optional for local web checks: Node.js 22+

Start the full stack:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Services:

| Service    | URL / role                                                    |
| ---------- | ------------------------------------------------------------- |
| `web`      | <http://localhost:3000>                                       |
| `api`      | <http://localhost:8080/health>, <http://localhost:8080/ready> |
| `worker`   | no public port; polls `backtest_jobs`                         |
| `ai`       | <http://localhost:8000/health> in dev compose                 |
| `research` | <http://localhost:8001/health> in dev compose (Python platform skeleton) |
| `postgres` | port `5432` in dev compose                                    |

Demo login:

| Role       | Email                    | Password        |
| ---------- | ------------------------ | --------------- |
| RESEARCHER | `researcher@example.com` | `Research#2026` |
| OPERATOR   | `operator@example.com`   | `Operator#2026` |
| ADMIN      | `admin@example.com`      | `Admin#2026`    |

## Demo Flow

1. Open <http://localhost:3000>.
2. Login with the RESEARCHER account.
3. Watch the four independent `ETHUSDT` panels fed by Binance USD-M Futures public klines: `5m`, `15m`, `1h`, `4h`.
4. Change one panel timeframe or strategy; only that panel refetches/resubscribes.
5. Click **Run backtest**. The API writes an immutable experiment snapshot and a PostgreSQL job, then returns `202`.
6. The worker claims the job, runs Go backtest/evaluation, and writes trades, equity, metrics and leaderboard entry.
7. Inspect the result chart, metrics, trade table and equity curve.
8. Click **Start search** to enqueue bounded composite candidates.
9. Open Leaderboard and click **Trace** to view provenance: candidate hash, dataset hash, execution assumptions and score policy.
10. Use News and sentiment to view CoinDesk RSS items, model coverage and the authenticated AI predict endpoint.

## Architecture

Unified target topology (blueprint `design.md` §1.2):

```text
Browser (Next.js)
  -> Go API (edge: auth/RBAC, quota, REST, WebSocket, realtime market normalize)
      -> PostgreSQL (source of truth, queue, read views, provenance)
      -> research (Python platform: strategy runtime, backtest, search, ranking,
                   news extraction/tagging, sentiment/AI orchestration) :8001
           -> ai (Python inference adapter) :8000
      -> worker (same research image, async backtest, 1 -> N replicas)
```

**Transitional note (as-built vs target).** Today the Go `server/` implements the
strategy domain (candles, strategies, backtest, evaluation, ranking, news
collection) and the Go worker consumes `backtest_jobs`; the `research` service
(`app/` at repo root, port `8001`) is the canonical Python target platform and is
currently an all-stubs skeleton; `ai` serves sentiment inference. The browser
only ever talks to the Go API in both the current state and the target — `ai`
and `research` are internal.

Implemented blueprint boundaries:

- Frontend does not calculate indicators, PnL, drawdown, score, sentiment aggregation or strategy signals.
- `POST /api/v1/experiments` is always async and returns `run_id`.
- Worker communicates through `backtest_jobs` in PostgreSQL.
- Leaderboard entries reference immutable evaluations and expose provenance.
- Market candles are collected server-side from Binance USD-M Futures REST. If Binance is unavailable and no real cache exists, market data is unavailable rather than synthesized.
- News collection uses server-side allowlisted RSS sources. CoinDesk RSS is seeded as the approved source.
- News collection and sentiment are separate; unavailable sentiment is represented as missing/null data, not fake neutral data.
- The app is simulation-only: no exchange API keys, no trading routes, no live order placement.

## External Data and Services

The stack imports only these external runtime inputs:

- Binance USD-M Futures public klines: `https://fapi.binance.com/fapi/v1/klines`
- CoinDesk RSS through the allowlisted `news_sources` table: `https://www.coindesk.com/arc/outboundfeeds/rss/`
- Internal Python AI service in Docker Compose: `http://ai:8000/predict`

No exchange keys are required. The AI service analyzes real collected news text, but it is local to the compose stack and does not call an external LLM/API.

## API Highlights

Public/read:

- `GET /api/v1/markets/pairs`
- `GET /api/v1/markets/candles`
- `GET /api/v1/markets/chart-overlays`
- `GET /api/v1/markets/stream` WebSocket
- `GET /api/v1/strategies`
- `GET /api/v1/leaderboard`
- `GET /api/v1/leaderboard/{entryId}/provenance`
- `GET /api/v1/news`
- `GET /api/v1/news/aggregate`

Authenticated commands:

- `POST /api/v1/auth/login`
- `POST /api/v1/experiments`
- `POST /api/v1/search-runs`
- `POST /api/v1/search-runs/{id}/actions`
- `POST /api/v1/ai/predict`

Operational:

- `GET /health`
- `GET /ready`
- `GET /metrics` requires OPERATOR or ADMIN

## Development Checks

Frontend:

```powershell
cd web
npm install
npm run lint
npx tsc --noEmit
```

Python (AI service):

```powershell
cd ai
pip install -r requirements-dev.txt
python -m pytest
```

Python (research platform, canonical target skeleton):

```powershell
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest
uvicorn app.main:app --reload --port 8001
```

Full stack verification should be done with:

```powershell
docker compose up --build
```

Production hardening override:

```powershell
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build
```

The production override removes public host ports for `ai` and `postgres`.

## Documentation

Read order:

1. [`requirements.html`](requirements.html)
2. [`blueprint/README.md`](blueprint/README.md)
3. [`blueprint/design.md`](blueprint/design.md)
4. [`blueprint/specs/`](blueprint/specs/)

The implementation intentionally keeps the blueprint's core rule: the browser only talks to the Go edge; the Python platform (`research`) is the canonical strategy/backtest/news domain target; `ai` is the sentiment model adapter; and Next.js is presentation.
