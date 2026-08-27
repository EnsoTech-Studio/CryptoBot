package market

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/shopspring/decimal"

	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/common"
	domainmarket "github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/market"
)

func TestListClosedCandlesNormalizesAndFiltersProvisionalRows(t *testing.T) {
	openMillis := int64(1_700_000_000_000)
	rows := [][]any{
		{openMillis, "100.0", "105.0", "99.0", "104.0", "42.5", openMillis + 59_999, "0", 7},
		{openMillis + 60_000, "104.0", "106.0", "103.0", "105.0", "12.0", openMillis + 119_999, "0", 3},
	}
	server := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		if request.URL.Path != "/fapi/v1/klines" {
			t.Fatalf("unexpected path %s", request.URL.Path)
		}
		if got := request.URL.Query().Get("symbol"); got != "BTCUSDT" {
			t.Fatalf("unexpected symbol %s", got)
		}
		writer.Header().Set("X-MBX-USED-WEIGHT-1M", "11")
		if err := json.NewEncoder(writer).Encode(rows); err != nil {
			t.Fatal(err)
		}
	}))
	defer server.Close()

	provider := NewBinanceProviderWithURLs(server.URL, "ws://unused", server.Client())
	provider.now = func() time.Time { return time.UnixMilli(openMillis + 90_000).UTC() }
	query := domainmarket.CandleQuery{
		Market: domainmarket.MarketKey{Provider: "binance_usdm", Symbol: "btcusdt", Timeframe: common.Timeframe("1m")},
		From:   time.UnixMilli(openMillis).UTC(),
		To:     time.UnixMilli(openMillis + 180_000).UTC(),
		Limit:  2,
	}
	candles, err := provider.ListClosedCandles(context.Background(), query)
	if err != nil {
		t.Fatal(err)
	}
	if len(candles) != 1 {
		t.Fatalf("expected one closed candle, got %d", len(candles))
	}
	if candles[0].Symbol != "BTCUSDT" || !candles[0].Close.Equal(decimal.RequireFromString("104.0")) {
		t.Fatalf("unexpected normalized candle: %+v", candles[0])
	}
	if candles[0].TradeCount == nil || *candles[0].TradeCount != 7 {
		t.Fatalf("unexpected trade count: %+v", candles[0].TradeCount)
	}
}

func TestBinanceProviderUsesSeparateTimeoutsForRESTAndWebSocket(t *testing.T) {
	client := &http.Client{Timeout: 17 * time.Second}
	provider := NewBinanceProviderWithURLs("http://rest.test", "ws://stream.test", client)

	if provider.restClient != client || provider.restClient.Timeout != 17*time.Second {
		t.Fatalf("REST client timeout changed: %s", provider.restClient.Timeout)
	}
	if provider.websocketClient == client {
		t.Fatal("WebSocket must not share the REST client instance")
	}
	if provider.websocketClient.Timeout != 0 {
		t.Fatalf("WebSocket client has a total timeout: %s", provider.websocketClient.Timeout)
	}
	if provider.websocketClient.Transport != client.Transport {
		t.Fatal("WebSocket client did not preserve the configured transport")
	}
}

func TestStreamMarketUsesSplitBinanceEndpoints(t *testing.T) {
	provider := newBinanceProviderWithEndpoints(
		"http://rest.test", "wss://stream.test/market/stream", "wss://stream.test/public/stream", nil,
	)
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	subscription, err := provider.StreamMarket(
		ctx,
		[]domainmarket.StreamKey{{
			Provider: "binance_usdm", Symbol: "ETHUSDT", Timeframe: common.Timeframe("1m"),
		}},
		func(domainmarket.KlineUpdate) {},
		func(domainmarket.BBO) {},
		nil,
	)
	if err != nil {
		t.Fatal(err)
	}
	defer subscription.Close()
	binanceStream := subscription.(*binanceSubscription)
	if len(binanceStream.endpoints) != 2 {
		t.Fatalf("expected market and public endpoints, got %d", len(binanceStream.endpoints))
	}
	if got := binanceStream.endpoints[0].url; got != "wss://stream.test/market/stream?streams=ethusdt@kline_1m" {
		t.Fatalf("unexpected market endpoint: %s", got)
	}
	if got := binanceStream.endpoints[1].url; got != "wss://stream.test/public/stream?streams=ethusdt@bookTicker" {
		t.Fatalf("unexpected public endpoint: %s", got)
	}
}

func TestNormalizeKlinePreservesFinalState(t *testing.T) {
	payload := []byte(`{"e":"kline","s":"BTCUSDT","k":{"t":1700000000000,"T":1700000059999,"s":"BTCUSDT","i":"1m","o":"100","c":"104","h":"105","l":"99","v":"42.5","n":7,"x":true}}`)
	update, err := normalizeKlineEvent(payload)
	if err != nil {
		t.Fatal(err)
	}
	if !update.Final || update.Market.Timeframe != common.Timeframe("1m") || update.Market.Symbol != "BTCUSDT" {
		t.Fatalf("unexpected update: %+v", update)
	}
}

func TestNormalizeBookTickerRejectsCrossedQuote(t *testing.T) {
	payload := []byte(`{"e":"bookTicker","E":1700000000000,"T":1700000000001,"s":"BTCUSDT","u":99,"b":"101","B":"2","a":"100","A":"3"}`)
	if _, err := normalizeBookTicker(payload, 1); err == nil {
		t.Fatal("expected crossed quote to fail validation")
	}
}

func TestNormalizeBookTickerCarriesOrderingEvidence(t *testing.T) {
	payload := []byte(`{"e":"bookTicker","E":1700000000000,"T":1700000000001,"s":"btcusdt","u":99,"b":"100","B":"2","a":"101","A":"3"}`)
	quote, err := normalizeBookTicker(payload, 17)
	if err != nil {
		t.Fatal(err)
	}
	if quote.Symbol != "BTCUSDT" || quote.SourceSequence != 17 || quote.UpdateID == nil || *quote.UpdateID != 99 {
		t.Fatalf("unexpected quote: %+v", quote)
	}
}

func TestHandleMessageDistinguishesEventTypeFromEventTime(t *testing.T) {
	payload := []byte(`{"stream":"ethusdt@bookTicker","data":{"e":"bookTicker","E":1700000000000,"T":1700000000001,"s":"ETHUSDT","u":99,"b":"100","B":"2","a":"101","A":"3"}}`)
	var received domainmarket.BBO
	subscription := binanceSubscription{
		publishBBO: func(quote domainmarket.BBO) { received = quote },
	}

	if err := subscription.handleMessage(payload); err != nil {
		t.Fatal(err)
	}
	if received.Symbol != "ETHUSDT" || !received.Bid.Equal(decimal.RequireFromString("100")) {
		t.Fatalf("unexpected quote: %+v", received)
	}
}

func TestHandleMessagePublishesRealisticCombinedKline(t *testing.T) {
	payload := []byte(`{"stream":"ethusdt@kline_1m","data":{"e":"kline","E":1700000000001,"s":"ETHUSDT","k":{"t":1700000000000,"T":1700000059999,"s":"ETHUSDT","i":"1m","f":100,"L":200,"o":"100","c":"104","h":"105","l":"99","v":"42.5","n":7,"x":false,"V":"21.25"}}}`)
	var received domainmarket.KlineUpdate
	subscription := binanceSubscription{
		publishKline: func(update domainmarket.KlineUpdate) { received = update },
	}

	if err := subscription.handleMessage(payload); err != nil {
		t.Fatal(err)
	}
	if received.Market.Symbol != "ETHUSDT" ||
		!received.Close.Equal(decimal.RequireFromString("104")) ||
		!received.Volume.Equal(decimal.RequireFromString("42.5")) {
		t.Fatalf("unexpected kline: %+v", received)
	}
}

func TestValidateCandleQueryBounds(t *testing.T) {
	now := time.Now().UTC()
	query := domainmarket.CandleQuery{
		Market: domainmarket.MarketKey{Provider: "binance_usdm", Symbol: "BTCUSDT", Timeframe: common.Timeframe("1m")},
		From:   now.Add(-time.Hour),
		To:     now,
		Limit:  maxDatasetCandles + 1,
	}
	if err := validateCandleQuery(query); err == nil {
		t.Fatal("expected oversized query to fail")
	}
}
