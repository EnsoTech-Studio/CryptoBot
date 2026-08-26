# Screen 04 - Backtest Results

| Field | Value |
| --- | --- |
| Reference | `UI-reference/backtest.jpg` |
| Target route | `/backtests` |
| Navigation label | `Backtest` |
| Delivery order | 4 of 5; depends on shared market and strategy selection |
| Primary data | Datasets, experiments, trades, equity, overlays and metrics |
| Plan status | Supported with frontend parameterization and result-type fixes |

## In plain words

Transform the existing asynchronous backtest view into the reference's complete configuration-and-results workspace. Every filter must affect the submitted immutable experiment, and every chart marker, trade row, fee, slippage value and metric must come from the completed run.

<details open class="node">
<summary>1. Outcome and scope</summary>

### User outcome

The user configures a market snapshot and execution assumptions, runs a deterministic backtest, follows its status, and inspects chart events, trades, metrics and assumptions on one page.

### Included

- Rebuild `/backtests` around a top configuration strip, chart, trade ledger and metric footer.
- Parameterize the current hardcoded experiment request.
- Use selected pair, timeframe, date range, initial capital, strategy, fee and slippage values.
- Preserve asynchronous queue/poll behavior and immutable dataset provenance.
- Normalize the full trade response, including fees, slippage, stop loss and take profit.
- Derive entry/exit/risk chart markers from real results where the endpoint does not return them directly.
- Add client-side trade pagination for the loaded result.
- Keep metrics, formula explanation and assumptions consistent with backend semantics.

### Excluded

- Editing an experiment after submission.
- Pretending dates are applied if no matching dataset is created/resolved.
- Showing MA series or support/resistance levels when result overlays do not provide them.
- Export, optimization and live trading actions not present in the reference.

</details>

<details open class="node">
<summary>2. Visual contract extracted from the reference</summary>

### Desktop composition

- Shared sidebar and header.
- One full-width filter strip containing eight compact controls.
- Main results row split roughly `40% / 60%`: chart on the left, trade ledger on the right.
- Bottom row contains six compact KPI cells followed by a wider profit formula and assumptions panel.
- Surfaces have thin borders and `10-12px` radii; metric cells are visually adjacent without large card gaps.

### Typography and data density

- Title: `Backtest & Kết quả giao dịch`, `28-30px`, bold.
- Filter labels: `12px`, semibold; control values: `13-14px`.
- Chart and table headings: `15-16px`, bold.
- Trade table: `11-12px` with tabular numbers and restrained row height.
- KPI values: `24-28px`; supporting text: `11-12px`.
- Profit, win and LONG values are green; losses, drawdown and SHORT values are red.

### Chart details

- White chart background with faint grid and right-side price labels.
- Candles plus volume pane.
- Visible legend for available MA, support and resistance series.
- LONG entry, SHORT entry, exit, stop-loss and take-profit markers use text plus color.
- Provide a fullscreen action only if it is implemented with a real dialog/fullscreen mode.

### Visible copy

- Title: `Backtest & Kết quả giao dịch`.
- Subtitle: `Chọn coin, thời gian test, vốn, strategy và đánh giá hiệu quả`.
- Filters: `Pair / Coin`, `Timeframe`, `From date`, `To date`, `Vốn (USD)`, `Strategy`, `Transaction Cost`, `Slippage`.
- Main sections: `Biểu đồ Backtest`, `Danh sách lệnh giao dịch`.
- Metrics: `Winrate`, `Wins`, `Losses`, `Total Profit`, `Max Drawdown`, `Total Trades`.
- Explanations: `Cách tính Profit`, `Giả định Backtest`.

</details>

<details open class="node">
<summary>3. Existing implementation mapping</summary>

| Current code | Reuse | Required change |
| --- | --- | --- |
| `web/app/backtests/page.tsx` | Route entry | Replace page composition |
| `BacktestPanel` | Run status and command | Convert to compact configuration/run-status behavior |
| `ExecutionTimeline` | Queued/running/completed semantics | Use inline progress/status near the run action or results header |
| `ResultChart` | Result presence and chart invocation | Rebuild chart header, markers and empty/loading states |
| `ChartCanvas` | Candles, series, signals and execution markers | Retheme and support result-specific annotations |
| `Inspector` metrics/trades | Existing detail views | Preserve provenance; avoid duplicating hidden result truth |
| `WorkspaceProvider.runBacktest()` | Queue and polling lifecycle | Accept a typed `BacktestDraft` and retain submitted config |
| `api.createExperiment()` | Dataset resolution and command | Parameterize every supported execution field |
| `api.experimentTrades()` | Trade normalization | Stop discarding fee, slippage, SL and TP fields |

### Current data gaps caused by the web adapter

- `ResearchTrade` omits `fee_paid`, `slippage_cost`, `sl_price` and `tp_price` even though research returns them.
- `Trade` does not preserve those values, so the reference ledger cannot be truthful yet.
- `experimentOverlays()` currently returns empty execution markers and empty series.
- The web request hardcodes `ETHUSDT`, `5m`, capital `100`, fee `10 bps`, slippage `0`, stop loss `2.5%` and take profit `4%`.
- `ensureDataset()` does not accept the visible date range.
- Backend metrics include return, win rate, drawdown and trade count. Wins, losses and total absolute profit can be derived from the real trade list.

</details>

<details open class="node">
<summary>4. Target state and data contracts</summary>

```ts
type BacktestDraft = {
  market: {
    provider: string;
    symbol: string;
    timeframe: string;
  };
  rangeFrom: string;
  rangeTo: string;
  initialEquity: number;
  fixedNotional: number;
  strategyId: string;
  strategyVersion: string;
  children?: Array<{
    strategyId: string;
    version: string;
    weight: number;
    parameters: Record<string, unknown>;
  }>;
  feeBps: number;
  slippageBps: number;
  stopLossPct?: number;
  takeProfitPct?: number;
  intrabarPriority: "stop_loss_first" | "take_profit_first";
};
```

Extend the web trade type with:

```ts
feePaid: number;
slippageCost: number;
stopLossPrice: number | null;
takeProfitPrice: number | null;
```

### Conversion rules

- UI transaction cost percent -> `fee_bps = percent * 100`.
- UI slippage is displayed and submitted in basis points with no hidden conversion.
- Dates are submitted as explicit UTC range boundaries.
- Capital maps to `initial_equity`; `fixed_notional` needs either a visible advanced control or a documented deterministic default.
- Store the submitted draft next to the accepted experiment ID. Results must display the submitted snapshot, not current unsaved controls.
- Disable edits that could imply mutation while the run is queued/running, or clearly offer `Tạo backtest mới` as a separate draft.

### Result derivation

- Wins: closed trades with `pnl > 0`.
- Losses: closed trades with `pnl < 0`; zero-PnL trades are neutral and disclosed.
- Total profit: sum of `pnl` values in result currency.
- Win rate: prefer backend metric; validate it against closed-trade counts in development tests.
- Max drawdown: backend metric in percentage. Only show absolute drawdown if derivable from the equity curve and label the unit.
- Entry/exit markers: derive from trade times and prices.
- Stop/take-profit lines: use trade-level frozen prices only when present.
- Fee and slippage columns: use returned per-trade values, never recalculate for display if persisted values exist.

</details>

<details open class="node">
<summary>5. Target components</summary>

- `BacktestScreen`: draft, submitted snapshot and result composition.
- `BacktestFilters`: pair, timeframe, range, capital, strategy, fee and slippage.
- `BacktestRunButton`: authenticated command with queued/running/completed state.
- `BacktestChartPanel`: chart title, legend, fullscreen action and real markers.
- `TradeLedger`: columns, sorting, page size, pagination and mobile row layout.
- `BacktestMetrics`: six reference KPIs derived from the result bundle.
- `ProfitFormula`: plain-language gross profit -> fees -> slippage -> net profit explanation.
- `BacktestAssumptions`: facts sourced from the submitted execution snapshot.
- `BacktestEmptyState`: no run yet.
- `BacktestFailureState`: failed/cancelled run with error code and retry-as-new action.

### Trade ledger columns

- Sequence number.
- Pair/coin from the experiment snapshot.
- Entry time.
- Side.
- Entry price.
- Stop loss.
- Take profit.
- Exit price.
- Fee paid.
- Slippage cost.
- Profit in result currency.

Use `10`, `25`, and `50` as page-size choices. Client pagination is acceptable because the current endpoint returns the complete bounded result.

</details>

<details open class="node">
<summary>6. Implementation sequence</summary>

1. Add `BacktestDraft`, submitted configuration and field-level validation.
2. Parameterize pair, timeframe and range in dataset lookup/creation. A successful run must point to the matching immutable dataset.
3. Refactor `api.createExperiment` to accept the full draft and preserve idempotency/CSRF.
4. Extend trade response types and normalization for fee, slippage, SL and TP.
5. Build the filter strip and status-aware run action.
6. Rebuild the result layout using existing chart primitives and real result data.
7. Derive execution markers from trades until the experiment overlay endpoint supplies them directly.
8. Render only overlay series actually returned. Do not add decorative MA/SR lines from reference sample values.
9. Implement ledger formatting, pagination and mobile transformation.
10. Implement KPI derivation, profit explanation and assumptions from the submitted execution object.
11. Preserve Inspector access for deeper metrics, equity and provenance.
12. Remove superseded operation-panel CSS after route-level behavior is verified.

</details>

<details open class="node">
<summary>7. Loading, failure and accessibility requirements</summary>

- Initial state shows filters plus a clear empty result area, not sample trades.
- Queue acceptance shows experiment ID and locked draft summary.
- Running state preserves prior results only if labelled as a previous run; otherwise use a stable skeleton.
- Failed/cancelled state includes the real status and retry-as-new behavior.
- No trades is a valid completed outcome and must not be presented as an API failure.
- Table headers use correct scope and numeric columns align consistently.
- Pagination exposes current page and total pages to assistive technology.
- Fullscreen chart traps focus only while open and restores it on close.
- Date controls include format guidance and range validation.
- Error messages identify the affected field, such as missing dataset or invalid range.
- On narrow screens, filters wrap, chart and ledger stack, and ledger rows become labelled facts.

</details>

<details open class="node">
<summary>8. Verification and acceptance</summary>

### Automated checks

- Unit-test percent-to-bps conversion and date-range validation.
- Unit-test experiment payload construction for simple and composite strategies.
- Unit-test trade normalization, KPI derivation and marker derivation.
- Component-test empty, queued, running, completed-with-trades, completed-no-trades, failed and unavailable states.
- Integration-test that changing each visible filter changes the submitted request/snapshot.
- Run web lint/build and existing experiment/backtest/API tests.

### Visual checks

- Compare at the standard four viewport sizes.
- Desktop must preserve the compact filter strip, chart/ledger split and low-profile KPI row.
- Table content must remain readable without shrinking below the typography floor.
- Chart annotations must not overlap axis labels at common result densities.

### Done checklist

- [ ] Every filter affects the immutable experiment or is removed from the UI.
- [ ] The result always names the submitted pair, timeframe, strategy and range.
- [ ] Trade fees, slippage, SL and TP use persisted values.
- [ ] Metrics are real and units are accurate.
- [ ] No sample chart line, trade or KPI remains.
- [ ] Empty, running, failed and completed states are distinct.
- [ ] Existing deterministic backtest and provenance behavior is preserved.
- [ ] `blueprint/` is untouched.

</details>
