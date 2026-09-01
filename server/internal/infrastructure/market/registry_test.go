package market

import (
	"context"
	"testing"
	"time"

	"github.com/shopspring/decimal"

	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/common"
	domainmarket "github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/market"
)

func TestProviderRegistryResolvesSecondFixtureThroughTheCanonicalPort(t *testing.T) {
	now := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	fixture := NewOKXFixtureProvider([]domainmarket.Candle{{
		Provider: "okx_fixture", Symbol: "ETHUSDT", Timeframe: common.Timeframe("5m"),
		OpenTime: now, CloseTime: now.Add(5*time.Minute - time.Millisecond),
		Open: decimal.NewFromInt(100), High: decimal.NewFromInt(102),
		Low: decimal.NewFromInt(99), Close: decimal.NewFromInt(101), Volume: decimal.NewFromInt(12),
	}})
	registry, err := NewProviderRegistry(fixture)
	if err != nil {
		t.Fatal(err)
	}

	provider, err := registry.Resolve("okx_fixture")
	if err != nil {
		t.Fatal(err)
	}
	candles, err := provider.ListClosedCandles(context.Background(), domainmarket.CandleQuery{
		Market: domainmarket.MarketKey{Provider: "okx_fixture", Symbol: "ETHUSDT", Timeframe: common.Timeframe("5m")},
		From:   now, To: now.Add(5 * time.Minute), Limit: 10,
	})
	if err != nil {
		t.Fatal(err)
	}
	if len(candles) != 1 || candles[0].Provider != "okx_fixture" || candles[0].Symbol != "ETHUSDT" {
		t.Fatalf("fixture escaped the canonical Candle contract: %+v", candles)
	}
}
