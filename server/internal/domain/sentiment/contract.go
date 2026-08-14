package sentiment

import (
	"time"

	"github.com/shopspring/decimal"
)

type Label string

const (
	Positive Label = "POSITIVE"
	Neutral  Label = "NEUTRAL"
	Negative Label = "NEGATIVE"
)

type Result struct {
	Label        Label           `json:"label"`
	Score        decimal.Decimal `json:"score"`
	Model        string          `json:"model"`
	ModelVersion string          `json:"model_version"`
	AnalyzedAt   time.Time       `json:"analyzed_at"`
}

type NewsSentimentWindow struct {
	WindowSec    int             `json:"window_sec"`
	AvgScore     decimal.Decimal `json:"avg_score"`
	ItemCount    int             `json:"item_count"`
	ModelVersion string          `json:"model_version"`
}
