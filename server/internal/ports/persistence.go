package ports

import (
	"context"
	"time"

	"github.com/google/uuid"

	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/backtest"
	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/evaluation"
	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/market"
	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/news"
	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/ranking"
	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/search"
)

type CandleReader interface {
	ListClosedCandles(context.Context, market.CandleQuery) ([]market.Candle, error)
}

type CandleWriter interface {
	UpsertClosedCandles(context.Context, []market.Candle) error
}

type DatasetReader interface {
	LoadDatasetCandles(context.Context, uuid.UUID) ([]market.Candle, error)
}

type ExperimentRepository interface {
	CreateSnapshot(context.Context, backtest.ExperimentSnapshot) error
	GetSnapshot(context.Context, uuid.UUID) (backtest.ExperimentSnapshot, error)
}

type RunRepository interface {
	PersistResult(context.Context, uuid.UUID, backtest.Result) error
	OwnsRun(context.Context, uuid.UUID, uuid.UUID) (bool, error)
}

type SearchRunRepository interface {
	Create(context.Context, search.SearchRun) error
	Get(context.Context, uuid.UUID) (search.SearchRun, error)
	ApplyAction(context.Context, uuid.UUID, string, uuid.UUID) error
}

type TradeReader interface {
	ListTrades(context.Context, uuid.UUID, int, int) ([]backtest.TradeFact, error)
}

type EquityReader interface {
	ListEquity(context.Context, uuid.UUID, int) ([]backtest.EquityPoint, error)
}

type EvaluationReader interface {
	GetEvaluation(context.Context, uuid.UUID, string) (evaluation.Evaluation, error)
}

type LeaderboardRepository interface {
	List(context.Context, string, string, int) ([]ranking.LeaderboardEntry, error)
	Insert(context.Context, ranking.LeaderboardEntry) error
}

type NewsRepository interface {
	ListSources(context.Context) ([]news.ApprovedSource, error)
	InsertItems(context.Context, []news.Item) ([]news.Item, error)
}

type EventStore interface {
	Append(context.Context, []byte) error
	ClaimForConsumer(context.Context, uuid.UUID, string) (bool, error)
}

type TransactionBoundary interface {
	WithinTransaction(context.Context, func(context.Context) error) error
}

type ReadinessChecker interface {
	Ready(context.Context) error
}

type Clock interface{ Now() time.Time }
