# Screen 05 - News Crawler

| Field | Value |
| --- | --- |
| Reference | `UI-reference/news_crawler.jpg` |
| Target route | `/news` |
| Navigation label | `News Crawler` |
| Delivery order | 5 of 5; depends on the shared shell |
| Primary data | News items, sentiment aggregate and admin collection commands |
| Plan status | Read view supported; crawl control and extraction telemetry need contracts |

## In plain words

Rebuild the current news panel into the reference's collection-and-analysis workspace. Real news and sentiment can be shown now. Crawl control, source configuration, extraction templates, self-healing telemetry and event classification require additional public contracts, so the UI must distinguish live operational data from explanatory system diagrams.

<details open class="node">
<summary>1. Outcome and scope</summary>

### User outcome

The user sees incoming market news, understands sentiment coverage, and, when authorized, can manage approved RSS sources and start real collection. The extraction workflow is transparent without pretending unsupported modes or telemetry exist.

### Included

- Rebuild `/news` with the shared shell and reference layout.
- Preserve real news loading, links, source metadata, related coins and sentiment.
- Preserve aggregate label counts and coverage.
- Preserve manual text sentiment analysis in a secondary dialog/drawer so existing functionality is not lost.
- Define role-aware source configuration and crawl command contracts.
- Render extraction and self-healing stages from live telemetry only when such telemetry exists.
- Provide explicit explanatory states for unsupported Website/HTML modes.

### Excluded

- Browser-side crawling or arbitrary HTML fetch.
- Claiming Website or raw HTML extraction works when the research service supports RSS only.
- Enabling admin collection controls for student/researcher roles.
- Invented template versions, error rates, confidence, source counts or event-type percentages.
- Decorative news content not returned by the API.

</details>

<details open class="node">
<summary>2. Visual contract extracted from the reference</summary>

### Desktop composition

- Shared sidebar and page header.
- Full-width control strip below the title: source mode, assets, refresh interval, source settings and crawl action.
- Main row uses three regions:
  - input news list, approximately `380px`;
  - extraction and self-healing workspace, flexible and widest;
  - analysis output and strategy integration rail, approximately `340px`.
- The center region contains two large sections: four-stage extraction and four-stage self-healing flow.
- Avoid placing every stage in its own heavy card. Use aligned steps and light inner surfaces.

### Typography and density

- Title: `News Crawler & Phân tích thị trường`, `28-30px`, bold.
- Subtitle: `14px`, muted.
- Main section headings: `16px`, bold.
- News headline: `12-13px`, semibold, at most two lines on desktop.
- Metadata and technical steps: `11-12px`.
- Analysis metrics: `13-16px`, with tabular numeric alignment.

### Color and motifs

- Primary crawl action and selected segment: shared blue-violet system.
- Positive: green; neutral: cool gray; negative: red.
- RSS accent: amber; HTML/code accent: muted violet/blue.
- Extraction step numbers are blue circles connected by a thin dotted line.
- Self-healing decision uses a pale red diamond only when a real validation error path is represented.
- Strategy integration uses a simple line diagram, not a decorative illustration asset.

### Visible copy

- Title: `News Crawler & Phân tích thị trường`.
- Subtitle: `Thu thập tin tức, hiểu HTML bằng LLM, lưu template và phân tích sentiment`.
- Controls: `Nguồn`, `Website`, `RSS`, `HTML`, `Pair (Asset)`, `Auto refresh`, `Cấu hình nguồn`, `Bắt đầu crawl`.
- Sections: `Tin tức đầu vào`, `LLM-assisted Extraction`, `Self-healing extraction`, `Đầu ra phân tích`, `Tích hợp với Strategy`.
- Extraction stages: `HTML thô`, `LLM hiểu tag HTML`, `Sinh Extraction Template`, `Lưu version template`.
- Self-healing stages: `Validate kết quả`, `Lỗi cao?`, `LLM sửa template`, `Lưu version mới`.

</details>

<details open class="node">
<summary>3. Existing implementation mapping and gaps</summary>

| Capability | Current implementation | Plan |
| --- | --- | --- |
| News list | `GET /api/v1/news` through Go -> research | Reuse and restyle |
| Sentiment aggregate | `GET /api/v1/news/aggregate` | Reuse counts and coverage; calculate percentages from real counts |
| Manual sentiment test | `POST /api/v1/ai/predict` | Preserve in an `Analyze text` dialog |
| Source creation | Research has admin `POST /api/v1/admin/news-sources` | Add a secured Go proxy and UI for Admin only |
| Manual collect | Research has admin `POST /api/v1/admin/news/collect` | Add a secured Go proxy and crawl command state |
| Sentiment backfill | Research has admin endpoint | Optional secured command; do not expose as ordinary crawl |
| Source list/status | No public read endpoint | Add before source settings/status can be complete |
| Website/HTML sources | Research schema currently supports `kind: "rss"` only | Disable and label as planned, or expand backend in a separate scope |
| Extraction templates | No current runtime contract | Explanatory diagram only until API exists |
| Self-healing metrics | No current runtime contract | Explicit unavailable state until API exists |
| Event types | `NewsItem` has no event classification | Omit or add a real classification contract |
| Confidence score | Aggregate exposes average sentiment score, not model confidence | Label current metric accurately; do not rename it confidence |

### Required public admin contracts

```text
GET  /api/v1/admin/news-sources
POST /api/v1/admin/news-sources
POST /api/v1/admin/news/collect
POST /api/v1/admin/sentiment/backfill
```

The Go API must enforce authentication, CSRF, role and command rate limits before proxying research. The frontend must not call the internal research service directly.

### Optional contracts for full visual-function parity

```text
GET /api/v1/admin/news/extraction-status
GET /api/v1/admin/news/templates?source_id=...
GET /api/v1/news/events/aggregate?window=24h
```

These responses need version, validation counts, error rates, source health and timestamps. Without them, the center panels are product documentation rather than live telemetry and must be labelled accordingly.

</details>

<details open class="node">
<summary>4. Target component and state design</summary>

### Components

- `NewsCrawlerScreen`: page composition and refresh lifecycle.
- `NewsCrawlerControls`: source mode, asset filter, refresh interval and role-aware commands.
- `NewsFeed`: real items, update timestamp, loading/unavailable/empty states and pagination/link out.
- `ExtractionPipeline`: static workflow plus optional live template/status data.
- `SelfHealingPipeline`: static decision flow plus optional real validation telemetry.
- `SentimentSummary`: real distribution, analyzed count and coverage.
- `EventTypeSummary`: rendered only when event classification exists.
- `StrategyIntegration`: explains the real `news_sentiment` strategy registry entry and links to Strategy/Discovery.
- `NewsSourceDialog`: Admin-only approved RSS source creation and status.
- `ManualSentimentDialog`: preserves the current text analysis workflow.

### State

```ts
type NewsSourceMode = "rss" | "website" | "html";

type NewsFilters = {
  assets: string[];
  sourceKeys: string[];
};

type NewsRefreshInterval = 0 | 60 | 120 | 180 | 240 | 300;

type CrawlCommandState =
  | { status: "idle" }
  | { status: "submitting" }
  | { status: "completed"; results: CollectionResult[] }
  | { status: "failed"; message: string };
```

### State rules

- Default mode is `rss`, the only supported source type.
- Website and HTML segments remain visible for parity but disabled with a concise support message.
- Asset filtering is applied to `related_coins`; `All assets` includes unclassified items.
- Auto refresh pauses when the document is hidden and resumes without duplicate timers.
- Refresh requests are serialized to avoid race conditions.
- `Bắt đầu crawl` is enabled only for an authenticated Admin and a configured approved source.
- A successful collection command triggers news and aggregate refresh; it does not imply sentiment backfill succeeded.
- Manual sentiment prediction state remains local to its dialog.
- Analysis percentage denominator is `items_total`; handle zero safely.

</details>

<details open class="node">
<summary>5. Data presentation rules</summary>

### News feed

- Render title, source, published time, related assets and sentiment label from `NewsItem`.
- Use the external URL for the headline with `target="_blank"` and `rel="noreferrer"`.
- Do not manufacture article summaries because the current public item contract has no summary/content.
- Use an asset icon derived from a text monogram or inline SVG; do not add image files.

### Sentiment summary

- Convert label counts to percentages using `items_total` or analyzed count, and state which denominator is used.
- Show analyzed coverage as `items_analyzed / items_total` and percentage.
- If average score is shown, label it `Điểm sentiment trung bình`, not confidence.
- Show the aggregate response timestamp only if the API provides one; otherwise use the client fetch timestamp labelled `Cập nhật giao diện`.

### Extraction and self-healing panels

- Before telemetry APIs exist, label the section `Quy trình hệ thống` and render only stable architectural steps.
- Do not show sample version numbers such as `v1.4.2`, sample error percentages, or success timestamps.
- When telemetry exists, every value must include its source status and last-updated timestamp.
- Error-rate thresholds and automatic repair actions must come from backend policy, not frontend constants presented as truth.

### Strategy integration

- Confirm `news_sentiment` exists in the strategy registry before showing it as available.
- Link to `/strategies` or preselect it in `/discovery` through a documented query parameter.
- If unavailable, show `Strategy News Sentiment chưa sẵn sàng` rather than a clickable fake module.

</details>

<details open class="node">
<summary>6. Implementation sequence</summary>

1. Rebuild `/news` using the shared shell, controls, three-region layout and current real read endpoints.
2. Split `NewsPanel.tsx` into feed, aggregate and manual analysis components.
3. Add asset/source filter state and safe auto-refresh with request serialization.
4. Preserve current manual text prediction in a secondary accessible dialog.
5. Implement RSS, Website and HTML segment states; only RSS is enabled under current capabilities.
6. Add Admin-only Go proxy handlers for source listing/creation and collection if functional crawl control is approved in this refactor scope.
7. Add typed web clients and source configuration/crawl command states.
8. Build extraction and self-healing workflow diagrams with inline CSS/SVG and clear `system process` labeling.
9. Connect template/version/error telemetry only after real endpoints are implemented.
10. Build the real sentiment summary and conditionally render event types.
11. Connect strategy integration to the registry and Discovery route.
12. Add responsive/accessibility behavior and remove obsolete news-panel CSS.

</details>

<details open class="node">
<summary>7. Responsive and accessibility requirements</summary>

- `>= 1500px`: three-region layout matching the reference.
- `1200-1499px`: feed at `340px`, analysis rail at `300px`, center flexible.
- `900-1199px`: feed plus analysis in two columns; extraction spans below.
- `< 900px`: controls wrap and all regions stack in workflow order.
- Source-mode tabs use a segmented radio group with disabled-state explanation.
- Auto-refresh uses a labelled radio/segmented group and exposes the current interval.
- Crawl loading uses `aria-busy` and reports one completion summary, not every item.
- Sentiment distribution includes text labels and percentages outside the colored bar.
- News headlines remain keyboard reachable and focus-visible.
- Pipeline diagrams include an ordered-list text equivalent.
- Dialogs trap focus, close on Escape and restore focus to their trigger.

</details>

<details open class="node">
<summary>8. Verification and acceptance</summary>

### Automated checks

- Unit-test aggregate percentage/coverage calculations and zero totals.
- Unit-test asset/source filters and refresh timer cleanup.
- Component-test loading, unavailable, empty, populated, filtered-empty and refresh-error states.
- Component-test role behavior for Student/Researcher versus Admin crawl controls.
- Contract-test source creation, SSRF rejection, collect commands and CSRF through the Go API if those endpoints are added.
- Run web lint/build plus existing news, sentiment and API tests.

### Visual checks

- Compare at the standard desktop, laptop, tablet and mobile sizes.
- Ensure the feed, extraction process and analysis output remain the three obvious jobs of the page.
- Keep technical stages readable; do not compress code/template text below the typography floor.
- Preserve open white space and avoid wrapping every stage in multiple nested cards.

### Done checklist

- [ ] Every news item and sentiment metric comes from a real endpoint.
- [ ] Unsupported Website/HTML modes are not actionable.
- [ ] Crawl commands are role-aware and pass through the Go API.
- [ ] Explanatory pipeline content is distinguishable from live telemetry.
- [ ] Existing manual sentiment analysis remains available.
- [ ] News strategy integration reflects the real registry.
- [ ] Refresh timers and requests do not duplicate or race.
- [ ] `blueprint/` is untouched.

</details>
