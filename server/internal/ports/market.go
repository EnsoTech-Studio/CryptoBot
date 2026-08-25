package ports

import (
	"context"
	"time"

	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/market"
)

type MarketDataProvider interface {
	ProviderID() string
	ListClosedCandles(context.Context, market.CandleQuery) ([]market.Candle, error)
	StreamKlines(context.Context, []market.StreamKey, func(market.KlineUpdate)) (market.Subscription, error)
}

type RealtimeMarketProvider interface {
	MarketDataProvider
	StreamMarket(
		context.Context,
		[]market.StreamKey,
		func(market.KlineUpdate),
		func(market.BBO),
		func(market.StreamStatus),
	) (market.Subscription, error)
}

type MarketRepository interface {
	PersistClosedCandles(context.Context, []market.Candle) error
	LoadCheckpoint(context.Context, market.MarketKey) (market.Checkpoint, error)
	MarkStreamStale(context.Context, market.MarketKey, uint64) error
	MarkStreamRecovered(context.Context, market.MarketKey, time.Time, uint64) error
	CreateDataset(context.Context, market.MarketKey, time.Time, time.Time, int, []market.BBO) (market.Dataset, error)
}
