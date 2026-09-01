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

func TestPublishKlineProvidesSequenceForSameSequenceOverlayDelta(t *testing.T) {
	hub := NewMemoryHub(nil)
	key := "binance_usdm|ETHUSDT|5m|ma_cross@v1|sha256:test"
	client := &hubClient{id: "test", send: make(chan []byte, 2), subscriptions: map[string]struct{}{key: {}}}
	hub.clients[client.id] = client
	update := domainmarket.KlineUpdate{
		Market:   domainmarket.MarketKey{Provider: "binance_usdm", Symbol: "ETHUSDT", Timeframe: "5m"},
		OpenTime: time.Unix(1_700_000_000, 0).UTC(), CloseTime: time.Unix(1_700_000_300, 0).UTC(),
		Open: decimal.NewFromInt(100), High: decimal.NewFromInt(101), Low: decimal.NewFromInt(99),
		Close: decimal.NewFromInt(100), Volume: decimal.NewFromInt(10), Final: true,
	}

	sequences := hub.PublishKline(update)
	if sequences[key] != 1 {
		t.Fatalf("expected key sequence 1, got %#v", sequences)
	}
	hub.PublishOverlay(key, sequences[key], map[string]any{"revised_from": "2023-11-14T22:13:20Z"})

	kline := decodeFrame(t, <-client.send)
	delta := decodeFrame(t, <-client.send)
	if kline["type"] != "kline" || delta["type"] != "overlay_delta" {
		t.Fatalf("unexpected frames: %#v %#v", kline, delta)
	}
	if kline["sequence"] != float64(1) || delta["sequence"] != float64(1) {
		t.Fatalf("expected shared sequence 1: %#v %#v", kline, delta)
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

func TestReplayKeepsOverlayDeltaWithTheLastReceivedKlineSequence(t *testing.T) {
	hub := NewMemoryHub(nil)
	client := &hubClient{send: make(chan []byte, 2), subscriptions: map[string]struct{}{}}
	history := []outboundFrame{
		{sequence: 10, payload: mustJSON(map[string]any{"type": "kline", "sequence": 10})},
		{sequence: 10, payload: mustJSON(map[string]any{"type": "overlay_delta", "sequence": 10})},
	}

	hub.replay(client, "binance_usdm|ETHUSDT|5m", 10, history)
	select {
	case payload := <-client.send:
		frame := decodeFrame(t, payload)
		if frame["type"] != "overlay_delta" {
			t.Fatalf("expected same-sequence overlay delta, got %#v", frame)
		}
	case <-time.After(100 * time.Millisecond):
		t.Fatal("expected same-sequence overlay delta to be replayed")
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

func TestSubscriptionKeyValidationAllowsRegisteredExternalProviders(t *testing.T) {
	if err := validatePublicKey("okx_swap|ETHUSDT|5m|ma_cross@v1|sha256:test"); err != nil {
		t.Fatalf("expected OKX subscription key to be accepted: %v", err)
	}
}

func TestScopedStatusDoesNotCrossProviderBoundary(t *testing.T) {
	hub := NewMemoryHub(nil)
	binanceKey := "binance_usdm|ETHUSDT|5m"
	okxKey := "okx_swap|ETHUSDT|5m"
	client := &hubClient{
		id: "test", send: make(chan []byte, 2),
		subscriptions: map[string]struct{}{binanceKey: {}, okxKey: {}},
	}
	hub.clients[client.id] = client

	hub.PublishStatusForMarkets(
		domainmarket.StreamStatus{State: domainmarket.StreamRecovered, OccurredAt: time.Now().UTC()},
		[]domainmarket.StreamKey{{Provider: "okx_swap", Symbol: "ETHUSDT", Timeframe: "5m"}},
	)

	frame := decodeFrame(t, <-client.send)
	if frame["key"] != okxKey || frame["type"] != "stream_status" {
		t.Fatalf("status crossed provider boundary: %#v", frame)
	}
	select {
	case extra := <-client.send:
		t.Fatalf("unexpected extra status: %s", extra)
	default:
	}
}
