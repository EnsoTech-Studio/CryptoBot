package strategy

import (
	"encoding/json"

	"github.com/shopspring/decimal"

	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/common"
	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/indicator"
	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/market"
	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/sentiment"
)

type Params map[string]any

type Definition struct {
	StrategyID        string                    `json:"strategy_id"`
	Version           string                    `json:"version"`
	Family            string                    `json:"family,omitempty"`
	ParametersSchema  json.RawMessage           `json:"parameters_schema"`
	InputRequirements []string                  `json:"input_requirements"`
	OverlayTypes      []string                  `json:"overlay_types"`
	WarmUpCandles     func(Params) (int, error) `json:"-"`
	IsComposite       bool                      `json:"is_composite"`
	DisplayName       string                    `json:"display_name"`
	Description       string                    `json:"description"`
	CodeFingerprint   string                    `json:"code_fingerprint,omitempty"`
}

type AnalysisContext struct {
	Provider      string
	Symbol        string
	Timeframe     common.Timeframe
	Candles       market.CausalCandles
	Index         int
	Indicators    indicator.IndicatorView
	NewsSentiment *sentiment.NewsSentimentWindow
	Params        Params
}

type Signal struct {
	Action     common.Action    `json:"action"`
	Confidence *decimal.Decimal `json:"confidence,omitempty"`
	Price      *decimal.Decimal `json:"price,omitempty"`
	SignedSize *decimal.Decimal `json:"signed_size,omitempty"`
	Evidence   json.RawMessage  `json:"evidence,omitempty"`
}

type Strategy interface {
	Definition() Definition
	Analyze(AnalysisContext) (Signal, error)
}

type Reference struct {
	StrategyID string `json:"strategy_id"`
	Version    string `json:"version"`
}

type ChildSignal struct {
	Strategy Reference       `json:"strategy"`
	Signal   Signal          `json:"signal"`
	Weight   decimal.Decimal `json:"weight"`
}

type ResolvedSignal struct {
	StrategyID string
	Version    string
	Signal     Signal
	Weight     decimal.Decimal
}

type CombinationPolicy struct {
	Policy    string          `json:"policy"`
	Threshold decimal.Decimal `json:"threshold"`
	Encoding  string          `json:"encoding"`
}

type ChildDefinition struct {
	StrategyID string          `json:"strategy_id"`
	Version    string          `json:"version"`
	Parameters Params          `json:"parameters"`
	Weight     decimal.Decimal `json:"weight"`
}

type CompositeDefinition struct {
	StrategyID  string            `json:"strategy_id"`
	Version     string            `json:"version"`
	Children    []ChildDefinition `json:"children"`
	Combination CombinationPolicy `json:"combination"`
}

type CompositeSpec = CompositeDefinition

type CandidateStrategy struct {
	Definition     CompositeDefinition `json:"definition"`
	CandidateHash  string               `json:"candidate_hash"`
	GeneratedBy    string               `json:"generated_by"`
	GenerationMeta json.RawMessage      `json:"generation_meta,omitempty"`
}
