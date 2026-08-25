package market

import (
	"context"
	"testing"
	"time"
)

func TestWeightLimiterHonorsContext(t *testing.T) {
	limiter := newWeightLimiter(1, time.Hour)
	if err := limiter.acquire(context.Background(), 1); err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Millisecond)
	defer cancel()
	if err := limiter.acquire(ctx, 1); err == nil {
		t.Fatal("expected acquire to stop with context")
	}
}

func TestWeightLimiterReconcilesResponseUsage(t *testing.T) {
	limiter := newWeightLimiter(10, time.Minute)
	limiter.observeUsed(9)
	limiter.mu.Lock()
	remaining := limiter.tokens
	limiter.mu.Unlock()
	if remaining != 1 {
		t.Fatalf("expected one token after reconciliation, got %f", remaining)
	}
}
