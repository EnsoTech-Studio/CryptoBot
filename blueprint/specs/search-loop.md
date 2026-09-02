# Đặc tả: Discovery Search Loop

Trạng thái: Blueprint target — chưa phải runtime claim  
Owner: Python `research`  
Runtime seam hiện có: `app/services/search.py`

## Mô tả

Discovery là `generator_id: "discovery"` bên trong SearchRun hiện có. Một
`DiscoveryController` durable tuần tự hoá đúng một candidate đang active:

```text
select generator -> propose -> duplicate/admission -> train
-> cheap filter -> V1/V2/V3 -> assess -> archive -> select parents -> stop
```

BacktestEngine, Evaluator, queue admission, worker lease, Ranking và immutable
experiment snapshot giữ ownership hiện có. Go chỉ auth/quota/proxy public
contract và fan-out event đã persist. Không thêm workflow/agent framework,
vector database, Optuna, DEAP, Ray, CPCV/PBO/Deflated Sharpe, MAP-Elites hoặc
Pareto optimization.

Ordinary `grid`, `random_search`, `domain_guided` giữ one-candidate/one-
experiment behavior. Discovery archive chỉ reuse trong cùng `search_run_id`.

## Immutable candidate contract

```python
@dataclass(frozen=True)
class StrategyCandidate:
    id: UUID
    strategy_spec: CandidateSpec
    generator: str  # random | mutation | crossover | ensemble | llm
    parent_ids: tuple[UUID, ...]
    generation: int
    hypothesis: str | None = None
    operation: str | None = None
```

`CandidateSpec` không phải Python arbitrary hay DSL mới. Nó bọc catalog DSL
safe/versioned hiện có:

```text
CandidateSpec
|- strategy: one catalog definition OR flat CompositeDefinition
`- risk_policy: stop-loss / take-profit override
```

Canonical hash là canonical JSON của toàn bộ `CandidateSpec`, gồm risk policy.
Compiler truyền `strategy` vào runtime hiện có và materialize `risk_policy`
vào immutable experiment snapshot. Composite chỉ một tầng: composite có thể là
parent nhưng không thể là leaf của composite khác.

## Generator policy

| Generator | MVP behaviour | Lineage |
| --- | --- | --- |
| `random` | Seeded sample catalog, compatible params và risk. | No parents, generation 0. |
| `mutation` | One parent; mutate one parameter/leaf/risk, or add/remove flat leaf. | Parent + operation. |
| `crossover` | Two compatible parents; combine params/flat children; select one risk. | Two parents + `crossover`. |
| `ensemble` | 2–5 unique catalog leaves, normalized Dirichlet weights, flat `weighted_vote`. | Members + `ensemble`. |
| `llm` | One validated catalog/flat-composite candidate. | Prompt-mode parent IDs. |

Initial selection probabilities are `random .35`, `mutation .30`, `crossover
.15`, `ensemble .10`, `llm .10`. Every 20 terminal trials, reserve `.05` for
each generator and distribute remaining `.75` proportional to
`0.1 + acceptance_rate`. Re-sample when generator has no eligible parent or
LLM endpoint unavailable; never create fake trial.

Mutation/crossover/ensemble parents: 80% sample highest-scoring 20% accepted
candidates; 20% sample all accepted. No accepted parent makes that generator
temporarily ineligible; random and LLM-new remain runnable.

## LLM provider boundary

LLM is one typed internal generator, backed only by existing server values
`OPENAI_BASE_URL`, `OPENAI_API_KEY`, `MODEL_CHEAP`, `LUNA_REASONING_EFFORT`.
No browser/research-facing environment variable is added. Archive records
provider model/version and prompt version. Provider failure is persisted as an
LLM generator failure; it never silently falls back to random.

Three strict-JSON prompt modes return `hypothesis`, `operation`, complete
`CandidateSpec`:

1. New hypothesis: allowed catalog, market capabilities, archive summaries,
   diversity gaps.
2. Improve failed strategy: parent metrics/failure evidence; exactly one
   structural change.
3. Combination: top candidates plus validation-return correlation; one
   complementary flat ensemble.

Response may reference only registered versions, configured parameter/risk
values and flat composites. It cannot write Python, publish definitions, make
nested composite, call backtest, write result tables or change stop policy.
Every output still passes catalog, parameter, causality, risk, hash, duplicate,
quota and cost validation before admission.

## Frozen split, filters and assessment

Run creation freezes chronological candle-index boundaries: first 60% train;
next 20% split into three contiguous equal V1/V2/V3; final 20% sealed test.
Segment may load preceding candles only for causal warmup. It must not trade,
score or expose facts before its boundary. Candidate may see train/validation,
never test during discovery.

Train is terminal before validation admission. Reserve queue cost for train and
all three validations before trial starts. Cheap filter requires successful
terminal backtest, finite Sharpe and at least 10 settled trades. Train reject
creates no validation job.

Each validation window requires finite Sharpe and at least 10 settled trades.
Reject if `abs(train_sharpe - median(validation_sharpes)) > 1.0`. For survivors:

```text
score = median_validation_sharpe
      - 0.5 * abs(train_sharpe - median_validation_sharpe)
      - 0.2 * abs(worst_validation_drawdown_pct) / 100
      - 0.1 * complexity
      - 0.2 * similarity
```

`complexity` is clamped `[0,1]` from flat leaf count and non-default parameter
count. `similarity` is zero at correlation `<= .95`, then normalized excess to
1.0. Waive similarity penalty only if validation Sharpe beats archive best by
at least `.10`. Correlation uses aligned per-candle returns across all three
validation windows against accepted survivors; missing/insufficient alignment
rejects with explicit reason. Accept only positive score.

Normal completion with accepted candidates schedules exactly one final test for
highest score. Persist separately. Test never changes acceptance, parents,
scores or generator probabilities. Cancelled/no-acceptance run never starts it.

## Archive, persistence and progress

Archive is sole per-run source for duplicate checks, lineage, parent selection,
diversity, generator stats and demo history. Persist terminal outcomes:
schema failure, duplicate skip, train/validation reject, provider failure and
acceptance.

| Record | Discovery additions |
| --- | --- |
| `search_runs` | mode snapshot, frozen split policy, generator policy/stats, final candidate/test state. |
| `search_candidates` | immutable spec/hash, generator, parents, generation, operation, hypothesis, terminal status. |
| candidate experiment partition | candidate, `train`/`validation`/`test`, validation ordinal, experiment ID, segment range. |
| assessment | immutable metric references, gap, complexity, correlation, novelty, score, accepted, rejection reason. |

Public query: `GET /api/v1/search-runs/{id}/archive`. Existing progress adds
accepted/rejected counts, active generator stats, best candidate ID/score,
lineage availability and sealed-test state. Persist events: proposed,
cheap-rejected, validation-completed, assessed, accepted/rejected,
final-test-started/completed.

## Lifecycle and stop policy

Pause prevents next candidate admission. Cancel prevents future discovery work
and final test. Reconcile after controller restart from immutable archive and
partition unique keys; no duplicate partition experiment.

Stop on first condition:

```text
trials >= 500
active elapsed >= 2 hours
backtest budget or quota exhausted
100 terminal trials without best score improvement >= .02
```

## Failure handling

| Condition | Result |
| --- | --- |
| Duplicate canonical hash | Archive duplicate skip; no experiment. |
| Invalid catalog/parameter/risk/cause | Terminal schema failure before queue. |
| LLM unavailable/invalid | Persist generator failure; select another runnable generator. |
| Train gate fails | Archive cheap rejection; no validation. |
| Validation/correlation fails | Archive rejection with evidence. |
| Worker/controller restart | Lease takeover/reconcile; partition unique key prevents duplicate work. |
| Pause/cancel | No next admission; cancel never starts final test. |

## Acceptance criteria

- [ ] Seeded random/mutation/crossover/ensemble candidates canonical, valid and reproducible with lineage.
- [ ] LLM fixture validates strict output/provenance, invalid rejection, provider failure and no queue bypass.
- [ ] Duplicate creates no duplicate experiment; failed train creates no validation jobs.
- [ ] Split/warmup, three-window median, gates, penalties and sealed-test isolation fixture tested.
- [ ] 80/20 parents, adaptive probabilities, exploration floor, re-sampling and every stop condition tested.
- [ ] Restart/reconcile preserves archive and cannot duplicate candidate partition experiment.
