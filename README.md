# Crypto Strategy Lab

Crypto Strategy Lab is a simulation-only research stack for realtime crypto market data, reproducible backtests, bounded strategy search, ranking, news, and sentiment analysis.

The browser has one boundary: the Go API. Go owns the public edge, persistent authentication, quotas, and Binance market normalization. Python `research` owns all strategy, backtest, evaluation, search, ranking, news, and sentiment orchestration. The `ai` service performs inference only.

## Start development

Requirements:

- Docker Desktop with Docker Compose v2
- Python 3.12, Go 1.23, and Node.js 22

Development runs only PostgreSQL in Docker. The Go API, research API, AI
adapter, queue worker, event worker, and news worker run as native processes.

First-time setup:

```powershell
Copy-Item .env.example .env
.\scripts\install-run-command.ps1
run setup
cd web
npm ci
cd ..
```

Start development:

```powershell
run up
cd web
npm run dev
```

Linux/macOS native launcher:

```bash
cp .env.example .env
chmod +x backend.sh
./backend.sh setup
./backend.sh up
cd web
pnpm install
pnpm dev
```

Use `./backend.sh status`, `./backend.sh logs api`, or `./backend.sh down`.
The PowerShell launcher is Windows-only; `backend.sh` provides its Linux/macOS
equivalent.

## Quick backend commands

Run these from the repository root. In PowerShell, run
`.\scripts\install-run-command.ps1` once; `run` then works in every new
PowerShell terminal without a `.` or `\` prefix.

| Command | Starts or performs |
| --- | --- |
| `run up` | PostgreSQL and every native backend service |
| `run db` | PostgreSQL only |
| `run api` | Go API and its required research service |
| `run research` / `run ai` | One native HTTP service |
| `run worker` / `run event-worker` / `run news-worker` / `run agent-worker` | One worker process |
| `run workers` | All four worker processes |
| `run stop [service]` | All native services, or one named service/group |
| `run status` | Native-process and PostgreSQL status |
| `run logs api` | Follow the latest 100 API log lines |
| `run down` | Stop native backend and PostgreSQL; keeps volumes |

Examples:

```powershell
run ai
run workers
run stop workers
run status
```

Open `http://localhost:3000`, register a user, then use the workspace. The initial migration includes an offline deterministic `ETHUSDT` 5-minute replay dataset, so experiment and search flows work without waiting for Binance.

| Service | Development endpoint / role |
| --- | --- |
| `web` | `http://localhost:3000` |
| `api` | `http://localhost:8080/health` and `/ready` |
| `research` | Native internal domain API at `http://127.0.0.1:8001` |
| `worker` | Canonical Python backtest executor; no public port |
| `event-worker` | Evaluation/ranking outbox consumer; no public port |
| `news-worker` | Allowlisted collection and sentiment retry loop; no public port |
| `agent-worker` | Durable strategy-authoring orchestration; no public port |
| `ai` | Native optional sentiment inference at `http://127.0.0.1:8000` |
| `postgres` | The only development container; source of truth, queue, facts, and projections |

Check or stop the native backend without stopping PostgreSQL:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/status-native-backend.ps1
powershell -ExecutionPolicy Bypass -File scripts/stop-native-backend.ps1
```

Use `docker compose down` when PostgreSQL should stop too. Native process output
is written under `.runtime/logs/`.

The PostgreSQL-only profile uses the `postgres-native-data` volume. The former
full-stack development volume is not deleted automatically, so legacy local
data remains recoverable instead of being silently migrated against a different
schema ledger.

Full-container production/rehearsal topology:

```powershell
docker compose -f docker-compose.stack.yml -f docker-compose.prod.yml up --build
```

The full-stack file is intentionally separate from local development. The
production override publishes only `web` and `api`; PostgreSQL, research, and
AI remain on the internal Compose network.

## As-built architecture

Plain-language summary: Go is the secure doorway and realtime market gateway; Python is the only research engine.

```text
Browser (Next.js)
  -> Go API
       |-> persistent RS256 auth, refresh rotation, CSRF/CORS, quotas
       |-> Binance USD-M REST/WSS -> closed candles, BBO, checkpoints, WS hub
       |-> PostgreSQL auth/market tables and versioned reads
       -> research (authenticated internal HTTP)
            |-> strategy registry and composite runtime
            |-> deterministic LONG/SHORT BBO backtest and evaluation
            |-> bounded search, ranking, provenance, news, sentiment orchestration
            |-> PostgreSQL queue, immutable facts, transactional outbox
            -> ai (optional inference adapter)

Python worker replicas -> claim PostgreSQL jobs with leases
Event worker           -> consume BacktestCompleted -> evaluate -> rank
News worker            -> collect approved sources -> retry missing sentiment
```

There is no Go lab engine or Go worker fallback. The active Go source contains no canonical strategy, backtest, evaluation, ranking, news extraction, or sentiment math.

## Product flow

1. Register or log in through Go.
2. View independent market panels backed by normalized Binance USD-M data.
3. Run an experiment. Go resolves an immutable dataset and returns `202`; the Python worker executes it asynchronously.
4. Inspect candles, signals, trades, equity, metrics, hashes, and execution provenance after completion.
5. Start a seeded grid, random, or domain-guided search. Candidate and concurrent-run quotas are applied atomically.
6. Inspect leaderboard entries and immutable provenance.
7. Read collected news. Missing AI coverage remains `sentiment: null`; it is never replaced with fake neutral data.

## Runtime guarantees

- Migrations 001 onward are checksum-verified and run by a dedicated startup step: native development uses `app.migrate`, while the full-container topology uses the one-off `migrate` service. API and workers do not execute DDL.
- `api_service` and `research_service` receive separate PostgreSQL roles and grants.
- Experiments and market datasets are immutable; explicit BBO rows are stored only in replay datasets.
- Job claim, facts, terminal state, result hash, and `BacktestCompleted` outbox publication use lease guards and transactional persistence.
- Outbox delivery is at-least-once with `(consumer_id, event_id)` idempotency.
- Result hashes are canonical and reproducible for identical snapshots.
- AI/news are optional dependencies and do not make core readiness fail.
- No exchange credentials or live order routes exist.

## Public API

Market and catalogue:

- `GET /api/v1/markets/pairs`
- `GET /api/v1/markets/candles`
- `GET|POST /api/v1/markets/datasets`
- `GET /api/v1/markets/status`
- `GET /api/v1/markets/chart-overlays`
- `GET /api/v1/markets/stream` (WebSocket)
- `GET /api/v1/strategies`

Research:

- `POST /api/v1/experiments`
- `GET /api/v1/experiments/{id}` and `/candles`, `/trades`, `/equity`, `/overlays`
- `POST /api/v1/search-runs`
- `GET /api/v1/search-runs/{id}`
- `POST /api/v1/search-runs/{id}/actions`
- `GET /api/v1/leaderboard`
- `GET /api/v1/leaderboard/{entryId}/provenance`
- `GET /api/v1/news` and `/api/v1/news/aggregate`
- `POST /api/v1/ai/predict`

Authentication and operations:

- `POST /api/v1/auth/register`, `/login`, `/refresh`, `/logout`
- `GET /api/v1/auth/me`
- `GET /health`, `/ready`
- `GET /metrics` for OPERATOR or ADMIN

Cookie-authenticated commands require a matching `X-CSRF-Token`. Go propagates request, correlation, user, role, and idempotency metadata to research.

## Verification

Run the smoke flow after starting the native backend and web app on the default
ports, or after starting the full-container topology:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/rehearsal-smoke.ps1 `
  -ApiBaseUrl http://127.0.0.1:8080 `
  -WebBaseUrl http://127.0.0.1:3000
```

Research unit and PostgreSQL integration tests:

```powershell
py -3 -m pytest tests --ignore=tests/integration -q
docker compose -f docker-compose.test.yml up -d postgres-test
py -3 -m pytest tests/integration -q
```

Failure/recovery evidence uses the same isolated PostgreSQL test database. It
runs the retry/idempotency baseline plus real worker-process crash rehearsals:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/failure-contract-smoke.ps1 -IncludeIntegration
```

The queue integration suite starts both a backtest worker and an event worker,
kills each after lease acquisition, then verifies a replacement process
reclaims the expired lease and completes exactly once. It is controlled local
recovery evidence, not a production load benchmark.

The 100k-job claim proof runs inside a transaction and rolls back all generated rows:

```powershell
docker compose -f docker-compose.test.yml exec postgres-test `
  psql -U cryptobot -d cryptobot -f /proof/queue-scale-proof.sql
py -3 scripts/api-latency-smoke.py --url http://127.0.0.1:8080/ready --requests 100
```

Other gates:

```powershell
cd server
go test -race ./...

cd ../ai
py -3 -m pytest -q

cd ../web
npm ci
npm run lint
npx tsc --noEmit
npm run build

cd ..
py -3 scripts/check_architecture.py
docker run --rm -v "${PWD}:/repo" -w /repo ghcr.io/astral-sh/ruff:0.6.9 `
  check app tests scripts
```

CI runs these suites, PostgreSQL migrations/integration tests, the ownership scan, and builds the research, API, AI, and web images.

## Documentation

Read in this order:

1. [`requirements.html`](requirements.html)
2. [`blueprint/README.md`](blueprint/README.md)
3. [`blueprint/design.md`](blueprint/design.md)
4. [`blueprint/specs/`](blueprint/specs/)
5. [`docs/architecture/architectural-drivers.md`](docs/architecture/architectural-drivers.md)
6. [`docs/note-update-require-status.md`](docs/note-update-require-status.md)
7. [`blueprint/traceability.md`](blueprint/traceability.md)

The source-of-truth boundary remains: browser -> Go; Go -> research; research -> AI; no live trading.
