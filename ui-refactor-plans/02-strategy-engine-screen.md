# Screen 02 - Strategy Engine

| Field | Value |
| --- | --- |
| Reference | `UI-reference/strategy.jpg` |
| Target route | `/strategies` |
| Navigation label | `Strategy Engine` |
| Delivery order | 2 of 5; depends on the shared shell from Screen 01 |
| Primary data | Strategy catalog plus new authoring contracts |
| Plan status | UI-ready; functional completion has API dependencies |

## In plain words

Build the prompt-or-URL strategy authoring workspace shown in the reference. The user must be able to understand a parsed strategy, inspect its canonical JSON, see validation results, and save a versioned strategy. The current codebase only lists built-in strategies, so analysis, URL extraction, validation persistence, and save actions must remain unavailable until real contracts exist.

<details open class="node">
<summary>1. Outcome and scope</summary>

### User outcome

The user enters a Vietnamese natural-language strategy description or a supported public URL, receives a structured draft, reviews validation, and saves an immutable version to the strategy library.

### Included

- Add the `/strategies` page and active sidebar state.
- Recreate the four-column desktop authoring workspace and recent-import table.
- Define a typed client-side authoring state machine.
- Render parsed LONG, SHORT, risk, timeframe and applicability sections from a real response.
- Provide a read-only canonical JSON view with copy support.
- Validate required fields, logical consistency and supported indicators.
- Define the missing API contracts required for functional delivery.
- Preserve auth and role-aware command behavior.

### Excluded

- Client-side simulation of LLM output.
- Fetching arbitrary URLs directly from the browser.
- Saving a draft only to local storage while claiming it is in the shared library.
- Executing generated source code. The saved object is a validated declarative strategy definition.

</details>

<details open class="node">
<summary>2. Visual contract extracted from the reference</summary>

### Desktop composition

- Shared `236px` sidebar and page header from Screen 01.
- Main content begins with title, subtitle and live source chip.
- Authoring row is divided into four visual groups:
  - input column, approximately `360px`;
  - parsed summary column, approximately `250px`;
  - JSON definition column, approximately `400px`;
  - validation and save rail, approximately `330px`.
- Recent imports span the first three columns beneath the authoring row.
- Each group is one surface. Inner status sections use tinted rows, not cards inside cards.

### Typography and spacing

- Page title: `28-30px`, weight `700`.
- Subtitle: `14px`, muted gray.
- Section headings: `15-16px`, weight `650-700`.
- Code: Geist Mono, `11-12px`, line height `1.55`.
- Input labels: `12-13px`, weight `600`.
- Main gutters: `24-28px`; column gaps: `12-16px`; surface padding: `16px`.

### Color logic

- Primary buttons and active sidebar: shared blue-to-violet gradient.
- LONG: green tint and border; SHORT: red tint and border.
- Risk: violet tint; timeframe/applicability: pale blue.
- Validation success: green; incomplete/warning: amber; invalid: red.
- JSON syntax uses restrained purple, blue and red tokens on a near-white code surface.

### Visible Vietnamese copy

- Title: `Tạo Strategy từ Prompt / URL`.
- Subtitle: `Người dùng nhập ngôn ngữ tự nhiên hoặc link website để hệ thống sinh strategy và lưu vào thư viện`.
- Inputs: `Nhập mô tả strategy`, `Phân tích bằng LLM`, `Xóa`, `Nhập URL chiến lược`, `Trích xuất từ website`.
- Output: `Strategy đã phân tích`, `Định nghĩa strategy (JSON)`, `Sao chép`.
- Validation: `Kiểm tra & Validation`, `Thiếu trường bắt buộc`, `Kiểm tra logic`, `Chỉ báo hỗ trợ`.
- Save: `Lưu vào Strategy Library`, `Lưu Strategy`.
- Table: `Chiến lược đã import gần đây`.

</details>

<details open class="node">
<summary>3. Existing implementation mapping and gaps</summary>

| Capability | Current codebase | Required for this screen |
| --- | --- | --- |
| List strategies | `GET /api/v1/strategies` through Go API | Reuse for supported indicators and library list |
| Strategy metadata | ID, version, family, description, parameter schema, overlays | Extend UI types for authoring metadata when API exists |
| Analyze prompt | Not implemented | New authenticated authoring endpoint |
| Extract URL | Not implemented | Server-side fetch with allowlist, SSRF controls and content limits |
| Validate definition | Registry validation exists internally but no public authoring endpoint | New validation endpoint returning field-level issues |
| Save authored strategy | Go route is GET-only; research registry is code-backed | New persistence and versioning contract |
| Recent imports | Strategy list lacks source, tags and creation timestamp | Extend strategy library response or add authored-strategy list |
| LLM service | Current AI service is sentiment-only | Add a separate strategy-authoring capability; do not reuse sentiment endpoint |

### Required public contracts

The UI work may define types and disabled states first, but it must not mark the screen complete until equivalent real endpoints exist.

```text
POST /api/v1/strategy-authoring/analyze
POST /api/v1/strategy-authoring/extract
POST /api/v1/strategy-authoring/validate
POST /api/v1/strategies
GET  /api/v1/strategies?source=authored&limit=20
```

Expected analyze/extract response:

```ts
type StrategyAuthoringResult = {
  draft_id: string;
  definition: StrategyDefinition;
  canonical_json: string;
  parsed: {
    long_conditions: ConditionSummary[];
    short_conditions: ConditionSummary[];
    risk: { stop_loss_pct?: number; take_profit_pct?: number };
    timeframe?: string;
    pairs?: string[];
    market?: string;
  };
  validation: StrategyValidation;
  source: { kind: "USER_PROMPT" | "WEB_IMPORT"; url?: string };
};
```

Security requirements for URL extraction:

- Fetch on the server, never in the browser.
- Require HTTPS and an approved hostname policy.
- Resolve DNS and block loopback, private, link-local and metadata addresses.
- Limit redirects, response size, content type and processing time.
- Sanitize extracted text and never execute remote script.
- Record source URL, content hash, model/version and validation version for provenance.

</details>

<details open class="node">
<summary>4. Target component and state design</summary>

### Components

- `StrategyEngineScreen`: route-level composition and query-state restoration.
- `StrategyPromptForm`: description, character count, analyze and clear actions.
- `StrategyUrlForm`: URL validation, supported-source hint and extract action.
- `ParsedStrategySummary`: LONG, SHORT, risk, timeframe and applicability rows.
- `StrategyJsonViewer`: read-only formatted JSON, copy action and overflow behavior.
- `StrategyValidationPanel`: required fields, logic and indicator support results.
- `StrategyLibraryForm`: name, version, tags, source and save action.
- `RecentStrategyImports`: real library rows, source, created time, version, tags and status.
- `AuthoringUnavailable`: explicit API dependency state used before authoring endpoints are live.

### State machine

```text
idle
  -> analyzing | extracting
  -> draft_ready
  -> validating
  -> valid | invalid
  -> saving
  -> saved | save_failed
```

Rules:

- Prompt and URL are mutually exclusive inputs for one request.
- Clear resets only the current unsaved draft; it does not delete a saved strategy.
- Analyze/extract buttons require an authenticated user and a valid input.
- JSON is derived from the server definition. Editing JSON is out of scope for visual parity and reduces accidental drift.
- Save is enabled only for `validation.status === "valid"` and a valid library form.
- Use request IDs to ignore stale analysis responses if the input changes during a request.
- Confirm before discarding a dirty draft during navigation.

### Validation presentation

- Required fields: strategy ID/name, version, conditions, timeframe and valid risk values.
- Logic: operator/value compatibility, LONG/SHORT contradictions, positive periods, and risk bounds.
- Indicator support: compare every indicator against the registry response and version.
- Validation messages must come from structured issue codes; do not parse prose errors.
- The overall green success block appears only when every blocking issue has passed.

</details>

<details open class="node">
<summary>5. Implementation sequence</summary>

1. Add `/strategies/page.tsx` and update the shared navigation. Keep Settings disabled and leave existing `/search` behavior untouched until Screen 03.
2. Define authoring types, discriminated UI state and error normalization in a focused client module rather than enlarging `WorkspaceProvider` with form-local state.
3. Build the static responsive composition using the extracted tokens and exact content hierarchy.
4. Wire `GET /api/v1/strategies` to the supported-indicator validation row and recent built-in library fallback.
5. Add an API capability check. Until authoring contracts exist, show the complete layout in an unavailable state with command buttons disabled and a precise explanation.
6. Implement the real analyze, extract and validate clients after the Go API proxies equivalent research endpoints.
7. Render parsed cards and canonical JSON from the response; add clipboard success/error feedback.
8. Implement library form validation and the authenticated save request with idempotency protection.
9. Refresh the recent import table after save and select the new immutable version without mutating the prior version.
10. Add dirty-form navigation protection, responsive behavior and accessibility.

</details>

<details open class="node">
<summary>6. Responsive, interaction and accessibility requirements</summary>

- `>= 1500px`: four-column authoring layout matching the reference.
- `1200-1499px`: input plus parsed summary on the left, JSON center, validation rail right; recent table below.
- `768-1199px`: two-column layout; validation/save follows JSON.
- `< 768px`: one column in workflow order: input -> parsed -> JSON -> validation -> save -> recent.
- The JSON area must scroll internally on narrow screens without forcing the whole page wider.
- Use real `label` elements and associate error text with `aria-describedby`.
- Status cannot rely only on tinted backgrounds; include text and consistent icons.
- Copy action announces success once through a polite live region.
- Loading buttons retain their width and expose `aria-busy`.
- Validation groups use headings and lists, not clickable cards.
- Recent imports table becomes a labelled list on mobile rather than an unreadable compressed table.

</details>

<details open class="node">
<summary>7. Verification and acceptance</summary>

### Automated checks

- Unit-test prompt/URL mutual exclusion, dirty state and character/URL validation.
- Unit-test authoring response normalization and structured validation issue mapping.
- Component-test idle, analyzing, invalid, valid, saving, saved and unavailable states.
- Contract-test CSRF and auth behavior for all new public commands.
- Security-test blocked URL classes, redirects, oversized content and unsupported MIME types if backend scope is approved.
- Run web lint/build and the related Go/research service tests.

### Visual checks

- Compare at `1680 x 944`, `1440 x 900`, `1024 x 768`, and `390 x 844`.
- Preserve the strong left-to-right workflow: input -> interpretation -> JSON -> validation/save.
- LONG, SHORT, risk and timeframe rows must remain visually distinct without becoming nested card stacks.
- JSON text, buttons, form controls and table metadata must remain readable at laptop scale.

### Done checklist

- [ ] The screen matches the reference hierarchy and shared shell.
- [ ] No LLM, extraction, validation or save result is fabricated client-side.
- [ ] URL fetch security is enforced server-side.
- [ ] A saved strategy is versioned, traceable and visible after refresh.
- [ ] Invalid drafts cannot be saved.
- [ ] Built-in strategy listing continues to work if authoring is unavailable.
- [ ] Keyboard and screen-reader users can complete the full workflow.
- [ ] `blueprint/` is untouched.

</details>
