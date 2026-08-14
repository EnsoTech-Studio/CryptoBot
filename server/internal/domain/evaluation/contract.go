package evaluation

import (
	"context"

	"github.com/google/uuid"
	"github.com/shopspring/decimal"

	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/backtest"
)

type EvaluationInput struct {
	RunID         uuid.UUID
	InitialEquity decimal.Decimal
	Trades        []backtest.TradeFact
	EquityPoints  []backtest.EquityPoint
}

type EvaluationPolicy struct {
	EvaluatorVersion    string
	PeriodsPerYear      int
	ZeroPnLCountsAsWin  bool
	StddevDDOF          int
	MinPeriodsForSharpe int
	RiskFreeRate        decimal.Decimal
}

type Evaluation struct {
	BacktestRunID    uuid.UUID        `json:"backtest_run_id"`
	EvaluatorVersion string           `json:"evaluator_version"`
	TotalReturnPct   decimal.Decimal  `json:"total_return_pct"`
	WinRatePct       decimal.Decimal  `json:"win_rate_pct"`
	MaxDrawdownPct   decimal.Decimal  `json:"max_drawdown_pct"`
	TradeCount       int              `json:"trade_count"`
	OpenTradeCount   int              `json:"open_trade_count"`
	ProfitFactor     *decimal.Decimal `json:"profit_factor,omitempty"`
	SharpeRatio      *decimal.Decimal `json:"sharpe_ratio,omitempty"`
	AvgTradePct      *decimal.Decimal `json:"avg_trade_pct,omitempty"`
}

type Evaluator interface {
	Evaluate(context.Context, EvaluationInput, EvaluationPolicy) (Evaluation, error)
}
