package market

import (
	"errors"
	"testing"

	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/common"
)

func TestCausalCandlesRejectFutureAccess(t *testing.T) {
	t.Parallel()
	view, err := NewCausalCandles(make([]Candle, 3), 1)
	if err != nil {
		t.Fatal(err)
	}
	if view.Len() != 2 || view.Index() != 1 {
		t.Fatalf("unexpected causal window: len=%d index=%d", view.Len(), view.Index())
	}
	if _, err := view.At(2); !errors.Is(err, common.ErrLookAhead) {
		t.Fatalf("expected look-ahead error, got %v", err)
	}
}
