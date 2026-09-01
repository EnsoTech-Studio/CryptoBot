package market

import (
	"context"
	"fmt"
	"sort"
	"strings"
	"sync"
	"time"

	domainmarket "github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/market"
)

// OKXFixtureProvider is a deterministic second-provider adapter used as a
// contract proof. It does not open a network connection or pretend to be an
// OKX production integration.
type OKXFixtureProvider struct{ candles []domainmarket.Candle }

func NewOKXFixtureProvider(candles []domainmarket.Candle) *OKXFixtureProvider {
	copyOfCandles := append([]domainmarket.Candle(nil), candles...)
	for index := range copyOfCandles {
		copyOfCandles[index].Provider = "okx_fixture"
		copyOfCandles[index].Symbol = strings.ToUpper(copyOfCandles[index].Symbol)
	}
	sort.Slice(copyOfCandles, func(left, right int) bool { return copyOfCandles[left].OpenTime.Before(copyOfCandles[right].OpenTime) })
	return &OKXFixtureProvider{candles: copyOfCandles}
}

func (*OKXFixtureProvider) ProviderID() string { return "okx_fixture" }

func (p *OKXFixtureProvider) ListClosedCandles(_ context.Context, query domainmarket.CandleQuery) ([]domainmarket.Candle, error) {
	if query.Market.Provider != p.ProviderID() || query.Limit < 1 {
		return nil, fmt.Errorf("invalid OKX fixture candle query")
	}
	result := make([]domainmarket.Candle, 0, min(query.Limit, len(p.candles)))
	for _, candle := range p.candles {
		if candle.Symbol != strings.ToUpper(query.Market.Symbol) || candle.Timeframe != query.Market.Timeframe || candle.OpenTime.Before(query.From) || !candle.OpenTime.Before(query.To) {
			continue
		}
		result = append(result, candle)
		if len(result) == query.Limit {
			break
		}
	}
	return result, nil
}

func (p *OKXFixtureProvider) StreamKlines(ctx context.Context, keys []domainmarket.StreamKey, publish func(domainmarket.KlineUpdate)) (domainmarket.Subscription, error) {
	return p.StreamMarket(ctx, keys, publish, nil, nil)
}

func (p *OKXFixtureProvider) StreamMarket(
	ctx context.Context,
	keys []domainmarket.StreamKey,
	publishKline func(domainmarket.KlineUpdate),
	_ func(domainmarket.BBO),
	publishStatus func(domainmarket.StreamStatus),
) (domainmarket.Subscription, error) {
	for _, key := range keys {
		if key.Provider != p.ProviderID() {
			return nil, fmt.Errorf("OKX fixture received key for %q", key.Provider)
		}
	}
	runtimeCtx, cancel := context.WithCancel(ctx)
	go func() {
		if publishStatus != nil {
			publishStatus(domainmarket.StreamStatus{State: domainmarket.StreamConnected, OccurredAt: time.Now().UTC()})
		}
		for _, key := range keys {
			candles, _ := p.ListClosedCandles(runtimeCtx, domainmarket.CandleQuery{Market: key, From: time.Unix(0, 0), To: time.Now().Add(24 * time.Hour), Limit: len(p.candles)})
			for _, candle := range candles {
				publishKline(domainmarket.KlineUpdate{Market: key, OpenTime: candle.OpenTime, CloseTime: candle.CloseTime, Open: candle.Open, High: candle.High, Low: candle.Low, Close: candle.Close, Volume: candle.Volume, TradeCount: candle.TradeCount, Final: true})
			}
		}
		<-runtimeCtx.Done()
	}()
	return &fixtureSubscription{cancel: cancel}, nil
}

type fixtureSubscription struct {
	cancel context.CancelFunc
	once   sync.Once
}

func (s *fixtureSubscription) Close() error {
	s.once.Do(s.cancel)
	return nil
}
