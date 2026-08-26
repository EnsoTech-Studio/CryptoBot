# Screen 01 - Realtime Chart

| Field | Value |
| --- | --- |
| Reference | `UI-reference/realtime.jpg` |
| Target route | `/` |
| Navigation label | `Realtime` |
| Delivery order | 1 of 5; owns the shared application shell |
| Primary data | Go API + market WebSocket; labeled deterministic mock fallback |
| Plan status | Implemented and reference-parity audited |

## In plain words

Replace the current dark research terminal with the bright Realtime dashboard shown in the reference. Real candle, overlay, connection, authentication, and WebSocket behavior remains the first choice. If the market backend is unavailable, the complete screen uses deterministic demo data so the intended interface can still be reviewed; that mode must always be labeled `Mock` and must never be presented as live market data.

<details open class="node">
<summary>1. Outcome and scope</summary>

### User outcome

The user can choose a supported market, inspect four timeframes at once, see live connection health, and understand how incoming candle updates affect the charts.

### Included

- Build the shared light application shell used by all five screens.
- Replace the current primary-plus-context chart layout with a balanced 2 by 2 chart grid.
- Parameterize market requests and subscriptions instead of hardcoding `ETHUSDT`.
- Add pair loading through `GET /api/v1/markets/pairs`.
- Preserve historical candle loading, overlays, WebSocket reconnect, stale states, and authentication.
- Add truthful connection details and a bounded recent BBO/tick event list when the stream exposes those values.
- Add a deterministic, screenshot-stable mock market fallback for environments where the Go API or research service is not running.
- Add responsive and accessible states for desktop, tablet, and mobile.

### Excluded

- Trading or order placement. BUY and SELL are strategy signals only.
- Unlabeled fabricated values or silent mixing of mock and live market state.
- A new dark theme. Visual parity for this refactor is light mode.
- Settings functionality; the sidebar item remains disabled until a settings screen is defined.

</details>

<details open class="node">
<summary>2. Visual contract extracted from the reference</summary>

### Page hierarchy

1. Fixed left sidebar, approximately `236px` wide.
2. Page header with title on the left, a centered source chip, and utility icons on the right.
3. Main work area begins immediately below the header: a market column on the left and an information rail on the right.
4. The market column contains its own control card followed by the four-chart grid; the control card does not span above the information rail.
5. Account and plan blocks pinned to the lower sidebar.

### Desktop geometry

- Reference canvas is approximately `1680 x 944`.
- Main content starts after the sidebar with `28-32px` horizontal gutters.
- Information rail is approximately `320-336px` wide.
- Chart region uses two equal columns and two rows with `12-16px` gaps.
- Controls and chart cards use `10-12px` radii, a thin cool-gray border, and a very soft shadow.
- Avoid nested outer cards. Each chart and each information block is one clear surface.

### Typography

- Continue using Geist Sans; it is already installed and matches the clean grotesk character.
- Page title: `28-30px`, weight `700`, tight tracking.
- Card title: `15-16px`, weight `600-700`.
- Control labels: `12-13px`, weight `600`.
- Body and table text: `12-14px`, line height around `1.45`.
- Numeric quotes should use tabular numbers.

### Color and component logic

- App background: near-white `#fbfcff`.
- Surface: `#ffffff`.
- Primary ink: near-black `#111318`; secondary ink: `#667085`.
- Border: `#e7eaf0`; muted fill: `#f6f8fb`.
- Active navigation and primary controls: blue-to-violet gradient, approximately `#146df3 -> #5b3df5`.
- Positive/live: `#16a05d`; negative/sell: `#dc3150`; warning: `#e59a13`.
- MA line: medium blue; volume bars reuse up/down candle colors with reduced opacity.
- Focus rings must be visible blue outlines and not rely on box shadow alone.

### Visible Vietnamese copy

- Title: `Realtime Chart - Đa khung thời gian`.
- Source chip: `Nguồn dữ liệu: Binance API + WebSocket`.
- Controls: `Pair / Coin`, `Khung thời gian`, `Realtime`.
- Chart footer: `Load 1000 nến lịch sử`, `Cập nhật realtime`.
- Rail sections: `Logic cập nhật candle`, `Trạng thái kết nối`, `Recent Ticks`, `Chú thích`.

</details>

<details open class="node">
<summary>3. Existing implementation mapping</summary>

| Current code | Reuse | Required change |
| --- | --- | --- |
| `web/app/WorkspaceShell.tsx` | Provider lifetime and route persistence | Replace terminal shell markup with the shared light shell |
| `web/app/components/LeftRail.tsx` | Active route detection and stream summary | Rebuild navigation, logo, account block, and responsive drawer |
| `web/app/components/InstrumentHeader.tsx` | User session, stream state, notices | Split into shared `PageHeader`, `SourceStatus`, and account menu |
| `web/app/components/ChartWorkspace.tsx` | Four-panel orchestration | Render equal chart cards and the right information rail |
| `web/app/components/ChartPanel.tsx` | Candle quote, strategy, timeframe and chart | Match reference toolbar, signal badge, footer and loading states |
| `web/app/components/charts/ChartCanvas.tsx` | Real candles, volume, overlays and markers | Retheme axes/grid/markers for the white canvas; preserve chart math |
| `web/app/providers/workspace.tsx` | Fetching, reconnect, polling and persistent state | Add selected market, pair catalog, source status and recent stream events |
| `web/lib/api.ts` | Request/error normalization | Accept a market key in market methods; add `marketPairs()` and `marketStatus()` |
| `web/app/tokens.css` | Token entry point | Replace dark-first tokens with the extracted light design system |

### Current capability gaps

| Requirement | Current status | Plan |
| --- | --- | --- |
| Pair selector | Go endpoint exists; web client hardcodes ETHUSDT | Add typed pair API and selected market state |
| Four timeframes | Supported by panel model | Seed `1m`, `5m`, `15m`, `1h`; filter by pair-supported timeframes |
| Historical candles | Endpoint supports up to 1000 | Make the footer action request `limit=1000` for that panel |
| Kline updates | WebSocket path exists | Preserve update-by-open-time semantics and reconnect handling |
| BBO/recent ticks | Domain supports BBO; web client does not consume it | Normalize BBO into the reference table shape; use deterministic mock ticks only in labeled Mock mode |
| BUY/SELL badge | Markers may exist; overlay endpoint can be empty | Use real markers in live mode and reference-matching deterministic markers only in labeled Mock mode |
| Latency | Not currently measured | Compute browser receipt time minus frame `server_time` when available |

</details>

<details open class="node">
<summary>4. Target component and state design</summary>

### Shared shell components introduced here

- `web/app/components/shell/AppSidebar.tsx`
- `web/app/components/shell/PageHeader.tsx`
- `web/app/components/shell/SourceStatus.tsx`
- `web/app/components/shell/UserMenu.tsx`
- `web/app/components/ui/Icon.tsx` using inline SVG paths only; no image files outside `UI-reference/`
- `web/app/components/ui/StatusDot.tsx`
- `web/app/components/ui/SegmentedControl.tsx`
- `web/app/components/ui/Toggle.tsx`

### Realtime components

- `RealtimeScreen`: page composition and responsive grid.
- `MarketControls`: pair selector, timeframe focus controls, global realtime toggle.
- `RealtimeChartGrid`: owns grid semantics but not market data.
- `RealtimeChartCard`: chart header, quote, signal badge, canvas, legend and footer.
- `CandleUpdateGuide`: static explanation, clearly separated from live telemetry.
- `ConnectionStatusPanel`: provider, state, reconnect count, latency and last update.
- `RecentMarketEvents`: bounded list of the latest five real BBO/tick frames.
- `ChartLegend`: candle, MA, volume, BUY and SELL definitions.

### State additions

```ts
type MarketPair = {
  provider: string;
  symbol: string;
  base_asset: string;
  quote_asset: string;
  timeframes: string[];
};

type MarketSelection = {
  provider: string;
  symbol: string;
};

type RecentMarketEvent = {
  id: string;
  occurredAt: string;
  bid?: number;
  ask?: number;
  bidQty?: number;
  askQty?: number;
  sourceSequence?: number;
};
```

- Store `marketPairs`, `marketPairsState`, `selectedMarket`, `realtimeEnabled`, `recentMarketEvents`, `lastFrameAt`, `latencyMs`, and `reconnectCount` in the workspace provider.
- Store `dataMode` as `live` or `mock`; all source, connection, account-fallback, and chart copy must disclose Mock mode.
- Persist only the selected market in local storage. Do not persist live prices or stale connection state.
- Rebuild subscriptions when provider, symbol, timeframe, or strategy changes.
- Cap event history at five visible rows and at most fifty in memory.
- Cancel or ignore stale fetch responses after the market selection changes.

</details>

<details open class="node">
<summary>5. Implementation sequence</summary>

1. Read the applicable Next 16 guides under `web/node_modules/next/dist/docs/` before editing route/layout code, as required by `web/AGENTS.md`.
2. Replace the token palette and define shared spacing, radius, border, status and chart variables.
3. Build the shared shell and sidebar. Preserve `WorkspaceProvider` above route content so sockets and polls survive navigation.
4. Add typed `marketPairs`, `marketStatus`, parameterized `candles`, `overlays`, `datasets`, and `wsURL` inputs in `web/lib/api.ts`.
5. Refactor workspace state away from the hardcoded symbol. Make all panel fetches and subscription keys use `selectedMarket`.
6. Add a request limit parameter so `Load 1000 nến lịch sử` performs a real fetch and exposes loading/error state per card.
7. Extend the WebSocket adapter for the actual Go frame envelope and BBO payload. Keep sequence-gap recovery and exponential reconnect.
8. Rebuild `ChartWorkspace` as the target screen composition and retheme `ChartCanvas` without changing scale calculations.
9. Add the information rail. Static candle logic must be labeled as documentation; live status and recent events must use runtime data.
10. Implement responsive layouts and keyboard navigation.
11. Remove obsolete terminal-only header/stats markup after all consumed behavior has moved into the new shell.
12. Add deterministic BTCUSDT candles, MA(20), BUY/SELL markers, tick rows, and a lightweight mock realtime update loop. Enter this mode only after market services fail, and retry the real catalog on demand.

</details>

<details open class="node">
<summary>6. Interaction, loading and failure behavior</summary>

- Pair change -> set all panels to loading -> close old sockets -> load historical candles -> open new subscriptions.
- Timeframe change on a card -> reload only that card and its subscription.
- Global realtime off -> close sockets cleanly, retain historical candles, and show `Đã tạm dừng`.
- Realtime on -> reconnect all visible panels with their last sequence where safe.
- Pair catalog unavailable -> switch to the labeled deterministic mock catalog, keep the selector usable, and retain a path to retry the real catalog.
- Candle fetch loading -> chart skeleton matching the card height; do not flash an empty-state message.
- Loaded with zero candles -> explicit no-data state naming the pair and timeframe.
- Socket stale -> retain the last chart, show amber/red status, and disclose reconnect attempts.
- No live signal marker -> neutral `No signal`; labeled Mock mode may use deterministic BUY/SELL fixtures to reproduce the reference.
- Source help and notification icons -> implement accessible buttons; disable notification behavior until a real notification source exists.

</details>

<details open class="node">
<summary>7. Responsive and accessibility requirements</summary>

- `>= 1440px`: full sidebar, two chart columns, fixed information rail.
- `1100-1439px`: compact sidebar or narrower labels; information rail moves below the chart grid if cards become narrower than `440px`.
- `768-1099px`: off-canvas sidebar, two chart columns when space permits, stacked information panels.
- `< 768px`: one chart per row, sticky compact page header, horizontally scrollable timeframe control.
- Use `nav`, `main`, `section`, headings in order, and one unique `h1`.
- Pair selector and realtime toggle need explicit labels and keyboard states.
- Use `aria-live="polite"` for connection changes; do not announce every market tick.
- Charts need text summaries containing pair, timeframe, latest close and signal.
- Red/green meaning must also use text and icon shape.
- Minimum interactive target is `40px`; visible focus must meet contrast requirements.

</details>

<details open class="node">
<summary>8. Verification and acceptance</summary>

### Automated checks

- Unit-test market URL construction for provider, symbol, timeframe and limit.
- Unit-test candle upsert behavior for same-open-time update versus new candle append.
- Unit-test BBO/event normalization and bounded history.
- Component-test pair change, realtime pause/resume, loading, stale and no-data states.
- Run `npm run lint` and `npm run build` from `web/`.
- Run existing Go WebSocket and market HTTP tests when frame handling changes require contract confirmation.

### Visual checks

- Compare at `1680 x 944`, `1440 x 900`, `1024 x 768`, and `390 x 844`.
- The first desktop viewport must contain the title, controls and at least the first chart row without clipped controls.
- Sidebar width, active gradient, chart density, right-rail proportions and white-space rhythm must visibly match the reference.
- No dark terminal tokens, lime primary actions, oversized rounded wrappers, or nested card stacks remain on this screen.

### Verification result - 2026-08-25

- [x] Browser comparison completed against `realtime.jpg` at `1680 x 944`.
- [x] Responsive checks completed at `1440 x 900`, `1024 x 768`, and `390 x 844`.
- [x] No horizontal overflow at tablet or mobile widths.
- [x] Mock pause/resume and BTCUSDT/ETHUSDT switching verified in a real browser.
- [x] `npm test`, `npm run lint`, and `npm run build` pass.

### Done checklist

- [x] Live mode displays API/WebSocket values; fallback values are deterministic and visibly labeled `Mock`.
- [x] Pair selection changes every request and subscription consistently.
- [x] Four chart cards render and update independently.
- [x] Connection status distinguishes connecting, live, stale, paused, unavailable, and mock.
- [x] Historical 1000-candle loading is real in live mode and deterministic in Mock mode, with progress/error feedback.
- [x] Desktop and mobile navigation are keyboard accessible.
- [x] Existing auth, reconnect and route-persistent state still work.
- [x] `blueprint/` is untouched.

</details>
