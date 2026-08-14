package ranking

import (
	"github.com/google/uuid"
	"github.com/shopspring/decimal"
)

type ScorePolicy struct {
	Version   string                     `json:"version"`
	MinTrades int                        `json:"min_trades"`
	Weights   map[string]decimal.Decimal `json:"weights"`
}

type LeaderboardEntry struct {
	ID                 uuid.UUID       `json:"entry_id"`
	EvaluationID       uuid.UUID       `json:"evaluation_id"`
	Score              decimal.Decimal `json:"score"`
	Rank               int             `json:"rank"`
	ScorePolicyVersion string          `json:"score_policy_version"`
}

type RankingService interface {
	Rank(ScorePolicy, decimal.Decimal, int) (LeaderboardEntry, error)
}
