package httpapi

import (
	"testing"
	"time"

	domainmarket "github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/market"
)

func TestMarketCheckpointStaleUsesCheckpointAndCandleAge(t *testing.T) {
	now := time.Date(2026, time.August, 27, 9, 0, 0, 0, time.UTC)
	recent := now.Add(-2 * time.Minute)
	old := now.Add(-4 * time.Minute)

	cases := []struct {
		name       string
		checkpoint domainmarket.Checkpoint
		want       bool
	}{
		{name: "recent candle", checkpoint: domainmarket.Checkpoint{LastClosedAt: &recent}, want: false},
		{name: "old candle despite recovered flag", checkpoint: domainmarket.Checkpoint{LastClosedAt: &old}, want: true},
		{name: "explicit stale flag", checkpoint: domainmarket.Checkpoint{LastClosedAt: &recent, IsStale: true}, want: true},
		{name: "missing candle", checkpoint: domainmarket.Checkpoint{}, want: true},
	}

	for _, testCase := range cases {
		t.Run(testCase.name, func(t *testing.T) {
			if got := marketCheckpointStale(testCase.checkpoint, "1m", now); got != testCase.want {
				t.Fatalf("marketCheckpointStale() = %v, want %v", got, testCase.want)
			}
		})
	}
}
