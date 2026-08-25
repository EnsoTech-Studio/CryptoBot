package market

import (
	"context"
	"fmt"
	"sync"
	"time"
)

type weightLimiter struct {
	mu       sync.Mutex
	capacity float64
	tokens   float64
	period   time.Duration
	last     time.Time
}

func newWeightLimiter(capacity int, period time.Duration) *weightLimiter {
	return &weightLimiter{
		capacity: float64(capacity),
		tokens:   float64(capacity),
		period:   period,
		last:     time.Now(),
	}
}

func (l *weightLimiter) acquire(ctx context.Context, weight int) error {
	if weight <= 0 || float64(weight) > l.capacity {
		return fmt.Errorf("invalid request weight %d", weight)
	}
	for {
		l.mu.Lock()
		now := time.Now()
		elapsed := now.Sub(l.last)
		l.tokens = min(l.capacity, l.tokens+elapsed.Seconds()*l.capacity/l.period.Seconds())
		l.last = now
		if l.tokens >= float64(weight) {
			l.tokens -= float64(weight)
			l.mu.Unlock()
			return nil
		}
		missing := float64(weight) - l.tokens
		wait := time.Duration(missing / l.capacity * float64(l.period))
		l.mu.Unlock()
		timer := time.NewTimer(max(wait, time.Millisecond))
		select {
		case <-ctx.Done():
			timer.Stop()
			return ctx.Err()
		case <-timer.C:
		}
	}
}

func (l *weightLimiter) observeUsed(used int) {
	l.mu.Lock()
	defer l.mu.Unlock()
	remaining := l.capacity - float64(used)
	if remaining < l.tokens {
		l.tokens = max(0, remaining)
	}
}
