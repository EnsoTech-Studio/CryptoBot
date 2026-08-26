# Screen 03 - Strategy Discovery

| Field | Value |
| --- | --- |
| Reference | `UI-reference/discover.jpg` |
| Target route | `/discovery` with redirect from `/search` |
| Navigation label | `Discovery` |
| Delivery order | 3 of 5; depends on shared shell and strategy catalog |
| Primary data | Strategies, search runs, experiments and leaderboard |
| Plan status | Mostly supported; genetic search and live aggregate signal are gaps |

## In plain words

Turn the current Search and Leaderboard pages into one coherent discovery workspace. The user chooses strategy building blocks, assigns weights, starts a supported search method, watches real progress, and reviews ranked results. Unsupported methods and unavailable live signals must be clearly identified instead of being simulated.

<details open class="node">
<summary>1. Outcome and scope</summary>

### User outcome

The user can compose strategies from the real registry, configure a bounded discovery run, start or control it, and see the real leaderboard update as candidates are evaluated.

### Included

- Add `/discovery` and redirect `/search` to preserve old links.
- Merge current `SearchPanel` and `LeaderboardPanel` into the reference layout.
- Build a selectable simple-strategy catalog from `GET /api/v1/strategies`.
- Add selected strategy chips, normalized weights and combination-policy controls.
- Pass a real discovery configuration into `POST /api/v1/search-runs` instead of using the hardcoded web payload.
- Preserve pause, resume, cancel, polling, ranking and provenance actions.
- Add a direct backtest action using the selected strategy children.
- Keep all progress and ranking values tied to API data.

### Excluded

- Genetic search until a backend generator exists.
- Invented LONG/HOLD/SHORT scores when no real aggregate signal is available.
- Converting leaderboard return to USDT unless the API includes the run's initial equity.
- Drag-and-drop ordering; selection and keyboard-reorder controls are sufficient.

</details>

<details open class="node">
<summary>2. Visual contract extracted from the reference</summary>

### Desktop composition

- Shared sidebar and page header.
- Three main columns:
  - simple strategy catalog, approximately `290px`;
  - combined strategy builder, approximately `440px`;
  - discovery workflow, leaderboard and method/progress area using the remaining width.
- Left and middle columns run nearly the full viewport height.
- Right column is vertically split into workflow, leaderboard, then method and progress panels.
- Use one border per major area. Rows inside catalog and method selector are flat list items separated by subtle lines.

### Typography and density

- Title: `Strategy Engine & Loop Discovery`, `28-30px`, bold.
- Subtitle: `14px`, muted.
- Section headings: `16px`, bold.
- Strategy title: `14px`, semibold; descriptions: `12px`, muted.
- Leaderboard cells: `12-13px` with tabular numeric values.
- Main column gaps: `16px`; panel padding: `16px`; row gap: `10-12px`.

### Color and visual motifs

- Shared blue-violet primary gradient.
- Strategy families use restrained accent tints: violet, blue, green, amber and pink.
- Selected chips use pale blue/violet fills and a clear remove control.
- Slider tracks are blue with visible numeric inputs.
- LONG is green, HOLD neutral gray, SHORT red.
- Workflow uses five circular line-icon steps connected by thin arrows.
- Top-three leaderboard ranks use gold, silver and bronze accents; all other rows remain neutral.

### Visible copy

- Title: `Strategy Engine & Loop Discovery`.
- Subtitle: `Tạo strategy đơn, strategy kết hợp và tự động tìm biến thể tốt nhất`.
- Sections: `Strategy đơn`, `Strategy kết hợp`, `Weighted Voting (Tín hiệu tổng hợp)`, `Loop Discovery`, `Leaderboard (Top strategies)`, `Phương pháp Discovery`, `Tiến trình Discovery`.
- Actions: `Tạo strategy đơn mới`, `Lưu strategy kết hợp`, `Backtest ngay`.
- Workflow: `Generate`, `Backtest`, `Evaluate`, `Rank`, `Leaderboard`.

</details>

<details open class="node">
<summary>3. Existing implementation mapping</summary>

| Current code | Reuse | Required change |
| --- | --- | --- |
| `web/app/search/page.tsx` | Existing route entry | Replace with redirect to `/discovery` after the new route is stable |
| `SearchPanel` in `Operations.tsx` | Search status and actions | Split into discovery config, workflow and progress components |
| `LeaderboardPanel.tsx` | Sorting, refresh and provenance | Restyle and embed in discovery screen |
| `WorkspaceProvider.startSearch()` | Start and polling lifecycle | Accept a typed `SearchDraft`; remove hardcoded strategy IDs/method |
| `WorkspaceProvider.searchAction()` | Pause/resume/cancel | Preserve; expose status-aware enabled actions |
| `api.strategies()` | Strategy catalog | Use family, description, parameters and composite flags |
| `api.createExperiment(children)` | Direct backtest | Pass selected normalized weights and market selection |
| `api.leaderboard()` | Ranked results | Preserve real return, win rate, score and provenance |

### Capability matrix

| Reference behavior | Backend support | Delivery choice |
| --- | --- | --- |
| Grid search | Supported by research | Available if exposed in method mapping |
| Random search | Supported as `random` or `random_search` | Available |
| Domain-guided search | Supported as `domain_guided` | Available |
| Genetic search | Not implemented | Visible but disabled with `Chưa hỗ trợ` |
| Weighted vote | Supported | Available; weights must sum to 1.0 |
| Majority vote | Supported | Optional advanced policy |
| Live aggregate signal | No dedicated API; overlays may be empty | Show `Chưa có dữ liệu` unless a real signal/evidence frame exists |
| Leaderboard profit in USDT | API returns percentage, not starting equity | Display `Return (%)`; do not label it USDT |
| Current iteration out of 500 | API returns generated/tested and configured stop limit | Display `tested / max_candidates` from the submitted draft |

</details>

<details open class="node">
<summary>4. Target component and state design</summary>

### Components

- `DiscoveryScreen`: route composition and top-level state ownership.
- `StrategyCatalog`: registry-derived list with search/filter support.
- `CombinedStrategyBuilder`: selected chips, suggestions and combination policy.
- `WeightEditor`: enabled children, accessible range controls, numeric inputs and total.
- `AggregateSignalPanel`: renders only real aggregate evidence or an explicit unavailable state.
- `DiscoveryWorkflow`: static five-step process explanation plus current stage highlight.
- `DiscoveryLeaderboard`: compact real leaderboard with sort and provenance actions.
- `DiscoveryMethodSelector`: grid, random, domain-guided and disabled genetic rows.
- `DiscoveryProgress`: status, tested count, generated count, best score and best candidate.
- `DiscoveryRunActions`: start, pause, resume, cancel and retry.

### Draft state

```ts
type DiscoveryMethod = "grid" | "random_search" | "domain_guided";

type DiscoveryDraft = {
  selectedStrategyIds: string[];
  weights: Record<string, number>;
  policy: "weighted_vote" | "majority_vote";
  method: DiscoveryMethod;
  maxCandidates: number;
  maxDurationSec: number;
  maxNonImproving: number;
  seed: number;
  market: MarketSelection & { timeframe: string };
};
```

### State rules

- Require two to five selected strategies for a combined strategy.
- Keep strategy IDs unique and remove their weight when a chip is removed.
- For weighted vote, normalize weights to six decimal places and require the total to equal `1.0` before submit.
- For majority vote, hide or disable weight inputs because the backend policy does not use them.
- Disable draft editing while a start request is being accepted; allow editing a copy after the run starts.
- Persist the draft locally, but persist run status only from the API.
- Store the submitted stop conditions alongside `searchId` so progress has a truthful denominator.
- Map API status to workflow step and available commands.

</details>

<details open class="node">
<summary>5. API refactor</summary>

Replace the hardcoded `startSearch()` client with a typed method:

```ts
api.startSearch({
  generatorId,
  searchSpace: {
    strategyIds,
    cardinality,
    policies,
    parameterGrid,
  },
  stopConditions,
  market,
  seed,
});
```

Implementation requirements:

- Use the shared selected market from Screen 01.
- Resolve or create a dataset for the selected symbol/timeframe.
- Convert UI method names exactly to accepted generator IDs.
- Preserve idempotency keys and CSRF behavior.
- Validate the draft before network calls and surface structured API errors near the relevant controls.
- Update `api.createExperiment` to accept selected children and normalized weights for `Backtest ngay`.
- Keep leaderboard sort names aligned with the API. Client-only sorting is acceptable for the loaded page; server sort must be used when pagination is later added.
- Provenance remains in the existing inspector or moves to an accessible side drawer without losing content.

</details>

<details open class="node">
<summary>6. Implementation sequence</summary>

1. Add `/discovery/page.tsx` and update sidebar routing.
2. Extract search and leaderboard logic from monolithic panels into the target components.
3. Build the strategy catalog from real registry data; exclude the composite root from selectable children unless explicitly supported.
4. Implement chip selection, suggestions, policy and accessible weight editing.
5. Refactor `api.startSearch` and workspace action signatures to receive `DiscoveryDraft`.
6. Connect start/poll/pause/resume/cancel with status-aware buttons and preserved notices.
7. Embed the leaderboard and provenance action. Use return percentage rather than fake USDT profit.
8. Wire `Backtest ngay` to a real experiment request using the selected children.
9. Add the workflow stage visualization and progress details from search state.
10. Add the aggregate signal unavailable state; connect it only if real marker evidence is present.
11. Redirect `/search` to `/discovery`; decide whether `/leaderboard` redirects to the Discovery leaderboard anchor or remains a compatibility page.
12. Implement responsive and accessibility behavior, then remove obsolete search-specific CSS.

</details>

<details open class="node">
<summary>7. Responsive and accessibility requirements</summary>

- `>= 1500px`: three-column composition matching the reference.
- `1200-1499px`: catalog at `280px`, builder at `400px`, right region flexible.
- `900-1199px`: catalog plus builder in two columns; discovery and leaderboard span below.
- `< 900px`: single workflow column; catalog becomes a compact selector list.
- On mobile, selected chips wrap and weight rows remain at least `44px` high.
- Range controls require paired numeric inputs and an announced label/value.
- Method rows use radio inputs; genetic is a disabled radio with explanatory text.
- Workflow step state uses `aria-current="step"`.
- Tables keep headers associated with cells; transform to labelled rows below `640px`.
- Do not use color alone for LONG/HOLD/SHORT or rank medals.

</details>

<details open class="node">
<summary>8. Verification and acceptance</summary>

### Automated checks

- Unit-test weight add/remove/normalization and policy switching.
- Unit-test method-to-generator mapping and stop-condition payload construction.
- Component-test empty catalog, unavailable API, running, paused, completed, failed and cancelled runs.
- Component-test leaderboard sorting and provenance opening.
- Integration-test start -> poll -> pause/resume -> completion using the real public API contract.
- Run web lint/build plus existing search, composite and API tests.

### Visual checks

- Compare at the standard desktop, laptop, tablet and mobile sizes.
- Preserve the reference's three clear jobs: choose inputs, configure composition, observe discovery.
- Keep the right-side workflow readable; do not shrink five steps into illegible icons.
- Avoid adding extra nested cards around each row or metric.

### Done checklist

- [ ] Strategy choices come from the real registry.
- [ ] Submitted weights and policy match the visible draft.
- [ ] Search method and progress values match the real run.
- [ ] Genetic search is not presented as available.
- [ ] Leaderboard units are truthful.
- [ ] Pause, resume, cancel, direct backtest and provenance work.
- [ ] Old `/search` links still resolve.
- [ ] `blueprint/` is untouched.

</details>
