# Requirement Traceability & Verification Gates

> Version 1.5. `[SRC]` là yêu cầu trong đề bài/PDF; `[SRC-ADD]` là yêu cầu bổ sung trong `note.txt`; `[PD]` là quyết định thiết kế của nhóm. `Designed` chỉ xác nhận đã có contract trong blueprint, không đồng nghĩa runtime đã hoàn thành.

Giá trị trạng thái: `Yes`, `Partial`, `No`, `Optional`. Cột `Verified` chỉ được đổi thành `Yes` khi có test/demo/benchmark artifact thật; sơ đồ không phải implementation evidence.

| ID | Source | Requirement / invariant | Canonical spec | Diagram | Designed | Implemented | Verified | Verification gate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R01 | [SRC] | Binance historical + realtime normalized Candle/BBO | `specs/market-data.md` | 04, 05, 09, 20, 35 | Yes | Partial | No | Provider contract, integration reconnect/backfill, zero missing/duplicate closed candles |
| R02 | [SRC] | Candlestick dashboard, tối đa 4 panel độc lập | `specs/market-data.md`, `specs/chart-overlay.md` | 01, 04, 05, 34, 35 | Yes | Partial | No | UI test đổi panel 1 không request/render lại panel 2–4 |
| R03 | [SRC] | MA, RSI, Bollinger, Support/Resistance qua Plugin Registry | `specs/strategy-registry.md` | 03, 10, 22, 36 | Yes | Partial | No | Registry/fixture tests; architecture test cấm branch theo strategy ID |
| R04 | [SRC] | Manual composite với policy giải thích được | `specs/composite-strategy.md` | 03, 10, 34, 36 | Yes | Partial | No | Majority/weighted fixtures + immutable candidate hash |
| R05 | [SRC] | Backtest historical, cùng runtime với realtime | `specs/backtest.md`, `specs/experiment.md` | 11, 16, 17, 19, 22, 23 | Yes | Partial | No | Hand-calculated LONG/SHORT/BBO fixture; parity hash test |
| R06 | [SRC] | Return, Win Rate, Max Drawdown, Number of Trades | `specs/evaluation.md` | 11, 17, 24 | Yes | Partial | No | Metric golden fixtures, evaluator-version provenance |
| R07 | [SRC] | Random Search bắt buộc; CandidateGenerator thay thế được | `specs/search-loop.md` | 11, 12, 15, 37 | Yes | Partial | No | Seed determinism, generator contract, bounded batch/stop test |
| R08 | [SRC] | Top-K Leaderboard | `specs/leaderboard.md` | 11, 24 | Yes | Partial | No | Ranking golden fixture, append-only/provenance test |
| R09 | [SRC] | Buy/Sell và Entry/Exit visualization | `specs/visualization.md`, `specs/chart-overlay.md` | 10, 22, 24 | Yes | Partial | No | API/schema/UI marker alignment test |
| R10 | [SRC] | News Collect → Store → Sentiment | `specs/news.md`, `specs/sentiment.md` | 13, 14, 38 | Yes | Partial | No | Collection survives AI-down; null/unavailable is not fake neutral |
| R11 | [SRC] | Strategy versioning + reproducible experiments | `specs/strategy-registry.md`, `specs/experiment.md` | 06, 16, 22, 24 | Yes | Partial | No | Rerun same snapshot/version gives same facts/hash |
| R12 | [SRC] | Search stop conditions; không có unbounded loop | `specs/search-loop.md` | 12, 15 | Yes | Partial | No | Candidate/time/no-improvement/cancel/pause recovery tests |
| R13 | [SRC] | System Context, Container, Component, Data/Realtime/Strategy/Search flows | `design.md` §2–§6 | 01–39 | Yes | N/A | Yes | 39 canonical source diagrams parse/render and links resolve |
| R14 | [SRC] | Modifiability, scalability, realtime, reliability, performance, maintainability, observability, reproducibility | `design.md` §8–§11, `specs/observability.md` | 07–09, 14–20, 24, 35–39 | Yes | Partial | No | Architecture tests, crash recovery demo, load benchmark, metric dashboard |
| A01 | [SRC-ADD] | Chọn single/combined; Automatic Loop Discovery hiển thị best variants | `specs/composite-strategy.md`, `specs/search-loop.md`, `specs/leaderboard.md` | 10–12, 31, 34, 37 | Yes | Partial | No | End-to-end search run shows validated unique Top-K candidates |
| A02 | [SRC-ADD] | Natural language hoặc URL → draft cho user review | `specs/strategy-authoring.md`, `specs/agent-architecture.md` | 21, 25–27, 33 | Yes | Partial | Partial | `tests/test_authoring.py` và `tests/integration/test_queue_integration.py::test_approved_dsl_strategy_is_resolved_by_the_backtest_worker`: text → immutable draft → review/approve → runtime. Còn thiếu URL/SSRF/prompt-injection demo đầy đủ. |
| A03 | [SRC-ADD] | Sinh Python strategy file và bounded repair loop | `specs/strategy-authoring.md`, `specs/agent-architecture.md` | 21, 26, 28, 29, 33 | Yes | Partial | Partial | Deterministic data-only artifact, AST/preflight, tối đa 3 lần repair và published runtime đã có unit/integration evidence. Còn thiếu sandbox process/container cô lập và persisted attempt audit đầy đủ. |
| A04 | [SRC-ADD] | Backtest input: pair, range, investment, single/combined strategy | `specs/experiment.md`, `specs/backtest.md` | 16, 17, 23 | Yes | Partial | No | API validation + immutable ExperimentSnapshot test |
| A05 | [SRC-ADD] | Trade row đủ pair/time/LONG-SHORT/USD notional/prices/SL-TP/cost/spread-slippage/profit | `specs/backtest.md`, `specs/visualization.md` | 06, 23, 24 | Yes | Partial | No | Exact API/schema/UI columns; null SL/TP; gross/net reconciliation |
| A06 | [SRC-ADD] | Wins, losses, total profit, Win Rate, Max Drawdown | `specs/evaluation.md`, `specs/visualization.md` | 17, 24 | Yes | Partial | No | Metric fixture + UI contract test |
| A07 | [SRC-ADD] | Adaptive news extraction khi DOM thay đổi | `specs/news.md`, `specs/agent-architecture.md` | 13, 25, 30, 33, 38 | Yes | Yes | Yes | `tests/test_adaptive_news.py`, `tests/test_html_news.py`, `tests/test_news_sentiment.py`: quality-gate -> sanitized-document agent, exact-evidence validation, model-aware cache |
| A08 | [SRC-ADD] | Mỗi panel bootstrap 1.000 closed candles + merge provisional theo `open_time` | `specs/market-data.md` | 05, 09 | Yes | Partial | Partial | `web/lib/api.test.ts` verifies the shared 1,000-candle bootstrap request; `web/lib/market.test.ts` verifies replacement/de-dup by `open_time`. Còn thiếu browser isolation test cho panel 1–4 và live provider demo. |
| A09 | [SRC-ADD] | MA, Bollinger, SMC và strategy bổ sung | `specs/strategy-registry.md`, `specs/strategy-authoring.md` | 03, 10, 21, 22, 36 | Yes | Partial; SMC No | No | MA/BB fixtures; SMC chỉ claim khi có plugin, tests và demo evidence |
| A10 | [SRC-ADD] | Advanced LLM market analysis | `specs/agent-architecture.md` | 25, 32, 33 | Yes | Optional | No | Read-only insight, timestamp/provenance; cannot order/publish/submit candidate |
| A11 | [SRC-ADD] | Use Case cho account, market, strategy, experiment, discovery, leaderboard, news và operations | `design.md`, `specs/*.md` | 34 | Yes | Partial | No | Use-case walkthrough maps every actor action to an owned API/UI capability |
| A12 | [SRC-ADD] | Docker Compose MVP, health checks và scale path; Kubernetes optional | `design.md` §1.3, §8, §12 | 39 | Yes | Partial | No | Compose smoke test, private-network exposure check, health/readiness and worker-scale demo |
| P01 | [PD] | Go chỉ sở hữu API/edge/auth/quota/WS fan-out + Market Data | `design.md` §1.2, `go-review-checklist.md` | 02, 04, 14, 20, 33, 35, 39 | Yes | Partial | No | Architecture test chặn Go strategy/backtest/search/news/agent packages và DB grants |
| P02 | [PD] | Python `research` là single canonical domain runtime | `specs/python-research.md` | 02–04, 11, 17, 22, 25, 36–38 | Yes | Partial | No | Same StrategySpec/version for realtime/backtest; internal API contract tests |
| P03 | [PD] | `ai` internal inference only; no workflow/domain write/approve/publish | `specs/agent-architecture.md`, `specs/sentiment.md` | 02, 14, 25, 33 | Yes | Partial | No | Network/DB permission test; schema-invalid output rejected by Python |
| P04 | [PD] | Six logical agents, deterministic orchestrator, typed least-privilege tools | `specs/agent-architecture.md` | 25–33 | Yes | No | No | Role permission matrix; forbidden shell/SQL/HTTP/filesystem/publish tests |
| P05 | [PD] | DSL-backed authoring MVP; custom Python requires review/build/deploy | `specs/strategy-authoring.md` | 21, 26, 28, 29, 33 | Yes | Partial | Partial | `tests/test_authoring.py`, `tests/test_strategy_publish.py` và PostgreSQL runtime test chứng minh compile/review/hash/publish DSL; custom Python deployment và isolated sandbox còn pending. |

## Diagram mapping

- `01–24`: system/domain/runtime/reliability baseline.
- `25`: Agent Platform components.
- `26`: persisted agent-run state machine.
- `27–32`: one vertical flow for each logical agent.
- `33`: tool invocation and security boundary.
- `34`: system Use Case overview.
- `35`: C4 Level 3 for Go Edge and Market Gateway.
- `36–38`: UML class contracts for Strategy, Search and News Crawler.
- `39`: Docker Compose deployment topology and scale path.

Canonical file is `assets/diagrams/<number>-<slug>.mmd`; `.svg` and `.png` are generated outputs. Backlog delivery items must reference the IDs above and may not set `Verified=Yes` without the named artifact.
