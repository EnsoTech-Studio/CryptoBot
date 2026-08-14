package search

import (
	"context"
	"encoding/json"

	"github.com/shopspring/decimal"

	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/strategy"
)

type SearchSpace struct {
	StrategyIDs   []string                    `json:"strategy_ids"`
	ParameterGrid map[string]map[string][]any `json:"parameter_grid"`
	Cardinality   [2]int                      `json:"cardinality"`
	Policies      []string                    `json:"policies"`
	WeightOptions []decimal.Decimal           `json:"weight_options"`
}

type ScoredCandidate struct {
	Candidate strategy.CandidateStrategy
	Score     decimal.Decimal
}

type HashSet interface {
	Has(string) bool
	Add(string)
}

type SearchHistory struct {
	TestedHashes      HashSet
	TopK              []ScoredCandidate
	BestScore         *decimal.Decimal
	NonImprovingCount int
}

type History = SearchHistory

type CandidateGenerator interface {
	GeneratorID() string
	GeneratorVersion() string
	Generate(context.Context, SearchSpace, int, *int64, SearchHistory) ([]strategy.CandidateStrategy, error)
}

type StopConditions struct {
	MaxCandidates   *int             `json:"max_candidates,omitempty"`
	MaxDurationSec  *int             `json:"max_duration_sec,omitempty"`
	MaxNonImproving *int             `json:"max_non_improving,omitempty"`
	MaxFailureRate  *decimal.Decimal `json:"max_failure_rate,omitempty"`
}

type SearchRun struct {
	GeneratorID      string          `json:"generator_id"`
	GeneratorVersion string          `json:"generator_version"`
	StopConditions   StopConditions  `json:"stop_conditions"`
	Seed             *int64          `json:"seed,omitempty"`
	ExecutionConfig  json.RawMessage `json:"execution_config"`
}
