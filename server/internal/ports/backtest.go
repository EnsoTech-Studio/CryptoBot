package ports

import (
	"context"

	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/backtest"
	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/market"
)

type BacktestEngine interface {
	Run(context.Context, backtest.ExperimentSnapshot, []market.Candle, []market.BBO) (backtest.Result, error)
}
