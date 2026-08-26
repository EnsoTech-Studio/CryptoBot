# UI Refactor - Implementation Sequence

| Field | Value |
| --- | --- |
| Branch | `feat/ui-reference-refactor` |
| Inputs | Five images in `UI-reference/` |
| Detailed plans | `01` through `05` in this directory |
| Delivery model | Shared foundation first, then one complete screen at a time |
| Commit model | One foundation commit plus one commit per screen |
| Protected path | `blueprint/` must not be changed |
| Plan status | Ready for execution |

## In plain words

Implement the common visual system once, then finish and verify each screen before moving to the next. This keeps all five screens consistent without turning the refactor into one large change where CSS, state, API and responsive regressions are difficult to isolate.

<details open class="node">
<summary>1. Delivery decision</summary>

### Chosen approach

```text
Shared foundation
  -> Realtime
  -> Discovery
  -> Backtest
  -> News Crawler
  -> Strategy Engine
  -> Cross-screen regression and final polish
```

### Why this order

- The shared foundation locks the visual language before any screen-specific work.
- Realtime establishes market selection, WebSocket state and the application shell used everywhere else.
- Discovery establishes strategy selection, search state and leaderboard composition.
- Backtest reuses both market and strategy state and therefore follows those screens.
- News Crawler is mostly independent and can reuse the completed shell and status patterns.
- Strategy Engine comes last because prompt analysis, URL extraction, validation persistence and save APIs are not currently implemented.

### What is avoided

- Do not rewrite all five pages and global CSS in one unverified batch.
- Do not build each screen with its own duplicated tokens, sidebar or header.
- Do not add sample data to make incomplete API-backed sections resemble the images.
- Do not carry a broken intermediate state across multiple screen commits.

</details>

<details open class="node">
<summary>2. Shared foundation - Commit 1</summary>

### Goal

Create the common shell and component language once. Screen-specific content remains functional while the shell is migrated.

### Work items

1. Read the applicable Next 16 guides under `web/node_modules/next/dist/docs/`, as required by `web/AGENTS.md`.
2. Define the new light design tokens in `web/app/tokens.css`:
   - typography scale and tabular numbers;
   - spacing and page gutters;
   - surface, border and shadow hierarchy;
   - blue-to-violet brand gradient;
   - positive, negative, warning and unavailable states;
   - shared control heights and radii;
   - desktop, tablet and mobile breakpoints.
3. Rebuild the application shell:
   - fixed desktop sidebar;
   - responsive mobile drawer;
   - shared page header;
   - data-source status chip;
   - user/account menu;
   - active-route styling.
4. Create reusable primitives:
   - inline SVG icon adapter;
   - buttons and icon buttons;
   - segmented control;
   - inputs, selects and toggles;
   - status dot and status message;
   - skeleton, empty, error and unavailable states;
   - dialog/drawer foundation.
5. Keep `WorkspaceProvider` mounted above route content so route changes do not reset sockets, polls or authentication.
6. Preserve legacy component styles only where a screen has not yet migrated. Delete legacy CSS incrementally after its final consumer is removed.

### Foundation acceptance gate

- [ ] Sidebar and header match the shared parts of all five references.
- [ ] Every current route still renders and remains navigable.
- [ ] Authentication, logout and route-persistent workspace state still work.
- [ ] Light mode is the visual baseline; no old lime action styling leaks into the new shell.
- [ ] Desktop and mobile navigation are keyboard accessible.
- [ ] `npm run lint` and `npm run build` pass.

### Commit boundary

```text
refactor(web): establish shared UI shell
```

</details>

<details open class="node">
<summary>3. Screen sequence - Commits 2 through 6</summary>

<details open class="disc">
<summary>Stage 1 - Realtime</summary>

Detailed plan: [01-realtime-screen.md](./01-realtime-screen.md)

Why first: this screen owns the shared selected market and live connection behavior that later screens consume.

Primary work:

- Parameterize API methods and WebSocket subscriptions instead of hardcoding `ETHUSDT`.
- Load supported pairs from the Go API.
- Build the four-chart grid and connection information rail.
- Preserve sequence recovery, historical loading and stale states.
- Consume real BBO/recent events only when present.

Exit gate:

- [ ] Pair and timeframe changes affect every relevant request/subscription.
- [ ] Four chart cards update independently without duplicate sockets.
- [ ] No displayed price, signal, latency or tick is fabricated.
- [ ] Reference comparison passes at desktop, laptop, tablet and mobile sizes.
- [ ] Web lint/build and relevant market/WebSocket tests pass.

Commit:

```text
refactor(web): rebuild realtime workspace
```

</details>

<details open class="disc">
<summary>Stage 2 - Discovery</summary>

Detailed plan: [03-discovery-screen.md](./03-discovery-screen.md)

Why second: it introduces the real strategy-selection and search configuration state required by Backtest.

Primary work:

- Add `/discovery` and preserve `/search` through a redirect.
- Build the strategy catalog and combined-strategy editor.
- Replace the hardcoded search payload with the visible draft.
- Integrate real progress, actions, leaderboard and provenance.
- Keep genetic search disabled because the generator is not implemented.

Exit gate:

- [ ] Strategy choices come from the registry.
- [ ] Visible policy, weights, method and limits match the submitted request.
- [ ] Pause, resume, cancel, direct backtest and provenance work.
- [ ] Leaderboard units remain truthful.
- [ ] Web lint/build and search/composite tests pass.

Commit:

```text
refactor(web): rebuild strategy discovery
```

</details>

<details open class="disc">
<summary>Stage 3 - Backtest</summary>

Detailed plan: [04-backtest-screen.md](./04-backtest-screen.md)

Why third: it reuses the selected market and strategy state established in Stages 1 and 2.

Primary work:

- Build the configuration strip and immutable submitted snapshot.
- Parameterize dataset and experiment requests.
- Preserve fee, slippage, stop-loss and take-profit fields in the web adapter.
- Build the real result chart, trade ledger, KPIs and assumptions.
- Derive markers and summary values only from persisted result data.

Exit gate:

- [ ] Every visible filter changes the submitted snapshot or is removed.
- [ ] Queued, running, completed, failed and no-trades states are distinct.
- [ ] Trade values and metrics use correct units and persisted data.
- [ ] Deterministic execution and provenance behavior remain intact.
- [ ] Web lint/build and experiment/backtest tests pass.

Commit:

```text
refactor(web): rebuild backtest results
```

</details>

<details open class="disc">
<summary>Stage 4 - News Crawler</summary>

Detailed plan: [05-news-crawler-screen.md](./05-news-crawler-screen.md)

Why fourth: the read-only news and sentiment flows are already available, while crawl administration has a clear API boundary.

Primary work:

- Rebuild the feed, extraction workflow and analysis rail.
- Preserve real news, sentiment aggregate and manual text analysis.
- Add safe auto-refresh and asset filtering.
- Keep Website/HTML modes unavailable under the current RSS-only implementation.
- Expose source management and crawl commands only through authorized Go API endpoints if backend expansion is included.

Exit gate:

- [ ] News and sentiment values come from real endpoints.
- [ ] Static system explanations are visibly different from live telemetry.
- [ ] Unsupported modes cannot be activated.
- [ ] Role-aware controls do not bypass Go API auth/CSRF.
- [ ] Web lint/build and news/sentiment tests pass.

Commit:

```text
refactor(web): rebuild news crawler workspace
```

</details>

<details open class="disc">
<summary>Stage 5 - Strategy Engine</summary>

Detailed plan: [02-strategy-engine-screen.md](./02-strategy-engine-screen.md)

Why last: it has the largest functional gap and may require a separate backend implementation decision.

Primary work:

- Add `/strategies` and the complete authoring composition.
- Build prompt, URL, parsed summary, JSON, validation and library form states.
- Use the current strategy catalog for supported indicators and existing library rows.
- Do not simulate prompt analysis, remote extraction, validation success or saving.
- Connect full actions only after authenticated authoring contracts exist.

Exit gate:

- [ ] The screen matches the reference workflow and remains truthful when authoring APIs are unavailable.
- [ ] If authoring APIs are in scope, analyze, extract, validate and save work end to end.
- [ ] URL extraction enforces server-side SSRF and content controls.
- [ ] Invalid definitions cannot be saved.
- [ ] Web lint/build and new authoring contract tests pass.

Commit:

```text
refactor(web): add strategy authoring workspace
```

</details>

</details>

<details open class="node">
<summary>4. API boundary checkpoint</summary>

### Purpose

Separate visual refactoring from new backend product capabilities. Existing behavior should remain functional, but missing services must not be silently replaced with client-side demos.

### Supported primarily through frontend refactoring

- Realtime candles, pairs, market status and WebSocket subscriptions.
- Strategy registry listing.
- Experiment submission and result retrieval.
- Search run creation, polling and lifecycle actions.
- Leaderboard and provenance.
- News list, sentiment aggregate and manual sentiment prediction.

### Requires backend contract expansion for full parity

- Prompt-based strategy authoring.
- URL extraction and strategy parsing.
- Authored-strategy validation and persistence.
- News source listing through the public Go API.
- Admin crawl and sentiment-backfill commands through the public Go API.
- Website/HTML extraction modes.
- Extraction-template and self-healing telemetry.
- Genetic discovery.

### Default delivery rule

If backend expansion is not explicitly included, implement the screen with accurate unavailable/disabled states and complete all supported flows. Do not mark unsupported actions as successful. Functional completion for those actions remains open until the required contracts are approved and implemented.

</details>

<details open class="node">
<summary>5. Per-screen execution loop</summary>

Use the same loop for each stage:

1. Re-open the matching reference image at original detail.
2. Review the detailed screen plan and current component/API contracts.
3. Implement the smallest complete vertical slice for that screen.
4. Run lint, build and focused tests.
5. Start the real local stack required by the screen.
6. Verify loading, empty, success, unavailable, stale and failure states.
7. Capture temporary comparison screenshots at:
   - `1680 x 944`;
   - `1440 x 900`;
   - `1024 x 768`;
   - `390 x 844`.
8. Compare hierarchy, spacing, typography, controls and responsive behavior with the source image.
9. Fix visual and behavior regressions before moving on.
10. Review the screen-specific diff and create its isolated commit.

Temporary screenshots and browser traces are verification artefacts. Keep them outside committed source unless the user explicitly requests otherwise.

</details>

<details open class="node">
<summary>6. Cross-screen consistency rules</summary>

- One shared sidebar, logo treatment, page header and account menu.
- One token source for spacing, typography, radii, borders, status and brand colors.
- One selected market model reused by Realtime, Discovery and Backtest.
- One strategy identity format: `strategy_id`, immutable version and display name.
- One status vocabulary for loading, live, stale, unavailable, queued, running, completed, failed and cancelled.
- One API error-normalization path and one notice/toast pattern.
- One responsive breakpoint system.
- One accessible dialog/drawer implementation.
- Inline SVG or code-native icons only; do not add image assets outside `UI-reference/`.
- All displayed runtime values must be API-derived, WebSocket-derived or explicitly labelled documentation.

</details>

<details open class="node">
<summary>7. Final regression and cleanup - Optional Commit 7</summary>

### Final pass

1. Navigate through all five routes without reload and verify provider state persists correctly.
2. Confirm sockets reconnect only when market subscription inputs change.
3. Confirm polls and timers stop on completion or unmount.
4. Verify every active sidebar item and compatibility redirect.
5. Verify user roles, disabled actions, CSRF commands and logout behavior.
6. Run complete web lint/build plus relevant Go, research and AI tests if their contracts changed.
7. Run the responsive visual matrix for every screen.
8. Remove unused legacy components, selectors, theme code and route-specific CSS only after reference searches confirm no consumers remain.
9. Run `git diff --check` and review the final diff for unrelated files.
10. Confirm `blueprint/` has no diff.

### Final acceptance checklist

- [ ] All five screens share one coherent design system.
- [ ] Each screen matches the corresponding image's hierarchy and density.
- [ ] Existing functional behavior has no regression.
- [ ] Unsupported behavior is explicit and non-interactive.
- [ ] Desktop, laptop, tablet and mobile layouts are usable.
- [ ] Accessibility and keyboard checks pass.
- [ ] No temporary screenshots, traces or generated output are staged unintentionally.
- [ ] `blueprint/` is untouched.
- [ ] Commit history remains reviewable by foundation and screen.

Optional cleanup commit:

```text
refactor(web): finalize UI consistency
```

</details>

<details open class="node">
<summary>8. Expected commit sequence</summary>

```text
1. refactor(web): establish shared UI shell
2. refactor(web): rebuild realtime workspace
3. refactor(web): rebuild strategy discovery
4. refactor(web): rebuild backtest results
5. refactor(web): rebuild news crawler workspace
6. refactor(web): add strategy authoring workspace
7. refactor(web): finalize UI consistency        // only if cleanup is material
```

Do not combine stages only to reduce commit count. A stage may use several local work sessions, but it reaches its commit boundary only after its exit gate passes.

</details>
