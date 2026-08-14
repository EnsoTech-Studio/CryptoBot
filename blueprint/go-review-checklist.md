# Quick Reference Checklist
Use this checklist as a quick reference during code review. 

# Blueprint Handoff Gates

The active implementation contracts are the Go domain contracts in
`specs/market-data.md`, `specs/strategy-registry.md`, `specs/backtest.md`,
`specs/evaluation.md`, and `specs/experiment.md`.

- Marketdata: canonical `Candle` is closed and keyed by `(provider,symbol,timeframe,open_time)`; `KlineUpdate` stays provisional; BBO uses optional live `updateID` and fixture `sourceSequence`.
- Strategy: `StrategyRegistry` resolves `(strategy_id,version)`; `AnalysisContext` has causal candles/indicators and no DB/network; plugin code is trusted compiled Go.
- Backtest: merge BBO before `CandleClosed`; LIMIT BUY crosses ask, LIMIT SELL crosses bid; one net LONG/SHORT; fixed `10 USDT`, initial `100 USDT`, leverage `1x`.
- Persistence: Go owns migrations, repositories, `api_reader`/`read.*` projections, dataset snapshots and transactional outbox; Python is sentiment inference only.
- Fixture: verify `blueprint/verification/sol-2026-03-04-ma20-50.md`; never commit guessed PnL or result hashes.

# Concurrency & Synchronization

Goroutines have clear lifecycle and termination paths
Shared state protected by sync.Mutex or sync.RWMutex
Channels closed by sender, never by receiver
Select statements have default case or timeout to prevent deadlocks
sync.WaitGroup used for goroutine coordination, not sleep statements
Context passed as first parameter: func Process(ctx context.Context, ...)
Context cancellation checked in loops: case <-ctx.Done():
No data races detected by go run -race

# Error Handling

Errors checked immediately after function calls, not deferred
Error wrapping uses fmt.Errorf with %w verb: fmt.Errorf("failed: %w", err)
Sentinel errors defined as package-level variables: var ErrNotFound = errors.New("not found")
Custom error types implement Error() string method
Functions return errors as last return value
panic only used for truly unrecoverable errors
recover only in deferred functions at package boundaries
Error messages lowercase, no punctuation: errors.New("connection failed")
Idiomatic Go Patterns

Receiver names consistent and short (1-2 letters): func (u *User) Save()
Pointer receivers for methods that modify state or large structs
Interface definitions small and focused (1-3 methods)
Interfaces defined by consumer, not producer
Zero values are useful: structs work without explicit initialization
defer used for cleanup: defer file.Close()
Variable names short in small scopes, descriptive in larger scopes
Early returns reduce nesting: avoid else after if err != nil { return err }

# Memory & Resource Management

defer statements close resources: files, connections, locks
Contexts with deadlines prevent resource leaks: ctx, cancel := context.WithTimeout()
Defer cancel() immediately after creating contexts
Slices pre-allocated when size known: make([]int, 0, expectedSize)
Maps not accessed concurrently without synchronization
Pointer usage intentional: use pointers for large structs or when sharing
Nil pointer checks before dereferencing
String concatenation in loops uses strings.Builder

# Testing & Tooling

Table-driven tests for multiple similar cases
Test names describe scenario: TestUserSave_WithInvalidEmail_ReturnsError
Subtests use t.Run() for grouping
Tests clean up resources with t.Cleanup()
Benchmarks exist for performance-critical code
go vet passes without warnings
golangci-lint configured and passing
Test coverage focused on critical paths, not 100% coverage

# Package Organization

Package names lowercase, single word, no underscores: package user
main package minimal, delegates to library packages
Internal packages (internal/) for unexported code
Exported names start with uppercase: type User struct
Package-level documentation on package declaration: // Package user handles...
No circular dependencies between packages
Test files in same package: package user not package user_test (except for integration tests)
