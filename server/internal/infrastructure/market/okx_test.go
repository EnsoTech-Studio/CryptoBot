package market

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strconv"
	"testing"
	"time"

	"github.com/shopspring/decimal"

	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/common"
	domainmarket "github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/market"
)

func TestOKXListClosedCandlesNormalizesConfirmedRows(t *testing.T) {
	openMillis := int64(1_700_000_000_000)
	rows := [][]any{
		{strconvString(openMillis + 300_000), "104", "106", "103", "105", "20", "2.0", "210", "0"},
		{strconvString(openMillis), "100", "105", "99", "104", "10", "1.5", "156", "1"},
	}
	server := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		if request.URL.Path != "/api/v5/market/history-candles" {
			t.Fatalf("unexpected path %s", request.URL.Path)
		}
		if got := request.URL.Query().Get("instId"); got != "ETH-USDT-SWAP" {
			t.Fatalf("unexpected instId %s", got)
		}
		if got := request.URL.Query().Get("bar"); got != "5m" {
			t.Fatalf("unexpected bar %s", got)
		}
		if err := json.NewEncoder(writer).Encode(map[string]any{
			"code": "0", "msg": "", "data": rows,
		}); err != nil {
			t.Fatal(err)
		}
	}))
	defer server.Close()

	provider := NewOKXSwapProviderWithURLs(server.URL, "ws://unused", "ws://unused", server.Client())
	provider.now = func() time.Time { return time.UnixMilli(openMillis + 600_000).UTC() }
	candles, err := provider.ListClosedCandles(context.Background(), domainmarket.CandleQuery{
		Market: domainmarket.MarketKey{Provider: "okx_swap", Symbol: "ethusdt", Timeframe: common.Timeframe("5m")},
		From:   time.UnixMilli(openMillis).UTC(),
		To:     time.UnixMilli(openMillis + 900_000).UTC(),
		Limit:  2,
	})
	if err != nil {
		t.Fatal(err)
	}
	if len(candles) != 1 {
		t.Fatalf("expected one confirmed candle, got %d", len(candles))
	}
	if candles[0].Provider != "okx_swap" || candles[0].Symbol != "ETHUSDT" ||
		!candles[0].Close.Equal(decimal.RequireFromString("104")) ||
		!candles[0].Volume.Equal(decimal.RequireFromString("1.5")) {
		t.Fatalf("unexpected normalized candle: %+v", candles[0])
	}
}

func TestOKXStreamMarketUsesBusinessAndPublicEndpoints(t *testing.T) {
	provider := NewOKXSwapProviderWithURLs(
		"http://rest.test", "wss://stream.test/business", "wss://stream.test/public", nil,
	)
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	subscription, err := provider.StreamMarket(
		ctx,
		[]domainmarket.StreamKey{{Provider: "okx_swap", Symbol: "ETHUSDT", Timeframe: common.Timeframe("1h")}},
		func(domainmarket.KlineUpdate) {},
		func(domainmarket.BBO) {},
		nil,
	)
	if err != nil {
		t.Fatal(err)
	}
	defer subscription.Close()
	okxStream := subscription.(*okxSubscription)
	if len(okxStream.endpoints) != 2 {
		t.Fatalf("expected business and public endpoints, got %d", len(okxStream.endpoints))
	}
	if got := okxStream.endpoints[0].args[0]; got.Channel != "candle1H" || got.InstID != "ETH-USDT-SWAP" {
		t.Fatalf("unexpected candle arg: %+v", got)
	}
	if got := okxStream.endpoints[1].args[0]; got.Channel != "bbo-tbt" || got.InstID != "ETH-USDT-SWAP" {
		t.Fatalf("unexpected BBO arg: %+v", got)
	}
}

func TestOKXStreamNormalizesCandleAndBBOFrames(t *testing.T) {
	openMillis := int64(1_700_000_000_000)
	var candle domainmarket.KlineUpdate
	var quote domainmarket.BBO
	subscription := okxSubscription{
		publishKline: func(update domainmarket.KlineUpdate) { candle = update },
		publishBBO:   func(update domainmarket.BBO) { quote = update },
	}

	if err := subscription.handleMessage([]byte(`{"arg":{"channel":"candle5m","instId":"ETH-USDT-SWAP"},"data":[["1700000000000","100","105","99","104","10","1.5","156","1"]]}`)); err != nil {
		t.Fatal(err)
	}
	if candle.Market.Provider != "okx_swap" || candle.Market.Symbol != "ETHUSDT" ||
		candle.Market.Timeframe != common.Timeframe("5m") || !candle.Final ||
		!candle.Close.Equal(decimal.RequireFromString("104")) {
		t.Fatalf("unexpected OKX candle: %+v", candle)
	}
	if !candle.CloseTime.Equal(time.UnixMilli(openMillis).UTC().Add(5*time.Minute - time.Millisecond)) {
		t.Fatalf("unexpected close time: %s", candle.CloseTime)
	}

	if err := subscription.handleMessage([]byte(`{"arg":{"channel":"bbo-tbt","instId":"ETH-USDT-SWAP"},"data":[{"asks":[["105","2","0","1"]],"bids":[["104","3","0","1"]],"ts":"1700000001000","seqId":123}]}`)); err != nil {
		t.Fatal(err)
	}
	if quote.Provider != "okx_swap" || quote.Symbol != "ETHUSDT" ||
		quote.UpdateID == nil || *quote.UpdateID != 123 ||
		!quote.Bid.Equal(decimal.RequireFromString("104")) {
		t.Fatalf("unexpected OKX BBO: %+v", quote)
	}
}

func strconvString(value int64) string {
	return strconv.FormatInt(value, 10)
}
