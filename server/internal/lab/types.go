package lab

import "time"

const (
	ProviderBinance = "binance_usdm"
	SymbolETHUSDT   = "ETHUSDT"
)

type Principal struct {
	ID          string `json:"id"`
	Email       string `json:"email"`
	DisplayName string `json:"display_name"`
	Role        string `json:"role"`
}

type MarketPair struct {
	Provider   string   `json:"provider"`
	Symbol     string   `json:"symbol"`
	BaseAsset  string   `json:"base_asset"`
	QuoteAsset string   `json:"quote_asset"`
	Timeframes []string `json:"timeframes"`
}

type Candle struct {
	Provider   string    `json:"provider"`
	Symbol     string    `json:"symbol"`
	Timeframe  string    `json:"timeframe"`
	OpenTime   time.Time `json:"open_time"`
	CloseTime  time.Time `json:"close_time"`
	Open       float64   `json:"open"`
	High       float64   `json:"high"`
	Low        float64   `json:"low"`
	Close      float64   `json:"close"`
	Volume     float64   `json:"volume"`
	TradeCount int       `json:"trade_count"`
}

type OverlayPoint struct {
	T time.Time `json:"t"`
	V *float64  `json:"v"`
}

type OverlaySeries struct {
	Name        string             `json:"name"`
	OverlayType string             `json:"overlay_type"`
	Pane        string             `json:"pane"`
	Unit        string             `json:"unit,omitempty"`
	Scale       map[string]float64 `json:"scale,omitempty"`
	Points      []OverlayPoint     `json:"points,omitempty"`
	Band        *OverlayBand       `json:"band,omitempty"`
	Zones       []OverlayZone      `json:"zones,omitempty"`
	Constant    *float64           `json:"constant,omitempty"`
	Style       string             `json:"style,omitempty"`
}

type OverlayBand struct {
	Upper  []OverlayPoint `json:"upper"`
	Middle []OverlayPoint `json:"middle"`
	Lower  []OverlayPoint `json:"lower"`
}

type OverlayZone struct {
	From      time.Time `json:"from"`
	To        time.Time `json:"to"`
	PriceLow  float64   `json:"price_low"`
	PriceHigh float64   `json:"price_high"`
}

type OverlayMarker struct {
	T           time.Time      `json:"t"`
	OverlayType string         `json:"overlay_type"`
	Confidence  *float64       `json:"confidence"`
	Evidence    map[string]any `json:"evidence"`
}

type StrategyDefinition struct {
	StrategyID        string         `json:"strategy_id"`
	Version           string         `json:"version"`
	Family            string         `json:"family,omitempty"`
	DisplayName       string         `json:"display_name"`
	Description       string         `json:"description"`
	ParametersSchema  map[string]any `json:"parameters_schema"`
	InputRequirements []string       `json:"input_requirements"`
	OverlayTypes      []string       `json:"overlay_types"`
	WarmUpCandles     int            `json:"warm_up_candles"`
	IsComposite       bool           `json:"is_composite"`
	CodeFingerprint   string         `json:"code_fingerprint"`
}

type ExperimentRequest struct {
	Provider           string           `json:"provider"`
	Symbol             string           `json:"symbol"`
	Timeframe          string           `json:"timeframe"`
	StrategyID         string           `json:"strategy_id"`
	StrategyVersion    string           `json:"strategy_version"`
	Children           []StrategyChild  `json:"children"`
	Combination        CombinationInput `json:"combination"`
	RangeFrom          *time.Time       `json:"range_from,omitempty"`
	RangeTo            *time.Time       `json:"range_to,omitempty"`
	InitialEquity      float64          `json:"initial_equity"`
	FixedNotional      float64          `json:"fixed_notional"`
	Leverage           float64          `json:"leverage"`
	FeeBps             int              `json:"fee_bps"`
	SlippageBps        int              `json:"slippage_bps"`
	StopLossPct        *float64         `json:"stop_loss_pct,omitempty"`
	TakeProfitPct      *float64         `json:"take_profit_pct,omitempty"`
	IntrabarPriority   string           `json:"intrabar_priority"`
	IdempotencyKey     string           `json:"idempotency_key,omitempty"`
	SearchRunID        string           `json:"-"`
	GeneratedBy        string           `json:"-"`
	GenerationMetaJSON string           `json:"-"`
}

type StrategyChild struct {
	StrategyID string         `json:"strategy_id"`
	Version    string         `json:"version"`
	Parameters map[string]any `json:"parameters"`
	Weight     float64        `json:"weight"`
}

type CombinationInput struct {
	Policy    string  `json:"policy"`
	Threshold float64 `json:"threshold"`
	Encoding  string  `json:"encoding"`
}

type AcceptedRun struct {
	RunID        string `json:"run_id"`
	ExperimentID string `json:"experiment_id"`
	Status       string `json:"status"`
	Reused       bool   `json:"reused"`
}

type Trade struct {
	ID          string    `json:"id"`
	SequenceNo  int       `json:"sequence_no"`
	Side        string    `json:"side"`
	EntryTime   time.Time `json:"entry_time"`
	ExitTime    time.Time `json:"exit_time"`
	EntryPrice  float64   `json:"entry_price"`
	ExitPrice   float64   `json:"exit_price"`
	Quantity    float64   `json:"quantity"`
	PnL          float64   `json:"pnl"`
	PnLPct       float64   `json:"pnl_pct"`
	ExitReason  string    `json:"exit_reason"`
	SignalT     time.Time `json:"signal_t"`
	ChildSignals map[string]any `json:"child_signals,omitempty"`
}

type EquityPoint struct {
	T      time.Time `json:"t"`
	Equity float64   `json:"equity"`
	DrawdownPct float64 `json:"drawdown_pct"`
}

type Metrics struct {
	TotalReturnPct float64 `json:"total_return_pct"`
	WinRatePct     float64 `json:"win_rate_pct"`
	MaxDrawdownPct float64 `json:"max_drawdown_pct"`
	TradeCount     int     `json:"trade_count"`
	ProfitFactor   float64 `json:"profit_factor"`
	SharpeRatio    float64 `json:"sharpe_ratio"`
	Score          float64 `json:"score"`
	EvaluatorVersion string `json:"evaluator_version"`
}

type ExperimentSummary struct {
	ID              string          `json:"id"`
	RunID           string          `json:"run_id"`
	Status          string          `json:"status"`
	Provider        string          `json:"provider"`
	Symbol          string          `json:"symbol"`
	Timeframe       string          `json:"timeframe"`
	StrategyID      string          `json:"strategy_id"`
	StrategyVersion string          `json:"strategy_version"`
	CandidateHash   string          `json:"candidate_hash"`
	DatasetVersion  string          `json:"dataset_version"`
	ContentHash     string          `json:"content_hash"`
	CreatedAt       time.Time       `json:"created_at"`
	StartedAt       *time.Time      `json:"started_at,omitempty"`
	FinishedAt      *time.Time      `json:"finished_at,omitempty"`
	CandlesRead     int             `json:"candles_read"`
	SignalsCount    int             `json:"signals_count"`
	Metrics          *Metrics        `json:"metrics"`
	Execution        map[string]any  `json:"execution"`
	CandidateDefinition map[string]any `json:"candidate_definition"`
	ErrorCode       *string         `json:"error_code,omitempty"`
}

type LeaderboardEntry struct {
	ID              string    `json:"id"`
	Rank            int       `json:"rank"`
	Score           float64   `json:"score"`
	StrategyID      string    `json:"strategy_id"`
	StrategyVersion string    `json:"strategy_version"`
	CandidateHash   string    `json:"candidate_hash"`
	DatasetVersion  string    `json:"dataset_version"`
	TotalReturnPct  float64   `json:"total_return_pct"`
	WinRatePct      float64   `json:"win_rate_pct"`
	MaxDrawdownPct  float64   `json:"max_drawdown_pct"`
	SharpeRatio     float64   `json:"sharpe_ratio"`
	TradeCount      int       `json:"trade_count"`
	ObservedAt      time.Time `json:"observed_at"`
}

type SearchRunRequest struct {
	GeneratorID    string           `json:"generator_id"`
	SearchSpace    SearchSpaceInput `json:"search_space"`
	StopConditions map[string]any    `json:"stop_conditions"`
	Market         SearchMarketInput `json:"market"`
	Execution      ExperimentRequest `json:"execution"`
	Seed           int64             `json:"seed"`
	IdempotencyKey string            `json:"idempotency_key"`
}

type SearchSpaceInput struct {
	StrategyIDs    []string                       `json:"strategy_ids"`
	Cardinality    []int                          `json:"cardinality"`
	Policies       []string                       `json:"policies"`
	ParameterGrid  map[string]map[string][]any    `json:"parameter_grid"`
}

type SearchMarketInput struct {
	Provider  string    `json:"provider"`
	Symbol    string    `json:"symbol"`
	Timeframe string    `json:"timeframe"`
	RangeFrom time.Time `json:"range_from"`
	RangeTo   time.Time `json:"range_to"`
}

type NewsItem struct {
	ID           string         `json:"id"`
	Title        string         `json:"title"`
	URL          string         `json:"url"`
	PublishedAt  time.Time      `json:"published_at"`
	Source       map[string]any `json:"source"`
	RelatedCoins []string       `json:"related_coins"`
	Sentiment    *SentimentResult `json:"sentiment"`
}

type SentimentResult struct {
	Label        string    `json:"label"`
	Score        float64   `json:"score"`
	Model        string    `json:"model"`
	ModelVersion string    `json:"model_version"`
	AnalyzedAt   time.Time `json:"analyzed_at"`
}

