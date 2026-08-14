package ports

import (
	"context"

	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/market"
)

type MarketDataProvider interface {
	ProviderID() string
	ListClosedCandles(context.Context, market.CandleQuery) ([]market.Candle, error)
	StreamKlines(context.Context, []market.StreamKey, func(market.KlineUpdate)) (market.Subscription, error)
}
