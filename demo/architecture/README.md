# Architecture demo kit

This directory is intentionally outside app/ and server/ runtime packages.
The files here are extracted copies of the production implementations. They
are not imported by the running application until the recording copies them
back into the runtime packages and registers them.

## 1. Add a MACD strategy

The source file is the production MACD implementation. Keep it outside the
runtime while preparing the recording, then copy it back as a new plugin.
Because this checkout already has macd@v1, do this on a temporary branch or
worktree when demonstrating the initial absent-plugin state.

### Prepare the move-out state

In a disposable branch/worktree, extract the production file to this demo kit
and remove its import and registration from catalog.py. The running checkout
is deliberately not modified by this documentation step:

~~~bash
cp app/domain/strategy/plugins/macd.py demo/architecture/python/macd.py
# remove the MACD import and registry.register(MACDStrategy) in the temporary branch
rm app/domain/strategy/plugins/macd.py
~~~

The empty state demonstrates that the core engine does not contain a MACD
branch. The demo file is now the only implementation being shown.

### Copy the plugin

From the repository root:

~~~bash
cp demo/architecture/python/macd.py app/domain/strategy/plugins/macd.py
~~~

The copied file contains a normal Strategy implementation. It uses only
AnalysisContext, Definition, and Signal; it does not import a controller,
backtester, evaluator, database, or frontend module.

### Add the registration

Open app/domain/strategy/plugins/catalog.py and apply the snippet from
[register_macd.snippet.py](python/register_macd.snippet.py):

~~~python
from .macd import MACDStrategy

# inside register_all(registry)
registry.register(MACDStrategy)
~~~

Do not add a second registration with the same (strategy_id, version) pair.

### Verify the extension seam

~~~bash
.venv/bin/python - <<'PY'
from app.domain.strategy.plugins.catalog import default_registry

registry = default_registry()
definition = registry.resolve("macd", "v1").definition()
print(definition.strategy_id, definition.version, definition.display_name)
assert definition.strategy_id == "macd"
assert definition.version == "v1"
PY

.venv/bin/python -m pytest tests/test_indicators_plugins.py -q
~~~

For the video, show the new file and the single catalog registration, then
show that the existing backtest/evaluator tests still pass. The key statement
is: “The downstream components receive the same strategy contract; no core
branch was added.”

## 2. Add an OKX market-data provider

[okx_fixture.go](go/okx_fixture.go) is a deterministic OKX
fixture adapter implementing the canonical RealtimeMarketProvider port. It is
named okx_fixture to distinguish it from the live okx_swap integration.
Copy it only when recording the provider-extension part:

### Prepare the move-out state

In the same disposable branch/worktree, extract the provider and remove its
fixture registration/test setup from the temporary runtime copy. Keep the
current checkout intact because it is used by the live demo stack:

~~~bash
cp server/internal/infrastructure/market/okx_fixture.go demo/architecture/go/okx_fixture.go
rm server/internal/infrastructure/market/okx_fixture.go
~~~

The provider is intentionally a deterministic fixture. It proves the OKX
adapter contract without depending on network timing.

~~~bash
cp demo/architecture/go/okx_fixture.go server/internal/infrastructure/market/okx_fixture.go
~~~

Then add the registration line from
[register_okx.snippet.txt](go/register_okx.snippet.txt) beside the
existing Binance/OKX providers in server/cmd/api/main.go:

~~~go
marketadapter.NewOKXFixtureProvider(okxCandles),
~~~

Use a small local candle fixture for okxCandles. If the provider should be
visible through the market API, also add okx_fixture to the demo provider
keys and restart the API. No change belongs in MarketService, the Python
strategy runtime, or the frontend provider schema.

Verify:

~~~bash
gofmt -w server/internal/infrastructure/market/okx_fixture.go
go -C server test ./internal/application ./internal/infrastructure/market
~~~

The current repository already has this implementation and its contract test.
For the video, first show the file outside the runtime, then copy it back and
register it. Do not copy over an active file twice.

## 3. Recording order

1. Use a temporary branch/worktree; keep the running checkout intact.
2. Start with this directory and explain that the extracted files are inert.
3. Copy one implementation into its runtime package.
4. Add only the import/registration line.
5. Run the focused test and show the unchanged downstream tests.
6. Open the UI or API only after the test passes.
7. Remove only the temporary copy/registration, or discard the temporary
   branch/worktree after recording.

Useful evidence commands:

~~~bash
git diff --stat
git diff -- app/domain/strategy/plugins/macd.py app/domain/strategy/plugins/catalog.py
git diff -- server/internal/infrastructure/market/okx_fixture.go server/cmd/api/main.go
~~~

## 4. Other scenario evidence

- Genetic/domain-guided search: /discovery, select the generator, run, and
  show generated/tested/failed plus the final score.
- WebSocket recovery: / pause/resume realtime; show the market status API
  reconnect_count, stale, and persisted checkpoint/backfill tests.
- News isolation: stop only news-worker; refresh /news and / to show
  news collection is degraded while stored news and market data remain usable.
- Leaderboard trace: click Provenance top 1; show strategy version,
  parameters, dataset/provider/timeframe, evaluator, trades, backtest run, and
  experiment IDs in Inspector.
- Scale: run scripts/backtest-throughput-benchmark.py against an isolated
  database with 100 jobs at 1 and 4 workers; show both completion counts and
  elapsed times.

## Cleanup

The demo directory can remain in the repository. It has no runtime effect.
Only the copied runtime files and their registration lines need to be removed
after a recording if the temporary branch/worktree is not discarded.
