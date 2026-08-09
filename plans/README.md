# Crypto Strategy Lab -- Architecture Blueprint

These documents turn the final-project brief into an implementation-ready architecture. They intentionally prioritize **changeability, reproducible experiments, and observable asynchronous work** over a needlessly large microservice estate.

## Reading order

1. [Requirements and scope](01-requirements-and-scope.md) -- what the brief requires, MVP boundary, and acceptance criteria.
2. [Target architecture](02-target-architecture.md) -- C4-style context, containers, modules, and extension seams.
3. [Domain contracts](03-domain-contracts.md) -- core vocabulary, stable interfaces, API/resource shapes, and versioning rules.
4. [Runtime flows](04-runtime-flows.md) -- realtime, backtest/search, news/sentiment, and failure handling flows.
5. [Data and operations](05-data-and-operational-design.md) -- persistence model, deployment, reliability, security, observability, and scale path.
6. [Architecture decisions and roadmap](06-decisions-and-roadmap.md) -- ADRs, delivery phases, demonstrations, and traceability.
7. [Readable HTML overview](architecture-overview.html) -- a foldable, presentation-friendly summary.

## Scope rule

The MVP is a **simulated research platform**, never a live-trading system. It connects to Binance only through an adapter; it does not hold exchange credentials or place orders. Queue, worker, cache, and extra providers are introduced only when the workload demonstrates the need.

## Source

All course-specific requirements in this folder are traced to `Crypto Strategy Lab – Đồ án cuối kỳ.pdf`, especially pp. 2, 6--8, 12--25, 31--54.
