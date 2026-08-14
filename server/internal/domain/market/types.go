package market

import (
	"time"

	"github.com/shopspring/decimal"

	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/common"
)

type MarketKey struct {
	Provider  string           `json:"provider"`
	Symbol    string           `json:"symbol"`
	Timeframe common.Timeframe `json:"timeframe"`
}

type SubscriptionKey struct {
	Market          MarketKey `json:"market"`
	StrategyID      string    `json:"strategy_id,omitempty"`
	StrategyVersion string    `json:"strategy_version,omitempty"`
	ConfigHash      string    `json:"config_hash,omitempty"`
}

type Candle struct {
	Provider   string           `json:"provider"`
	Symbol     string           `json:"symbol"`
	Timeframe  common.Timeframe `json:"timeframe"`
	OpenTime   time.Time        `json:"open_time"`
	CloseTime  time.Time        `json:"close_time"`
	Open       decimal.Decimal  `json:"open"`
	High       decimal.Decimal  `json:"high"`
	Low        decimal.Decimal  `json:"low"`
	Close      decimal.Decimal  `json:"close"`
	Volume     decimal.Decimal  `json:"volume"`
	TradeCount *int             `json:"trade_count,omitempty"`
}

type KlineUpdate struct {
	Market     MarketKey       `json:"market"`
	OpenTime   time.Time       `json:"open_time"`
	CloseTime  time.Time       `json:"close_time"`
	Open       decimal.Decimal `json:"open"`
	High       decimal.Decimal `json:"high"`
	Low        decimal.Decimal `json:"low"`
	Close      decimal.Decimal `json:"close"`
	Volume     decimal.Decimal `json:"volume"`
	TradeCount *int             `json:"trade_count,omitempty"`
	Final      bool            `json:"final"`
}

type BBO struct {
	Provider       string          `json:"provider"`
	Symbol         string          `json:"symbol"`
	EventTime      time.Time       `json:"event_time"`
	Bid            decimal.Decimal `json:"bid"`
	BidQty         decimal.Decimal `json:"bid_qty"`
	Ask            decimal.Decimal `json:"ask"`
	AskQty         decimal.Decimal `json:"ask_qty"`
	UpdateID       *uint64         `json:"update_id,omitempty"`
	SourceSequence uint64          `json:"source_sequence"`
}

type CandleQuery struct {
	Market MarketKey
	From   time.Time
	To     time.Time
	Limit  int
}

type StreamKey = MarketKey

type Subscription interface{ Close() error }

type CausalCandles struct{}

func NewCausalCandles([]Candle, int) (CausalCandles, error) {
	return CausalCandles{}, common.ErrNotImplemented
}
func (CausalCandles) At(int) (Candle, error) { return Candle{}, common.ErrNotImplemented }
func (CausalCandles) Len() int               { return 0 }
func (CausalCandles) Index() int             { return 0 }
