package market

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math/rand"
	"net/http"
	"net/url"
	"sort"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/coder/websocket"
	"github.com/shopspring/decimal"

	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/common"
	domainmarket "github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/market"
)

const (
	defaultRESTBaseURL     = "https://fapi.binance.com"
	defaultWSMarketBaseURL = "wss://fstream.binance.com/market/stream"
	defaultWSPublicBaseURL = "wss://fstream.binance.com/public/stream"
	maxRESTBodyBytes       = 4 << 20
	maxWSMessageBytes      = 1 << 20
	maxDatasetCandles      = 20_000
	streamReadIdleTimeout  = 90 * time.Second
)

var errInvalidMarketRequest = errors.New("invalid market request")

type BinanceProvider struct {
	restBaseURL     string
	wsMarketBaseURL string
	wsPublicBaseURL string
	restClient      *http.Client
	websocketClient *http.Client
	limiter         *weightLimiter
	now             func() time.Time
}

func NewBinanceProvider() *BinanceProvider {
	return newBinanceProviderWithEndpoints(
		defaultRESTBaseURL, defaultWSMarketBaseURL, defaultWSPublicBaseURL, nil,
	)
}

func NewBinanceProviderWithURLs(restBaseURL, wsBaseURL string, client *http.Client) *BinanceProvider {
	return newBinanceProviderWithEndpoints(restBaseURL, wsBaseURL, wsBaseURL, client)
}

func newBinanceProviderWithEndpoints(
	restBaseURL, wsMarketBaseURL, wsPublicBaseURL string,
	client *http.Client,
) *BinanceProvider {
	if client == nil {
		client = &http.Client{Timeout: 10 * time.Second}
	}
	// http.Client.Timeout covers the complete request lifetime. That is useful
	// for finite REST calls, but it would cancel an upgraded WebSocket after the
	// same timeout. Preserve the transport while removing the total timeout for
	// the long-lived Binance market stream.
	websocketClient := *client
	websocketClient.Timeout = 0
	return &BinanceProvider{
		restBaseURL:     strings.TrimRight(restBaseURL, "/"),
		wsMarketBaseURL: strings.TrimRight(wsMarketBaseURL, "/"),
		wsPublicBaseURL: strings.TrimRight(wsPublicBaseURL, "/"),
		restClient:      client,
		websocketClient: &websocketClient,
		limiter:         newWeightLimiter(4_800, time.Minute),
		now:             time.Now,
	}
}

func (*BinanceProvider) ProviderID() string { return "binance_usdm" }

func (p *BinanceProvider) ListClosedCandles(
	ctx context.Context, query domainmarket.CandleQuery,
) ([]domainmarket.Candle, error) {
	if err := validateCandleQuery(query); err != nil {
		return nil, err
	}
	remaining := query.Limit
	cursor := query.From
	candles := make([]domainmarket.Candle, 0, remaining)
	for remaining > 0 && cursor.Before(query.To) {
		pageLimit := min(remaining, 1500)
		page, err := p.listCandlePage(ctx, query.Market, cursor, query.To, pageLimit)
		if err != nil {
			return nil, err
		}
		if len(page) == 0 {
			break
		}
		for _, candle := range page {
			if !candle.OpenTime.Before(query.From) && !candle.CloseTime.After(query.To) {
				candles = append(candles, candle)
			}
		}
		last := page[len(page)-1]
		next := last.OpenTime.Add(time.Millisecond)
		if !next.After(cursor) {
			break
		}
		cursor = next
		remaining = query.Limit - len(candles)
		if len(page) < pageLimit {
			break
		}
	}
	sort.Slice(candles, func(i, j int) bool { return candles[i].OpenTime.Before(candles[j].OpenTime) })
	if len(candles) > query.Limit {
		candles = candles[:query.Limit]
	}
	return candles, nil
}

func (p *BinanceProvider) listCandlePage(
	ctx context.Context,
	key domainmarket.MarketKey,
	from time.Time,
	to time.Time,
	limit int,
) ([]domainmarket.Candle, error) {
	if err := p.limiter.acquire(ctx, candleRequestWeight(limit)); err != nil {
		return nil, fmt.Errorf("market provider throttled: %w", err)
	}
	endpoint, err := url.Parse(p.restBaseURL + "/fapi/v1/klines")
	if err != nil {
		return nil, fmt.Errorf("build Binance URL: %w", err)
	}
	values := endpoint.Query()
	values.Set("symbol", strings.ToUpper(key.Symbol))
	values.Set("interval", string(key.Timeframe))
	values.Set("startTime", strconv.FormatInt(from.UnixMilli(), 10))
	values.Set("endTime", strconv.FormatInt(to.UnixMilli(), 10))
	values.Set("limit", strconv.Itoa(limit))
	endpoint.RawQuery = values.Encode()
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, endpoint.String(), nil)
	if err != nil {
		return nil, fmt.Errorf("build Binance request: %w", err)
	}
	resp, err := p.restClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("Binance candles unavailable: %w", err)
	}
	defer resp.Body.Close()
	if used, parseErr := strconv.Atoi(resp.Header.Get("X-MBX-USED-WEIGHT-1M")); parseErr == nil {
		p.limiter.observeUsed(used)
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		message, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
		return nil, fmt.Errorf("Binance candles returned %d: %s", resp.StatusCode, strings.TrimSpace(string(message)))
	}
	decoder := json.NewDecoder(io.LimitReader(resp.Body, maxRESTBodyBytes+1))
	var rows [][]json.RawMessage
	if err := decoder.Decode(&rows); err != nil {
		return nil, fmt.Errorf("decode Binance candles: %w", err)
	}
	result := make([]domainmarket.Candle, 0, len(rows))
	for index, row := range rows {
		candle, err := normalizeRESTCandle(key, row)
		if err != nil {
			return nil, fmt.Errorf("normalize Binance candle %d: %w", index, err)
		}
		if candle.CloseTime.After(p.now().UTC()) {
			continue
		}
		result = append(result, candle)
	}
	return result, nil
}

func (p *BinanceProvider) StreamKlines(
	ctx context.Context,
	keys []domainmarket.StreamKey,
	publish func(domainmarket.KlineUpdate),
) (domainmarket.Subscription, error) {
	return p.StreamMarket(ctx, keys, publish, nil, nil)
}

func (p *BinanceProvider) StreamMarket(
	ctx context.Context,
	keys []domainmarket.StreamKey,
	publishKline func(domainmarket.KlineUpdate),
	publishBBO func(domainmarket.BBO),
	publishStatus func(domainmarket.StreamStatus),
) (domainmarket.Subscription, error) {
	if len(keys) == 0 || len(keys) > 512 {
		return nil, fmt.Errorf("%w: stream key count must be 1..512", errInvalidMarketRequest)
	}
	marketStreams := make([]string, 0, len(keys))
	publicStreams := make([]string, 0, len(keys))
	seenBBO := make(map[string]struct{})
	for _, key := range keys {
		if err := validateMarketKey(key); err != nil {
			return nil, err
		}
		symbol := strings.ToLower(key.Symbol)
		marketStreams = append(marketStreams, symbol+"@kline_"+string(key.Timeframe))
		if publishBBO != nil {
			if _, exists := seenBBO[symbol]; !exists {
				publicStreams = append(publicStreams, symbol+"@bookTicker")
				seenBBO[symbol] = struct{}{}
			}
		}
	}
	sort.Strings(marketStreams)
	sort.Strings(publicStreams)
	endpoints := []binanceStreamEndpoint{{
		url:           p.wsMarketBaseURL + "?streams=" + strings.Join(marketStreams, "/"),
		reportsStatus: true,
	}}
	if len(publicStreams) > 0 {
		endpoints = append(endpoints, binanceStreamEndpoint{
			url: p.wsPublicBaseURL + "?streams=" + strings.Join(publicStreams, "/"),
		})
	}
	subscriptionCtx, cancel := context.WithCancel(ctx)
	subscription := &binanceSubscription{
		cancel:        cancel,
		done:          make(chan struct{}),
		provider:      p,
		endpoints:     endpoints,
		publishKline:  publishKline,
		publishBBO:    publishBBO,
		publishStatus: publishStatus,
	}
	go subscription.run(subscriptionCtx)
	return subscription, nil
}

type binanceStreamEndpoint struct {
	url           string
	reportsStatus bool
}

type binanceSubscription struct {
	cancel        context.CancelFunc
	done          chan struct{}
	closeOnce     sync.Once
	provider      *BinanceProvider
	endpoints     []binanceStreamEndpoint
	publishKline  func(domainmarket.KlineUpdate)
	publishBBO    func(domainmarket.BBO)
	publishStatus func(domainmarket.StreamStatus)
	sequence      atomic.Uint64
}

func (s *binanceSubscription) Close() error {
	s.closeOnce.Do(s.cancel)
	<-s.done
	return nil
}

func (s *binanceSubscription) run(ctx context.Context) {
	defer close(s.done)
	var connections sync.WaitGroup
	for _, endpoint := range s.endpoints {
		connections.Add(1)
		go func() {
			defer connections.Done()
			s.runEndpoint(ctx, endpoint)
		}()
	}
	connections.Wait()
}

func (s *binanceSubscription) runEndpoint(ctx context.Context, endpoint binanceStreamEndpoint) {
	for attempt := 0; ; attempt++ {
		if ctx.Err() != nil {
			return
		}
		if endpoint.reportsStatus {
			s.publishState(domainmarket.StreamConnecting, attempt, "")
		}
		connection, _, err := websocket.Dial(
			ctx,
			endpoint.url,
			&websocket.DialOptions{HTTPClient: s.provider.websocketClient},
		)
		if err == nil {
			if endpoint.reportsStatus {
				s.publishState(domainmarket.StreamConnected, attempt, "")
			}
			connection.SetReadLimit(maxWSMessageBytes)
			err = s.readConnection(ctx, connection)
			connection.CloseNow()
		}
		if ctx.Err() != nil {
			return
		}
		if endpoint.reportsStatus {
			s.publishState(domainmarket.StreamStale, attempt+1, "connection_lost")
		}
		backoff := reconnectBackoff(attempt)
		timer := time.NewTimer(backoff)
		select {
		case <-ctx.Done():
			timer.Stop()
			return
		case <-timer.C:
		}
		_ = err
	}
}

func (s *binanceSubscription) publishState(
	state domainmarket.StreamState, reconnectNo int, reason string,
) {
	if s.publishStatus != nil {
		s.publishStatus(domainmarket.StreamStatus{
			State: state, OccurredAt: time.Now().UTC(), Reason: reason, ReconnectNo: reconnectNo,
		})
	}
}

func (s *binanceSubscription) readConnection(ctx context.Context, connection *websocket.Conn) error {
	sessionCtx, cancel := context.WithCancel(ctx)
	defer cancel()
	pingErrors := make(chan error, 1)
	go func() {
		ticker := time.NewTicker(30 * time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-sessionCtx.Done():
				return
			case <-ticker.C:
				pingCtx, stop := context.WithTimeout(sessionCtx, 10*time.Second)
				err := connection.Ping(pingCtx)
				stop()
				if err != nil {
					select {
					case pingErrors <- err:
					default:
					}
					cancel()
					return
				}
			}
		}
	}()
	for {
		readCtx, stopRead := context.WithTimeout(sessionCtx, streamReadIdleTimeout)
		_, payload, err := connection.Read(readCtx)
		stopRead()
		if err != nil {
			select {
			case pingErr := <-pingErrors:
				return pingErr
			default:
				return err
			}
		}
		if err := s.handleMessage(payload); err != nil {
			continue
		}
	}
}

func (s *binanceSubscription) handleMessage(payload []byte) error {
	var envelope struct {
		Stream string          `json:"stream"`
		Data   json.RawMessage `json:"data"`
	}
	if err := json.Unmarshal(payload, &envelope); err != nil {
		return err
	}
	// Decode the discriminator by its exact JSON key. Binance also sends an
	// uppercase "E" timestamp; decoding into a struct that only has `json:"e"`
	// makes encoding/json match "E" case-insensitively and reject the number as
	// a string, silently dropping every live frame.
	var header map[string]json.RawMessage
	if err := json.Unmarshal(envelope.Data, &header); err != nil {
		return err
	}
	var event string
	if err := json.Unmarshal(header["e"], &event); err != nil {
		return err
	}
	switch event {
	case "kline":
		update, err := normalizeKlineEvent(envelope.Data)
		if err != nil {
			return err
		}
		if s.publishKline != nil {
			s.publishKline(update)
		}
	case "bookTicker":
		quote, err := normalizeBookTicker(envelope.Data, s.sequence.Add(1))
		if err != nil {
			return err
		}
		if s.publishBBO != nil {
			s.publishBBO(quote)
		}
	}
	return nil
}

func normalizeRESTCandle(key domainmarket.MarketKey, row []json.RawMessage) (domainmarket.Candle, error) {
	if len(row) < 9 {
		return domainmarket.Candle{}, fmt.Errorf("expected at least 9 fields")
	}
	openMillis, err := rawInt64(row[0])
	if err != nil {
		return domainmarket.Candle{}, err
	}
	closeMillis, err := rawInt64(row[6])
	if err != nil {
		return domainmarket.Candle{}, err
	}
	open, err := rawDecimal(row[1])
	if err != nil {
		return domainmarket.Candle{}, err
	}
	high, err := rawDecimal(row[2])
	if err != nil {
		return domainmarket.Candle{}, err
	}
	low, err := rawDecimal(row[3])
	if err != nil {
		return domainmarket.Candle{}, err
	}
	closeValue, err := rawDecimal(row[4])
	if err != nil {
		return domainmarket.Candle{}, err
	}
	volume, err := rawDecimal(row[5])
	if err != nil {
		return domainmarket.Candle{}, err
	}
	trades, err := rawInt(row[8])
	if err != nil {
		return domainmarket.Candle{}, err
	}
	candle := domainmarket.Candle{
		Provider: key.Provider, Symbol: strings.ToUpper(key.Symbol), Timeframe: key.Timeframe,
		OpenTime: time.UnixMilli(openMillis).UTC(), CloseTime: time.UnixMilli(closeMillis).UTC(),
		Open: open, High: high, Low: low, Close: closeValue, Volume: volume, TradeCount: &trades,
	}
	if err := validateCandle(candle); err != nil {
		return domainmarket.Candle{}, err
	}
	return candle, nil
}

func normalizeKlineEvent(payload []byte) (domainmarket.KlineUpdate, error) {
	var event struct {
		Event     string `json:"e"`
		EventTime int64  `json:"E"`
		Symbol    string `json:"s"`
		Kline     struct {
			OpenTime           int64  `json:"t"`
			CloseTime          int64  `json:"T"`
			Symbol             string `json:"s"`
			Interval           string `json:"i"`
			FirstTradeID       int64  `json:"f"`
			LastTradeID        int64  `json:"L"`
			Open               string `json:"o"`
			Close              string `json:"c"`
			High               string `json:"h"`
			Low                string `json:"l"`
			Volume             string `json:"v"`
			TakerBuyBaseVolume string `json:"V"`
			Trades             int    `json:"n"`
			Final              bool   `json:"x"`
		} `json:"k"`
	}
	if err := json.Unmarshal(payload, &event); err != nil {
		return domainmarket.KlineUpdate{}, err
	}
	if event.Event != "kline" || event.Symbol == "" || !strings.EqualFold(event.Symbol, event.Kline.Symbol) {
		return domainmarket.KlineUpdate{}, fmt.Errorf("invalid kline envelope")
	}
	open, err := decimal.NewFromString(event.Kline.Open)
	if err != nil {
		return domainmarket.KlineUpdate{}, err
	}
	high, err := decimal.NewFromString(event.Kline.High)
	if err != nil {
		return domainmarket.KlineUpdate{}, err
	}
	low, err := decimal.NewFromString(event.Kline.Low)
	if err != nil {
		return domainmarket.KlineUpdate{}, err
	}
	closeValue, err := decimal.NewFromString(event.Kline.Close)
	if err != nil {
		return domainmarket.KlineUpdate{}, err
	}
	volume, err := decimal.NewFromString(event.Kline.Volume)
	if err != nil {
		return domainmarket.KlineUpdate{}, err
	}
	update := domainmarket.KlineUpdate{
		Market:   domainmarket.MarketKey{Provider: "binance_usdm", Symbol: strings.ToUpper(event.Symbol), Timeframe: common.Timeframe(event.Kline.Interval)},
		OpenTime: time.UnixMilli(event.Kline.OpenTime).UTC(), CloseTime: time.UnixMilli(event.Kline.CloseTime).UTC(),
		Open: open, High: high, Low: low, Close: closeValue, Volume: volume,
		TradeCount: &event.Kline.Trades, Final: event.Kline.Final,
	}
	if update.CloseTime.Before(update.OpenTime) || high.LessThan(low) || high.LessThan(open) || high.LessThan(closeValue) || low.GreaterThan(open) || low.GreaterThan(closeValue) || volume.IsNegative() {
		return domainmarket.KlineUpdate{}, fmt.Errorf("invalid kline values")
	}
	return update, nil
}

func normalizeBookTicker(payload []byte, sequence uint64) (domainmarket.BBO, error) {
	var event struct {
		Event     string `json:"e"`
		EventTime int64  `json:"E"`
		TradeTime int64  `json:"T"`
		Symbol    string `json:"s"`
		UpdateID  uint64 `json:"u"`
		Bid       string `json:"b"`
		BidQty    string `json:"B"`
		Ask       string `json:"a"`
		AskQty    string `json:"A"`
	}
	if err := json.Unmarshal(payload, &event); err != nil {
		return domainmarket.BBO{}, err
	}
	if event.Event != "bookTicker" || event.Symbol == "" {
		return domainmarket.BBO{}, fmt.Errorf("invalid bookTicker envelope")
	}
	bid, err := decimal.NewFromString(event.Bid)
	if err != nil {
		return domainmarket.BBO{}, err
	}
	bidQty, err := decimal.NewFromString(event.BidQty)
	if err != nil {
		return domainmarket.BBO{}, err
	}
	ask, err := decimal.NewFromString(event.Ask)
	if err != nil {
		return domainmarket.BBO{}, err
	}
	askQty, err := decimal.NewFromString(event.AskQty)
	if err != nil {
		return domainmarket.BBO{}, err
	}
	if bid.IsNegative() || ask.IsNegative() || bid.GreaterThan(ask) || bidQty.IsNegative() || askQty.IsNegative() {
		return domainmarket.BBO{}, fmt.Errorf("invalid bookTicker values")
	}
	eventTime := event.TradeTime
	if eventTime == 0 {
		eventTime = event.EventTime
	}
	updateID := event.UpdateID
	return domainmarket.BBO{
		Provider: "binance_usdm", Symbol: strings.ToUpper(event.Symbol), EventTime: time.UnixMilli(eventTime).UTC(),
		Bid: bid, BidQty: bidQty, Ask: ask, AskQty: askQty, UpdateID: &updateID, SourceSequence: sequence,
	}, nil
}

func validateCandleQuery(query domainmarket.CandleQuery) error {
	if err := validateMarketKey(query.Market); err != nil {
		return err
	}
	if query.From.IsZero() || query.To.IsZero() || !query.To.After(query.From) {
		return fmt.Errorf("%w: invalid candle range", errInvalidMarketRequest)
	}
	if query.Limit < 1 || query.Limit > maxDatasetCandles {
		return fmt.Errorf("%w: limit must be 1..%d", errInvalidMarketRequest, maxDatasetCandles)
	}
	return nil
}

func validateMarketKey(key domainmarket.MarketKey) error {
	if key.Provider != "binance_usdm" || strings.TrimSpace(key.Symbol) == "" || !validTimeframe(string(key.Timeframe)) {
		return fmt.Errorf("%w: unsupported provider, symbol, or timeframe", errInvalidMarketRequest)
	}
	return nil
}

func validateCandle(candle domainmarket.Candle) error {
	if !candle.CloseTime.After(candle.OpenTime) || candle.High.LessThan(candle.Low) || candle.High.LessThan(candle.Open) || candle.High.LessThan(candle.Close) || candle.Low.GreaterThan(candle.Open) || candle.Low.GreaterThan(candle.Close) || candle.Volume.IsNegative() {
		return fmt.Errorf("invalid OHLCV candle")
	}
	return nil
}

func validTimeframe(value string) bool {
	switch value {
	case "1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d":
		return true
	default:
		return false
	}
}

func rawDecimal(raw json.RawMessage) (decimal.Decimal, error) {
	var value string
	if err := json.Unmarshal(raw, &value); err != nil {
		return decimal.Zero, err
	}
	return decimal.NewFromString(value)
}

func rawInt64(raw json.RawMessage) (int64, error) {
	var value int64
	if err := json.Unmarshal(raw, &value); err != nil {
		return 0, err
	}
	return value, nil
}

func rawInt(raw json.RawMessage) (int, error) {
	var value int
	if err := json.Unmarshal(raw, &value); err != nil {
		return 0, err
	}
	return value, nil
}

func candleRequestWeight(limit int) int {
	switch {
	case limit < 100:
		return 1
	case limit < 500:
		return 2
	case limit <= 1000:
		return 5
	default:
		return 10
	}
}

func reconnectBackoff(attempt int) time.Duration {
	if attempt > 5 {
		attempt = 5
	}
	base := time.Second * time.Duration(1<<attempt)
	if base > 30*time.Second {
		base = 30 * time.Second
	}
	jitter := 0.8 + rand.Float64()*0.4
	return time.Duration(float64(base) * jitter)
}
