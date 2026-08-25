package lab

import (
	"testing"
	"time"
)

func TestChartOverlaysReturnsEmptyMarkersSlice(t *testing.T) {
	_, markers := ChartOverlays([]Candle{{OpenTime: time.Now().UTC()}}, "composite")
	if markers == nil {
		t.Fatal("expected an empty markers slice, not nil")
	}
	if len(markers) != 0 {
		t.Fatalf("expected no markers, got %d", len(markers))
	}
}
