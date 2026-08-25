package market

import (
	"fmt"
	"time"

	"github.com/shopspring/decimal"

	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/common"
)

type MarketKey struct {
	Provider  string           `json:"provider"`
	Symbol    string           `json:"symbol"`
	Timeframe common.Timeframe `json:"timeframe"`
}

type Pair struct {
	Provider   string   `json:"provider"`
	Symbol     string   `json:"symbol"`
	BaseAsset  string   `json:"base_asset"`
	QuoteAsset string   `json:"quote_asset"`
	Timeframes []string `json:"timeframes"`
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
	TradeCount *int            `json:"trade_count,omitempty"`
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

type CausalCandles struct {
	candles []Candle
	index   int
}

type StreamState string

const (
	StreamConnecting StreamState = "connecting"
	StreamStale      StreamState = "stale"
	StreamConnected  StreamState = "connected"
	StreamRecovered  StreamState = "recovered"
)

type StreamStatus struct {
	State       StreamState `json:"state"`
	OccurredAt  time.Time   `json:"occurred_at"`
	Reason      string      `json:"reason,omitempty"`
	ReconnectNo int         `json:"reconnect_no"`
}

type Checkpoint struct {
	Market             MarketKey
	LastClosedAt       *time.Time
	LastSourceSequence *uint64
	IsStale            bool
	ReconnectCount     int
}

type Dataset struct {
	ID             string    `json:"id"`
	DatasetVersion string    `json:"dataset_version"`
	Market         MarketKey `json:"market"`
	RangeFrom      time.Time `json:"range_from"`
	RangeTo        time.Time `json:"range_to"`
	RevisionNo     int       `json:"revision_no"`
	CandleCount    int       `json:"candle_count"`
	ContentHash    string    `json:"content_hash"`
	BBOContentHash string    `json:"bbo_content_hash"`
}

func NewCausalCandles(candles []Candle, index int) (CausalCandles, error) {
	if index < 0 || index >= len(candles) {
		return CausalCandles{}, fmt.Errorf("causal cursor %d outside candles [0,%d]", index, len(candles)-1)
	}
	return CausalCandles{candles: candles, index: index}, nil
}
func (c CausalCandles) At(index int) (Candle, error) {
	if index < 0 || index > c.index {
		return Candle{}, fmt.Errorf("%w: candle index %d outside causal window [0,%d]", common.ErrLookAhead, index, c.index)
	}
	return c.candles[index], nil
}
func (c CausalCandles) Len() int   { return c.index + 1 }
func (c CausalCandles) Index() int { return c.index }
