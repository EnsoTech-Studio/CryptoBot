package common

import (
	"errors"

	"github.com/google/uuid"
	"github.com/shopspring/decimal"
)

type ID = uuid.UUID
type Decimal = decimal.Decimal

type Timeframe string

const (
	Timeframe1m  Timeframe = "1m"
	Timeframe5m  Timeframe = "5m"
	Timeframe15m Timeframe = "15m"
	Timeframe30m Timeframe = "30m"
	Timeframe1h  Timeframe = "1h"
	Timeframe2h  Timeframe = "2h"
	Timeframe4h  Timeframe = "4h"
	Timeframe1d  Timeframe = "1d"
)

type Action string

const (
	ActionBuy  Action = "BUY"
	ActionSell Action = "SELL"
	ActionHold Action = "HOLD"
)

type SignalType string
type TradeSide string
type RunStatus string
type JobStatus string
type SentimentLabel string
type FillPolicy string
type PositionPolicy string
type OpenPositionPolicy string
type ExitReason string

const (
	TradeSideLong                 TradeSide          = "LONG"
	TradeSideShort                TradeSide          = "SHORT"
	RunQueued                     RunStatus          = "queued"
	RunRunning                    RunStatus          = "running"
	RunCompleted                  RunStatus          = "completed"
	RunFailed                     RunStatus          = "failed"
	RunCancelled                  RunStatus          = "cancelled"
	JobQueued                     JobStatus          = "queued"
	JobLeased                     JobStatus          = "leased"
	JobCompleted                  JobStatus          = "completed"
	JobFailed                     JobStatus          = "failed"
	JobCancelled                  JobStatus          = "cancelled"
	SentimentPositive             SentimentLabel     = "POSITIVE"
	SentimentNeutral              SentimentLabel     = "NEUTRAL"
	SentimentNegative             SentimentLabel     = "NEGATIVE"
	FillPolicyBBOLimit            FillPolicy         = "bbo_limit"
	PositionPolicyOneNet          PositionPolicy     = "one_net_position"
	OpenPositionLastExecutableBBO OpenPositionPolicy = "last_executable_bbo"
	OpenPositionDiscard           OpenPositionPolicy = "discard_open_trade"
	OpenPositionMarkUnrealized    OpenPositionPolicy = "mark_unrealized"
	ExitSignal                    ExitReason         = "signal"
	ExitStopLoss                  ExitReason         = "stop_loss"
	ExitTakeProfit                ExitReason         = "take_profit"
	ExitEndOfSample               ExitReason         = "end_of_sample"
)

var (
	ErrValidation          = errors.New("validation error")
	ErrUnknownStrategy     = errors.New("unknown strategy")
	ErrLookAhead           = errors.New("look-ahead access")
	ErrProviderUnavailable = errors.New("provider unavailable")
	ErrOwnership           = errors.New("ownership denied")
	ErrQuota               = errors.New("quota exceeded")
	ErrNotImplemented      = errors.New("not implemented")
	ErrLeaseLost           = errors.New("lease lost")
)

type DomainError struct {
	Code    string
	Message string
	Field   string
	Cause   error
}

func (e *DomainError) Error() string { return e.Message }
func (e *DomainError) Unwrap() error { return e.Cause }
