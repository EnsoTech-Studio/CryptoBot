package observability

import "context"

type Metrics interface {
	Observe(context.Context, string, float64)
	Snapshot() string
}

type NoopMetrics struct{}

func (NoopMetrics) Observe(context.Context, string, float64) {}
func (NoopMetrics) Snapshot() string                         { return "" }
