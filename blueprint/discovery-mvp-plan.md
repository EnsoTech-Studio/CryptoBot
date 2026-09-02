# Strategy Discovery MVP Plan

Status: `IMPLEMENTED — runtime verified locally; Supabase live replay interrupted by provider restart`

This document defines a one-day strategy-discovery demonstration and its
implemented verification contract. Runtime, database, API, UI, and environment
changes are tracked in repository code; live evidence remains data/provider
dependent.

## Goal

Demonstrate a bounded, archive-driven discovery system:

```text
different generators propose strategies
  -> system backtests train data
  -> validates out of sample
  -> keeps robust, diverse candidates
  -> selects winners as parents
  -> stops automatically
```

Keep current Go edge, Python research service, PostgreSQL queue, immutable
experiment snapshots, BacktestEngine, Evaluator, and worker leases. Discovery
mode evolves the current durable search core; it does not introduce workflow
frameworks, agent frameworks, vector databases, Optuna, DEAP, Ray, CPCV, PBO,
Deflated Sharpe, MAP-Elites, or Pareto optimization.

## Planned module boundary

Keep planned code small and inside Python research:

```text
app/services/discovery/
├── controller.py   # durable discovery orchestration
├── archive.py      # trials, assessments, lineage, parent queries
├── schema.py       # candidate and assessment contracts
├── generators.py   # random, mutation, crossover, ensemble, LLM
├── selection.py    # generator and parent selection
└── validation.py   # split, filters, score, diversity checks
```

`DiscoveryController` owns sequencing only. Backtesting, evaluation, queue
admission, ranking, and durable persistence remain existing service concerns.
Run one active candidate at a time in discovery mode. This keeps lineage,
generator adaptation, and stopping deterministic while ordinary runs may still
use worker concurrency.

## Candidate contract

All generators output one immutable `StrategyCandidate` shape:

```python
@dataclass(frozen=True)
class StrategyCandidate:
    id: UUID
    strategy_spec: CandidateSpec
    generator: str                 # random | mutation | crossover | ensemble | llm
    parent_ids: tuple[UUID, ...]
    generation: int
    hypothesis: str | None = None
    operation: str | None = None
```

`CandidateSpec` is not arbitrary Python or a new free-form strategy language.
It wraps existing safe, versioned catalog DSL:

```text
CandidateSpec
├── strategy: single catalog definition OR flat CompositeDefinition
└── risk_policy: stop-loss / take-profit override
```

Candidate hash is canonical JSON over the complete `CandidateSpec`, including
risk policy. The experiment compiler passes `strategy` to the existing
strategy runtime and materializes `risk_policy` into the immutable experiment
snapshot.

LLM output may only reference allowed registered strategy versions, valid
parameter values, configured risk values, and flat composites. It cannot write
Python, publish a strategy definition, create a nested composite, call the
backtest engine, write result tables, or alter stop conditions.

## Generators

All generators share the candidate contract and archive boundary.

| Generator | MVP behavior | Lineage |
| --- | --- | --- |
| Random | Seeded sample from allowed catalog strategies, parameter values, and risk values. | No parents; generation `0`. |
| Mutation | Clone one selected parent then mutate one compatible parameter, replace one leaf, add/remove a flat child, or change risk. | One parent; mutation name stored. |
| Crossover | Combine compatible parameter choices or flat child lists from two parents; select one parent risk policy. | Two parents; `crossover` stored. |
| Ensemble | Select 2–5 unique catalog leaf strategies and sample normalized weights from Dirichlet distribution. Materialize a flat `weighted_vote` composite. | Members become parents; `ensemble` stored. |
| LLM | Return one validated catalog/composite candidate and hypothesis using a strict JSON contract. | Parent IDs depend on new, improve, or combine prompt mode. |

Flat ensembles are deliberate MVP scope. An ensemble can become a mutation or
crossover parent, but cannot become a member of another composite. Nested
composite semantics remain deferred.

### LLM generator

AI service remains provider boundary. Discovery adds an internal typed endpoint
backed by already-present `.env` values:

```text
OPENAI_BASE_URL
OPENAI_API_KEY
MODEL_CHEAP
LUNA_REASONING_EFFORT
```

No environment variable is added or exposed to browser/research callers. The
AI response includes provider model/version and prompt version for archive
provenance. A provider failure becomes a recorded generator failure; it never
silently falls back to random generation.

Three prompt modes return strict JSON containing `hypothesis`, `operation`,
and complete `CandidateSpec`:

1. **New hypothesis** receives allowed catalog, market-data capabilities, best
   archive summaries, and diversity gaps.
2. **Improve failed strategy** receives a parent, train/validation metrics,
   failure evidence, and asks for exactly one structural modification.
3. **Combination** receives top candidates with validation-return correlation
   and proposes a complementary flat ensemble.

Every result still passes catalog, parameter, causality, risk, canonical-hash,
duplicate, quota, and cost validation before queue admission.

## Discovery loop

```text
select runnable generator
  -> generate candidate
  -> archive duplicate check
  -> train experiment
  -> cheap filter
  -> three validation experiments
  -> robust assessment
  -> accept/reject and archive
  -> update generator statistics
  -> select parents for next trial
```

Train must become terminal before validation is admitted. Every candidate has
one train experiment and three validation experiments; all use the same
candidate and execution snapshot. Existing queue admission reserves cost for
all required backtests before starting a trial.

### Generator selection

Initial probabilities:

```python
PROBABILITIES = {
    "random": 0.35,
    "mutation": 0.30,
    "crossover": 0.15,
    "ensemble": 0.10,
    "llm": 0.10,
}
```

Every 20 terminal trials, calculate each generator's acceptance rate. Reserve
5% probability for each of five generators, then distribute remaining 75% in
proportion to `0.1 + acceptance_rate`. Exclude generators with no eligible
parent or unavailable model endpoint for that selection attempt and re-sample
from runnable generators. Do not create fake trials.

### Parent selection

For mutation, crossover, and ensemble selection:

- 80% chance: sample from highest-scoring 20% of accepted candidates.
- 20% chance: sample from all accepted candidates.
- No accepted parent: generator is temporarily ineligible; random and LLM-new
  remain available.

## Out-of-sample validation

Each discovery run freezes chronological candle-index boundaries:

```text
first 60%     discovery train
next 20%      validation V1, V2, V3 in three contiguous equal windows
final 20%     sealed test
```

Each segment may load preceding candles only as causal indicator warmup. It
must not score, trade, or expose result facts before that segment's boundary.
The candidate may repeatedly see train and validation data. It may never see
test data during discovery.

Cheap train filter:

- finite Sharpe;
- at least 10 settled trades;
- terminal successful backtest.

Validation rejects a candidate when any window has fewer than 10 settled
trades or undefined Sharpe, or when:

```text
abs(train_sharpe - median(validation_sharpes)) > 1.0
```

For candidates passing those gates:

```text
score = median_validation_sharpe
      - 0.5 * abs(train_sharpe - median_validation_sharpe)
      - 0.2 * abs(worst_validation_drawdown_pct) / 100
      - 0.1 * complexity
      - 0.2 * similarity
```

`complexity` is clamped to `[0, 1]` from flat leaf count and non-default
parameter count. `similarity` is `0` at correlation `<= .95`; otherwise it is
the normalized excess through correlation `1.0`. Similarity penalty is waived
only when validation Sharpe beats current archive best by at least `.10`.
Accept only candidates with positive score.

Correlation uses aligned per-candle returns across the three validation
windows, compared against accepted archive survivors. Missing or insufficient
aligned data rejects the candidate with an explicit reason.

When normal completion finds an accepted candidate, schedule exactly one final
test experiment for the highest-scoring accepted candidate. Persist its result
separately. Test metrics never affect parent selection, acceptance, scores, or
generator probabilities. Cancelled runs and runs with no accepted candidate do
not run the test.

## Archive and durable records

Archive is central. It is the sole source for duplicate detection, parent
selection, diversity comparison, generator statistics, lineage, and demo
history. Store every terminal outcome, including schema failures, duplicate
skips, train rejections, validation rejections, and accepted candidates.

Planned persistence changes:

- `search_runs`: discovery mode snapshot, frozen split policy, generator
  policy/stats, selected final candidate, and final-test state.
- `search_candidates`: immutable generation, parent IDs, generator, operation,
  hypothesis, candidate specification/hash, and terminal status.
- Candidate-to-experiment partition link: candidate, `train`/`validation`/
  `test`, validation ordinal, immutable experiment ID, and segment range.
  This replaces one-experiment-per-candidate restriction for discovery mode.
- Immutable assessment record: train and validation metric references, gap,
  complexity, correlation, novelty, score, acceptance flag, and rejection
  reason.

Existing ordinary search modes retain their current one-candidate/one-
experiment behavior. Discovery archive queries are per search run; no cross-run
result reuse occurs in MVP.

## Public contract and observability

Add `generator_id: "discovery"` while preserving `grid`, `random_search`, and
`domain_guided`. Existing fields remain compatible. Discovery creates a
multi-generator run using frozen default policies above.

Expose archive detail through `GET /api/v1/search-runs/{id}/archive` and expand
search progress with accepted/rejected counts, active generator statistics,
best candidate ID/score, lineage availability, and sealed-test state. Go only
proxies these Python-owned query/command contracts.

Add persisted progress/events for candidate proposed, cheap-rejected,
validation-completed, assessed, accepted/rejected, final-test-started, and
final-test-completed. Current queue/lease/outbox guarantees remain unchanged.

## Stop policy

Stop when first condition occurs:

```text
trials >= 500
elapsed active time >= 2 hours
backtest budget or quota exhausted
100 terminal trials without best score improving by >= 0.02
```

Explicit pause, resume, and cancel behavior stays owned by `SearchRun`. Pause
prevents next candidate admission; cancel prevents future discovery work and
does not trigger final test.

## Blueprint work

Update these planned architecture sources:

1. `blueprint/specs/search-loop.md`: canonical discovery mode, contracts,
   controller lifecycle, score, validation, archive, and stop policy.
2. `blueprint/specs/agent-architecture.md`: reduce discovery to three typed LLM
   prompt modes; keep it inside normal queue/admission boundaries.
3. `blueprint/design.md`: update search component/data-flow/persistence target.
4. Search/discovery/generator UML Mermaid sources and rendered assets.
5. Blueprint index and traceability mapping.

## Verification plan

- Data (csv): data/formatted/sol/2026-03-04
- Seeded random, mutation, crossover, and ensemble generation produce valid,
  canonical, reproducible candidates and correct lineage.
- LLM fixture validates strict output, provenance, invalid candidate rejection,
  provider failure recording, and no queue bypass.
- Duplicate candidate creates no duplicate experiment. Train rejection creates
  no validation jobs.
- Split boundaries, causal warmup, three-window median, minimum trades,
  gap threshold, complexity penalty, correlation penalty, and test isolation
  have deterministic fixture tests.
- Parent 80/20 selection, adaptive generator update, 5% exploration floor,
  unavailable-generator re-sampling, and all stop conditions are tested.
- Coordinator restart/reconcile preserves archive state and cannot duplicate a
  candidate partition experiment.
- Demo evidence shows random generation followed by mutation/crossover lineage,
  then a complementary flat ensemble with validation evidence and one sealed
  final test.
