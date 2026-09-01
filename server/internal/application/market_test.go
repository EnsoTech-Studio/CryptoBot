package application

import (
	"context"
	"sync"
	"testing"
	"time"

	"github.com/shopspring/decimal"

	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/common"
	domainmarket "github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/market"
	"github.com/EnsoTech-Studio/CryptoBot/server/internal/ports"
)

type fakeSubscription struct{ cancel context.CancelFunc }

func (s *fakeSubscription) Close() error { s.cancel(); return nil }

type fakeMarketProvider struct {
	closed      []domainmarket.Candle
	providerID  string
	streamState domainmarket.StreamState
}

func (p *fakeMarketProvider) ProviderID() string {
	if p.providerID != "" {
		return p.providerID
	}
	return "binance_usdm"
}
func (p *fakeMarketProvider) ListClosedCandles(
	context.Context, domainmarket.CandleQuery,
) ([]domainmarket.Candle, error) {
	return append([]domainmarket.Candle(nil), p.closed...), nil
}

type fakeMarketProviderRegistry struct {
	providers map[string]ports.RealtimeMarketProvider
}

func (r fakeMarketProviderRegistry) Resolve(provider string) (ports.RealtimeMarketProvider, error) {
	return r.providers[provider], nil
}
func (p *fakeMarketProvider) StreamKlines(
	ctx context.Context, keys []domainmarket.StreamKey, publish func(domainmarket.KlineUpdate),
) (domainmarket.Subscription, error) {
	return p.StreamMarket(ctx, keys, publish, nil, nil)
}
func (p *fakeMarketProvider) StreamMarket(
	ctx context.Context,
	_keys []domainmarket.StreamKey,
	publishKline func(domainmarket.KlineUpdate),
	publishBBO func(domainmarket.BBO),
	publishStatus func(domainmarket.StreamStatus),
) (domainmarket.Subscription, error) {
	runtimeCtx, cancel := context.WithCancel(ctx)
	go func() {
		if p.streamState != "" && publishStatus != nil {
			publishStatus(domainmarket.StreamStatus{State: p.streamState, OccurredAt: time.Now()})
		}
		publishKline(domainmarket.KlineUpdate{Final: false})
		if publishBBO != nil {
			publishBBO(domainmarket.BBO{
				Provider: "binance_usdm", Symbol: "BTCUSDT", EventTime: time.Now().UTC(),
				Bid: decimal.NewFromInt(100), Ask: decimal.NewFromInt(101),
			})
		}
		<-runtimeCtx.Done()
	}()
	return &fakeSubscription{cancel: cancel}, nil
}

type fakeMarketStore struct {
	mu        sync.Mutex
	persisted int
	recovered int
	stale     int
	staleKeys []domainmarket.MarketKey
}

func (s *fakeMarketStore) PersistClosedCandles(_ context.Context, candles []domainmarket.Candle) error {
	s.mu.Lock()
	s.persisted += len(candles)
	s.mu.Unlock()
	return nil
}
func (*fakeMarketStore) LoadCheckpoint(
	_ context.Context, key domainmarket.MarketKey,
) (domainmarket.Checkpoint, error) {
	return domainmarket.Checkpoint{Market: key, IsStale: true}, nil
}
func (s *fakeMarketStore) MarkStreamStale(
	_ context.Context, key domainmarket.MarketKey, _ uint64,
) error {
	s.mu.Lock()
	s.stale++
	s.staleKeys = append(s.staleKeys, key)
	s.mu.Unlock()
	return nil
}
func (s *fakeMarketStore) MarkStreamRecovered(
	context.Context, domainmarket.MarketKey, time.Time, uint64,
) error {
	s.mu.Lock()
	s.recovered++
	s.mu.Unlock()
	return nil
}
func (*fakeMarketStore) CreateDataset(
	context.Context, domainmarket.MarketKey, time.Time, time.Time, int, []domainmarket.BBO,
) (domainmarket.Dataset, error) {
	return domainmarket.Dataset{}, nil
}

func TestMarketServiceBackfillsBeforeRecovered(t *testing.T) {
	now := time.Now().UTC().Truncate(time.Minute)
	key := domainmarket.MarketKey{
		Provider: "binance_usdm", Symbol: "BTCUSDT", Timeframe: common.Timeframe("1m"),
	}
	provider := &fakeMarketProvider{streamState: domainmarket.StreamConnected, closed: []domainmarket.Candle{{
		Provider: key.Provider, Symbol: key.Symbol, Timeframe: key.Timeframe,
		OpenTime: now.Add(-time.Minute), CloseTime: now.Add(-time.Millisecond),
		Open: decimal.NewFromInt(100), High: decimal.NewFromInt(102),
		Low: decimal.NewFromInt(99), Close: decimal.NewFromInt(101), Volume: decimal.NewFromInt(5),
	}}}
	store := &fakeMarketStore{}
	recovered := make(chan struct{}, 1)
	service, err := NewMarketService(fakeMarketProviderRegistry{providers: map[string]ports.RealtimeMarketProvider{
		key.Provider: provider,
	}}, store, []domainmarket.StreamKey{key}, MarketCallbacks{
		Status: func(status domainmarket.StreamStatus) {
			if status.State == domainmarket.StreamRecovered {
				recovered <- struct{}{}
			}
		},
	})
	if err != nil {
		t.Fatal(err)
	}
	subscription, err := service.Start(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	defer subscription.Close()
	select {
	case <-recovered:
	case <-time.After(time.Second):
		t.Fatal("market stream did not recover")
	}
	store.mu.Lock()
	persisted, recoveredCount := store.persisted, store.recovered
	store.mu.Unlock()
	if persisted != 1 || recoveredCount != 1 {
		t.Fatalf("expected backfill then recovered checkpoint, got persisted=%d recovered=%d", persisted, recoveredCount)
	}
}

func TestMarketServiceIsolatesStaleStatusToItsProviderKeys(t *testing.T) {
	binanceKey := domainmarket.MarketKey{Provider: "binance_usdm", Symbol: "BTCUSDT", Timeframe: common.Timeframe("1m")}
	okxKey := domainmarket.MarketKey{Provider: "okx_fixture", Symbol: "ETHUSDT", Timeframe: common.Timeframe("1m")}
	binance := &fakeMarketProvider{providerID: binanceKey.Provider, streamState: domainmarket.StreamStale}
	okx := &fakeMarketProvider{providerID: okxKey.Provider}
	store := &fakeMarketStore{}
	stale := make(chan struct{}, 1)
	service, err := NewMarketService(fakeMarketProviderRegistry{providers: map[string]ports.RealtimeMarketProvider{
		binanceKey.Provider: binance,
		okxKey.Provider:     okx,
	}}, store, []domainmarket.StreamKey{binanceKey, okxKey}, MarketCallbacks{
		Status: func(status domainmarket.StreamStatus) {
			if status.State == domainmarket.StreamStale {
				stale <- struct{}{}
			}
		},
	})
	if err != nil {
		t.Fatal(err)
	}
	subscription, err := service.Start(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	defer subscription.Close()
	select {
	case <-stale:
	case <-time.After(time.Second):
		t.Fatal("expected stale status from Binance provider")
	}
	store.mu.Lock()
	defer store.mu.Unlock()
	if len(store.staleKeys) != 1 || store.staleKeys[0] != binanceKey {
		t.Fatalf("stale status crossed provider boundary: %+v", store.staleKeys)
	}
}
