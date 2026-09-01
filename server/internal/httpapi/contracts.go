package httpapi

import (
	"fmt"
	"math"
	"time"
)

const (
	defaultProvider = "binance_usdm"
	defaultSymbol   = "ETHUSDT"
)

type principal struct {
	ID          string `json:"id"`
	Email       string `json:"email"`
	DisplayName string `json:"display_name"`
	Role        string `json:"role"`
}

type strategyChild struct {
	StrategyID string         `json:"strategy_id"`
	Version    string         `json:"version"`
	Parameters map[string]any `json:"parameters"`
	Weight     float64        `json:"weight"`
}

type combinationInput struct {
	Policy    string  `json:"policy"`
	Threshold float64 `json:"threshold"`
}

type experimentRequest struct {
	DatasetVersion   string           `json:"dataset_version"`
	Provider         string           `json:"provider"`
	Symbol           string           `json:"symbol"`
	Timeframe        string           `json:"timeframe"`
	StrategyID       string           `json:"strategy_id"`
	StrategyVersion  string           `json:"strategy_version"`
	Children         []strategyChild  `json:"children"`
	Combination      combinationInput `json:"combination"`
	RangeFrom        *time.Time       `json:"range_from,omitempty"`
	RangeTo          *time.Time       `json:"range_to,omitempty"`
	InitialEquity    float64          `json:"initial_equity"`
	FixedNotional    float64          `json:"fixed_notional"`
	Leverage         float64          `json:"leverage"`
	FeeBps           int              `json:"fee_bps"`
	SlippageBps      int              `json:"slippage_bps"`
	StopLossPct      *float64         `json:"stop_loss_pct,omitempty"`
	TakeProfitPct    *float64         `json:"take_profit_pct,omitempty"`
	IntrabarPriority string           `json:"intrabar_priority"`
	IdempotencyKey   string           `json:"idempotency_key,omitempty"`
}

type searchSpaceInput struct {
	StrategyIDs   []string                    `json:"strategy_ids"`
	Cardinality   []int                       `json:"cardinality"`
	Policies      []string                    `json:"policies"`
	ParameterGrid map[string]map[string][]any `json:"parameter_grid"`
}

type searchMarketInput struct {
	Provider       string    `json:"provider"`
	Symbol         string    `json:"symbol"`
	Timeframe      string    `json:"timeframe"`
	DatasetVersion string    `json:"dataset_version"`
	RangeFrom      time.Time `json:"range_from"`
	RangeTo        time.Time `json:"range_to"`
}

type searchRunRequest struct {
	GeneratorID    string            `json:"generator_id"`
	SearchSpace    searchSpaceInput  `json:"search_space"`
	StopConditions map[string]any    `json:"stop_conditions"`
	Market         searchMarketInput `json:"market"`
	Execution      experimentRequest `json:"execution"`
	Seed           int64             `json:"seed"`
	IdempotencyKey string            `json:"idempotency_key"`
}

type strategyDraftRequest struct {
	Mode   string `json:"mode"`
	Source struct {
		Type string         `json:"type"`
		Text string         `json:"text,omitempty"`
		URL  string         `json:"url,omitempty"`
		Spec map[string]any `json:"spec,omitempty"`
	} `json:"source"`
	NameHint       string `json:"name_hint,omitempty"`
	IdempotencyKey string `json:"idempotency_key,omitempty"`
}

type strategyApprovalRequest struct {
	Revision          int    `json:"revision"`
	SpecHash          string `json:"spec_hash"`
	ArtifactHash      string `json:"artifact_hash"`
	SandboxReportHash string `json:"sandbox_report_hash"`
	Decision          string `json:"decision"`
	Reason            string `json:"reason"`
	IdempotencyKey    string `json:"idempotency_key,omitempty"`
}

type strategyDraftActionRequest struct {
	Action string `json:"action"`
}

func (request *searchRunRequest) validate() error {
	if request.GeneratorID == "" {
		request.GeneratorID = "grid"
	}
	if request.GeneratorID != "grid" && request.GeneratorID != "random" &&
		request.GeneratorID != "random_search" && request.GeneratorID != "domain_guided" {
		return fmt.Errorf("unknown generator_id")
	}
	if len(request.SearchSpace.StrategyIDs) == 0 || len(request.SearchSpace.StrategyIDs) > 20 {
		return fmt.Errorf("strategy_ids must contain between 1 and 20 items")
	}
	strategies := make(map[string]struct{}, len(request.SearchSpace.StrategyIDs))
	for _, strategyID := range request.SearchSpace.StrategyIDs {
		if strategyID == "" {
			return fmt.Errorf("strategy_ids must not contain empty values")
		}
		if _, duplicate := strategies[strategyID]; duplicate {
			return fmt.Errorf("strategy_ids must be unique")
		}
		strategies[strategyID] = struct{}{}
	}
	if len(request.SearchSpace.Cardinality) == 0 {
		request.SearchSpace.Cardinality = []int{1}
	}
	for _, cardinality := range request.SearchSpace.Cardinality {
		if cardinality < 1 || cardinality > 5 || cardinality > len(strategies) {
			return fmt.Errorf("cardinality must be in [1, 5] and not exceed strategy count")
		}
	}
	if len(request.SearchSpace.Policies) == 0 {
		request.SearchSpace.Policies = []string{"weighted_vote"}
	}
	for _, policy := range request.SearchSpace.Policies {
		if policy != "weighted_vote" && policy != "majority_vote" {
			return fmt.Errorf("unknown combination policy")
		}
	}
	for strategyID := range request.SearchSpace.ParameterGrid {
		if _, exists := strategies[strategyID]; !exists {
			return fmt.Errorf("parameter_grid references an unknown strategy_id")
		}
	}
	return validateSearchStopConditions(request.StopConditions)
}

func validateSearchStopConditions(values map[string]any) error {
	if len(values) == 0 {
		return fmt.Errorf("at least one bounded stop condition is required")
	}
	known := map[string]float64{
		"max_candidates":    500,
		"max_duration_sec":  86_400,
		"max_non_improving": 500,
	}
	found := false
	for key, raw := range values {
		if key == "max_failure_rate" {
			value, ok := numberValue(raw)
			if !ok || value <= 0 || value > 1 {
				return fmt.Errorf("max_failure_rate must be a number in (0, 1]")
			}
			found = true
			continue
		}
		maximum, ok := known[key]
		if !ok {
			return fmt.Errorf("unknown stop condition %q", key)
		}
		value, ok := numberValue(raw)
		if !ok || value <= 0 || value > maximum || math.Trunc(value) != value {
			return fmt.Errorf("%s must be a positive bounded integer", key)
		}
		found = true
	}
	if !found {
		return fmt.Errorf("at least one bounded stop condition is required")
	}
	return nil
}

func numberValue(value any) (float64, bool) {
	switch number := value.(type) {
	case float64:
		return number, !math.IsNaN(number) && !math.IsInf(number, 0)
	case float32:
		return float64(number), true
	case int:
		return float64(number), true
	case int8:
		return float64(number), true
	case int16:
		return float64(number), true
	case int32:
		return float64(number), true
	case int64:
		return float64(number), true
	case uint:
		return float64(number), true
	case uint8:
		return float64(number), true
	case uint16:
		return float64(number), true
	case uint32:
		return float64(number), true
	case uint64:
		return float64(number), true
	default:
		return 0, false
	}
}
