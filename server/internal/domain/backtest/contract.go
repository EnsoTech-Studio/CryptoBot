package backtest

import (
	"context"
	"encoding/json"
	"time"

	"github.com/google/uuid"
	"github.com/shopspring/decimal"

	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/common"
	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/market"
	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/strategy"
)

type RiskPolicy struct {
	StopLossPct      *decimal.Decimal `json:"stop_loss_pct,omitempty"`
	TakeProfitPct    *decimal.Decimal `json:"take_profit_pct,omitempty"`
	IntrabarPriority string           `json:"intrabar_priority"`
}

type MarketSnapshot struct {
	DatasetVersion string           `json:"dataset_version"`
	RevisionNo     int              `json:"revision_no"`
	Provider       string           `json:"provider"`
	Symbol         string           `json:"symbol"`
	Timeframe      common.Timeframe `json:"timeframe"`
	RangeFrom      time.Time        `json:"range_from"`
	RangeTo        time.Time        `json:"range_to"`
	CandleCount    int              `json:"candle_count"`
	ContentHash    string           `json:"content_hash"`
	BBOContentHash string           `json:"bbo_content_hash,omitempty"`
}

type ExperimentSnapshot struct {
	ExperimentID        uuid.UUID                 `json:"experiment_id"`
	OwnerID             uuid.UUID                 `json:"owner_id,omitempty"`
	Strategy            strategy.Reference        `json:"strategy"`
	CandidateDefinition json.RawMessage           `json:"candidate_definition"`
	CandidateHash       string                    `json:"candidate_hash"`
	Market              MarketSnapshot            `json:"market"`
	InitialEquity       decimal.Decimal           `json:"initial_equity"`
	FixedNotional       decimal.Decimal           `json:"fixed_notional"`
	Leverage            decimal.Decimal           `json:"leverage"`
	FeeBPS              int                       `json:"fee_bps"`
	SlippageBPS         int                       `json:"slippage_bps"`
	FillPolicy          common.FillPolicy         `json:"fill_policy"`
	PositionPolicy      common.PositionPolicy     `json:"position_policy"`
	OpenPositionAtEnd   common.OpenPositionPolicy `json:"open_position_at_end"`
	RiskPolicy          *RiskPolicy               `json:"risk_policy,omitempty"`
	EvaluatorVersion    string                    `json:"evaluator_version"`
	CreatedAt           time.Time                 `json:"created_at"`
}

type OrderFact struct {
	SequenceNo int              `json:"sequence_no"`
	Side       common.TradeSide `json:"side"`
	Action     common.Action    `json:"action"`
	CreatedAt  time.Time        `json:"created_at"`
	LimitPrice decimal.Decimal  `json:"limit_price"`
	Status     string           `json:"status"`
}

type TradeFact struct {
	SequenceNo   int                `json:"sequence_no"`
	Side         common.TradeSide   `json:"side"`
	SignalAt     *time.Time         `json:"signal_t,omitempty"`
	EntryTime    time.Time          `json:"entry_time"`
	EntryPrice   decimal.Decimal    `json:"entry_price"`
	ExitTime     *time.Time         `json:"exit_time,omitempty"`
	ExitPrice    *decimal.Decimal   `json:"exit_price,omitempty"`
	Quantity     decimal.Decimal    `json:"quantity"`
	FeePaid      decimal.Decimal    `json:"fee_paid"`
	SlippageCost decimal.Decimal    `json:"slippage_cost"`
	PnLAbsolute  *decimal.Decimal   `json:"pnl_absolute,omitempty"`
	PnLPercent   *decimal.Decimal   `json:"pnl_percent,omitempty"`
	ExitReason   *common.ExitReason `json:"exit_reason,omitempty"`
}

type SignalRecord struct {
	CandleTime   time.Time        `json:"candle_time"`
	Action       common.Action    `json:"action"`
	Price        *decimal.Decimal `json:"price,omitempty"`
	Notional     *decimal.Decimal `json:"notional,omitempty"`
	Confidence   *decimal.Decimal `json:"confidence,omitempty"`
	ChildSignals json.RawMessage  `json:"child_signals,omitempty"`
}

type EquityPoint struct {
	PointTime   time.Time        `json:"point_time"`
	Equity      decimal.Decimal  `json:"equity"`
	DrawdownPct *decimal.Decimal `json:"drawdown_pct,omitempty"`
}

type Result struct {
	Trades        []TradeFact    `json:"trades"`
	Signals       []SignalRecord `json:"signals"`
	Orders        []OrderFact    `json:"orders"`
	EquityPoints  []EquityPoint  `json:"equity_points"`
	CandlesRead   int            `json:"candles_read"`
	WarmUpCandles int            `json:"warm_up_candles"`
	DurationMS    int            `json:"duration_ms"`
}

type BacktestResult = Result

type BacktestEngine interface {
	Run(context.Context, ExperimentSnapshot, []market.Candle, []market.BBO) (Result, error)
}
