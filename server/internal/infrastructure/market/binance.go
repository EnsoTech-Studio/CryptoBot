package market

import (
	"context"

	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/common"
	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/market"
)

type BinanceProvider struct{}

func NewBinanceProvider() *BinanceProvider  { return &BinanceProvider{} }
func (*BinanceProvider) ProviderID() string { return "binance_usdm" }
func (*BinanceProvider) ListClosedCandles(context.Context, market.CandleQuery) ([]market.Candle, error) {
	return nil, common.ErrNotImplemented
}
func (*BinanceProvider) StreamKlines(context.Context, []market.StreamKey, func(market.KlineUpdate)) (market.Subscription, error) {
	return nil, common.ErrNotImplemented
}
