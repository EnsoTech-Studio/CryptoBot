package ws

import (
	"encoding/json"
	"testing"
	"time"

	"github.com/shopspring/decimal"

	domainmarket "github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/market"
)

func TestPublishBBOSamplesHighFrequencyUpdatesForTheUI(t *testing.T) {
	hub := NewMemoryHub(nil)
	key := "binance_usdm|ETHUSDT|1m"
	client := &hubClient{
		id: "test", send: make(chan []byte, 4), subscriptions: map[string]struct{}{key: {}},
	}
	hub.clients[client.id] = client
	base := time.Unix(1_700_000_000, 0).UTC()
	quote := domainmarket.BBO{
		Provider: "binance_usdm", Symbol: "ETHUSDT", EventTime: base,
		Bid: decimal.NewFromInt(100), Ask: decimal.NewFromInt(101),
	}

	hub.PublishBBO(quote)
	quote.EventTime = base.Add(10 * time.Millisecond)
	hub.PublishBBO(quote)
	quote.EventTime = base.Add(100 * time.Millisecond)
	hub.PublishBBO(quote)

	first := decodeFrame(t, <-client.send)
	second := decodeFrame(t, <-client.send)
	if first["type"] != "bbo" || second["type"] != "bbo" {
		t.Fatalf("unexpected frames: %#v %#v", first, second)
	}
	select {
	case extra := <-client.send:
		t.Fatalf("unexpected unsampled BBO: %s", extra)
	default:
	}
}

func decodeFrame(t *testing.T, payload []byte) map[string]any {
	t.Helper()
	var frame map[string]any
	if err := json.Unmarshal(payload, &frame); err != nil {
		t.Fatalf("decode frame: %v", err)
	}
	return frame
}

func TestReplayReturnsOnlyMissingSequences(t *testing.T) {
	hub := NewMemoryHub(nil)
	client := &hubClient{send: make(chan []byte, 4), subscriptions: map[string]struct{}{}}
	history := []outboundFrame{
		{sequence: 10, payload: mustJSON(map[string]any{"type": "kline", "sequence": 10})},
		{sequence: 11, payload: mustJSON(map[string]any{"type": "bbo", "sequence": 11})},
	}

	hub.replay(client, "binance_usdm|ETHUSDT|5m", 10, history)
	frame := decodeFrame(t, <-client.send)
	if frame["sequence"] != float64(11) {
		t.Fatalf("expected sequence 11, got %#v", frame)
	}
	select {
	case extra := <-client.send:
		t.Fatalf("unexpected replay frame: %s", extra)
	default:
	}
}

func TestReplayRequiresRESTResyncWhenHistoryHasGap(t *testing.T) {
	hub := NewMemoryHub(nil)
	client := &hubClient{send: make(chan []byte, 2), subscriptions: map[string]struct{}{}}
	history := []outboundFrame{
		{sequence: 10, payload: mustJSON(map[string]any{"type": "kline", "sequence": 10})},
	}

	hub.replay(client, "binance_usdm|ETHUSDT|5m", 4, history)
	frame := decodeFrame(t, <-client.send)
	if frame["type"] != "resync_required" || frame["available_from"] != float64(10) {
		t.Fatalf("expected resync_required frame, got %#v", frame)
	}
}

func TestSlowClientGetsBoundedBufferResync(t *testing.T) {
	hub := NewMemoryHub(nil)
	client := &hubClient{send: make(chan []byte, 1), subscriptions: map[string]struct{}{}}
	client.send <- mustJSON(map[string]any{"type": "old"})

	hub.enqueue(client, mustJSON(map[string]any{"type": "new"}))
	frame := decodeFrame(t, <-client.send)
	if frame["type"] != "resync_required" || frame["reason"] != "client_buffer_overflow" {
		t.Fatalf("expected bounded-buffer resync, got %#v", frame)
	}
}

func TestSubscriptionKeyValidationRejectsInternalOrUnsupportedStreams(t *testing.T) {
	for _, key := range []string{
		"research|ETHUSDT|5m",
		"binance_usdm||5m",
		"binance_usdm|ETHUSDT|3m",
	} {
		if err := validatePublicKey(key); err == nil {
			t.Fatalf("expected key %q to be rejected", key)
		}
	}
}
