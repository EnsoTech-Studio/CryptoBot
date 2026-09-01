package application

import (
	"context"
	"fmt"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	domainmarket "github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/market"
	"github.com/EnsoTech-Studio/CryptoBot/server/internal/ports"
)

type MarketCallbacks struct {
	Kline  func(domainmarket.KlineUpdate)
	BBO    func(domainmarket.BBO)
	Status func(domainmarket.StreamStatus)
}

type providerStatusUpdate struct {
	status domainmarket.StreamStatus
	keys   []domainmarket.StreamKey
}

type MarketService struct {
	providers ports.RealtimeMarketProviderRegistry
	store     ports.MarketRepository
	keys      []domainmarket.StreamKey
	callback  MarketCallbacks
	sequence  atomic.Uint64

	mu          sync.RWMutex
	quoteLimit  int
	quoteByPair map[string][]domainmarket.BBO
}

func NewMarketService(
	providers ports.RealtimeMarketProviderRegistry,
	store ports.MarketRepository,
	keys []domainmarket.StreamKey,
	callback MarketCallbacks,
) (*MarketService, error) {
	if providers == nil || store == nil || len(keys) == 0 || len(keys) > 512 {
		return nil, fmt.Errorf("market service requires provider, store, and 1..512 keys")
	}
	return &MarketService{
		providers: providers, store: store, keys: append([]domainmarket.StreamKey(nil), keys...),
		callback: callback, quoteLimit: 200_000, quoteByPair: make(map[string][]domainmarket.BBO),
	}, nil
}

func (s *MarketService) Start(ctx context.Context) (domainmarket.Subscription, error) {
	updates := make(chan domainmarket.KlineUpdate, 2_048)
	quotes := make(chan domainmarket.BBO, 8_192)
	statuses := make(chan providerStatusUpdate, 64)
	runtimeCtx, cancel := context.WithCancel(ctx)
	keysByProvider := make(map[string][]domainmarket.StreamKey)
	for _, key := range s.keys {
		keysByProvider[key.Provider] = append(keysByProvider[key.Provider], key)
	}
	providerSubscriptions := make([]domainmarket.Subscription, 0, len(keysByProvider))
	for providerID, providerKeys := range keysByProvider {
		providerKeys = append([]domainmarket.StreamKey(nil), providerKeys...)
		provider, err := s.providers.Resolve(providerID)
		if err != nil || provider == nil {
			cancel()
			return nil, fmt.Errorf("resolve market provider %q: %w", providerID, err)
		}
		providerSubscription, err := provider.StreamMarket(
			runtimeCtx,
			providerKeys,
			func(update domainmarket.KlineUpdate) {
				select {
				case updates <- update:
				default:
					s.publishStatus(domainmarket.StreamStatus{
						State: domainmarket.StreamStale, OccurredAt: time.Now().UTC(),
						Reason: "kline_buffer_overflow",
					})
				}
			},
			func(quote domainmarket.BBO) {
				select {
				case quotes <- quote:
				default:
					s.publishStatus(domainmarket.StreamStatus{
						State: domainmarket.StreamStale, OccurredAt: time.Now().UTC(),
						Reason: "bbo_buffer_overflow",
					})
				}
			},
			func(status domainmarket.StreamStatus) {
				select {
				case statuses <- providerStatusUpdate{status: status, keys: providerKeys}:
				default:
				}
			},
		)
		if err != nil {
			cancel()
			for _, subscription := range providerSubscriptions {
				_ = subscription.Close()
			}
			return nil, err
		}
		providerSubscriptions = append(providerSubscriptions, providerSubscription)
	}
	runtime := &marketRuntime{cancel: cancel, providers: providerSubscriptions, done: make(chan struct{})}
	go func() {
		defer close(runtime.done)
		var handlers sync.WaitGroup
		handlers.Add(3)
		go func() {
			defer handlers.Done()
			for {
				select {
				case <-runtimeCtx.Done():
					return
				case update := <-updates:
					s.handleKline(runtimeCtx, update)
				}
			}
		}()
		go func() {
			defer handlers.Done()
			for {
				select {
				case <-runtimeCtx.Done():
					return
				case quote := <-quotes:
					s.handleBBO(quote)
				}
			}
		}()
		go func() {
			defer handlers.Done()
			for {
				select {
				case <-runtimeCtx.Done():
					return
				case update := <-statuses:
					s.handleStatus(runtimeCtx, update.status, update.keys)
				}
			}
		}()
		handlers.Wait()
	}()
	return runtime, nil
}

func (s *MarketService) handleKline(ctx context.Context, update domainmarket.KlineUpdate) {
	if s.callback.Kline != nil {
		s.callback.Kline(update)
	}
	if !update.Final {
		return
	}
	candle := domainmarket.Candle{
		Provider: update.Market.Provider, Symbol: update.Market.Symbol,
		Timeframe: update.Market.Timeframe, OpenTime: update.OpenTime, CloseTime: update.CloseTime,
		Open: update.Open, High: update.High, Low: update.Low, Close: update.Close,
		Volume: update.Volume, TradeCount: update.TradeCount,
	}
	if err := s.store.PersistClosedCandles(ctx, []domainmarket.Candle{candle}); err != nil {
		s.publishStatus(domainmarket.StreamStatus{
			State: domainmarket.StreamStale, OccurredAt: time.Now().UTC(), Reason: "candle_persist_failed",
		})
		return
	}
	sequence := s.sequence.Add(1)
	_ = s.store.MarkStreamRecovered(ctx, update.Market, update.CloseTime, sequence)
}

func (s *MarketService) handleBBO(quote domainmarket.BBO) {
	quote.SourceSequence = s.sequence.Add(1)
	pair := strings.ToUpper(quote.Provider + "|" + quote.Symbol)
	s.mu.Lock()
	history := append(s.quoteByPair[pair], quote)
	if len(history) > s.quoteLimit {
		history = history[len(history)-s.quoteLimit:]
	}
	s.quoteByPair[pair] = history
	s.mu.Unlock()
	if s.callback.BBO != nil {
		s.callback.BBO(quote)
	}
}

func (s *MarketService) handleStatus(ctx context.Context, status domainmarket.StreamStatus, keys []domainmarket.StreamKey) {
	s.publishStatus(status)
	switch status.State {
	case domainmarket.StreamStale:
		for _, key := range keys {
			_ = s.store.MarkStreamStale(ctx, key, s.sequence.Load())
		}
	case domainmarket.StreamConnected:
		if err := s.recover(ctx, keys); err != nil {
			s.publishStatus(domainmarket.StreamStatus{
				State: domainmarket.StreamStale, OccurredAt: time.Now().UTC(),
				Reason: "backfill_failed", ReconnectNo: status.ReconnectNo,
			})
			return
		}
		s.publishStatus(domainmarket.StreamStatus{
			State: domainmarket.StreamRecovered, OccurredAt: time.Now().UTC(),
			ReconnectNo: status.ReconnectNo,
		})
	}
}

func (s *MarketService) recover(ctx context.Context, keys []domainmarket.StreamKey) error {
	now := time.Now().UTC()
	for _, key := range keys {
		provider, err := s.providers.Resolve(key.Provider)
		if err != nil {
			return fmt.Errorf("resolve market provider %q: %w", key.Provider, err)
		}
		checkpoint, err := s.store.LoadCheckpoint(ctx, key)
		if err != nil {
			return err
		}
		from := now.Add(-500 * timeframeDuration(string(key.Timeframe)))
		if checkpoint.LastClosedAt != nil {
			from = checkpoint.LastClosedAt.Add(time.Millisecond)
		}
		if !from.Before(now) {
			from = now.Add(-timeframeDuration(string(key.Timeframe)))
		}
		candles, err := provider.ListClosedCandles(ctx, domainmarket.CandleQuery{
			Market: key, From: from, To: now, Limit: 2_000,
		})
		if err != nil {
			return err
		}
		if err := s.store.PersistClosedCandles(ctx, candles); err != nil {
			return err
		}
		lastClosed := from
		if checkpoint.LastClosedAt != nil {
			lastClosed = *checkpoint.LastClosedAt
		}
		if len(candles) > 0 {
			lastClosed = candles[len(candles)-1].CloseTime
		}
		if err := s.store.MarkStreamRecovered(ctx, key, lastClosed, s.sequence.Load()); err != nil {
			return err
		}
	}
	return nil
}

func (s *MarketService) CreateDataset(
	ctx context.Context, key domainmarket.MarketKey, from, to time.Time, revision int,
) (domainmarket.Dataset, error) {
	pair := strings.ToUpper(key.Provider + "|" + key.Symbol)
	s.mu.RLock()
	quotes := append([]domainmarket.BBO(nil), s.quoteByPair[pair]...)
	s.mu.RUnlock()
	filtered := quotes[:0]
	for _, quote := range quotes {
		if !quote.EventTime.Before(from) && !quote.EventTime.After(to) {
			filtered = append(filtered, quote)
		}
	}
	return s.store.CreateDataset(ctx, key, from, to, revision, filtered)
}

func (s *MarketService) publishStatus(status domainmarket.StreamStatus) {
	if s.callback.Status != nil {
		s.callback.Status(status)
	}
}

func timeframeDuration(value string) time.Duration {
	switch value {
	case "1m":
		return time.Minute
	case "5m":
		return 5 * time.Minute
	case "15m":
		return 15 * time.Minute
	case "30m":
		return 30 * time.Minute
	case "1h":
		return time.Hour
	case "2h":
		return 2 * time.Hour
	case "4h":
		return 4 * time.Hour
	case "1d":
		return 24 * time.Hour
	default:
		return time.Minute
	}
}

type marketRuntime struct {
	cancel    context.CancelFunc
	providers []domainmarket.Subscription
	done      chan struct{}
	once      sync.Once
}

func (r *marketRuntime) Close() error {
	var closeErr error
	r.once.Do(func() {
		r.cancel()
		for _, provider := range r.providers {
			if err := provider.Close(); err != nil && closeErr == nil {
				closeErr = err
			}
		}
		<-r.done
	})
	return closeErr
}
