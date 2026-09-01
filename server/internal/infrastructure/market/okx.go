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
	okxProviderID        = "okx_swap"
	defaultOKXRESTURL    = "https://www.okx.com"
	defaultOKXBusinessWS = "wss://ws.okx.com:8443/ws/v5/business"
	defaultOKXPublicWS   = "wss://ws.okx.com:8443/ws/v5/public"
	okxMaxRESTBodyBytes  = 4 << 20
	okxMaxWSMessageBytes = 1 << 20
	okxMaxCandlePageSize = 300
)

type OKXSwapProvider struct {
	restBaseURL     string
	wsBusinessURL   string
	wsPublicURL     string
	restClient      *http.Client
	websocketClient *http.Client
	limiter         *weightLimiter
	now             func() time.Time
}

func NewOKXSwapProvider() *OKXSwapProvider {
	return NewOKXSwapProviderWithURLs(defaultOKXRESTURL, defaultOKXBusinessWS, defaultOKXPublicWS, nil)
}

func NewOKXSwapProviderWithURLs(restBaseURL, wsBusinessURL, wsPublicURL string, client *http.Client) *OKXSwapProvider {
	if client == nil {
		client = &http.Client{Timeout: 10 * time.Second}
	}
	websocketClient := *client
	websocketClient.Timeout = 0
	return &OKXSwapProvider{
		restBaseURL:     strings.TrimRight(restBaseURL, "/"),
		wsBusinessURL:   strings.TrimRight(wsBusinessURL, "/"),
		wsPublicURL:     strings.TrimRight(wsPublicURL, "/"),
		restClient:      client,
		websocketClient: &websocketClient,
		limiter:         newWeightLimiter(1_000, time.Minute),
		now:             time.Now,
	}
}

func (*OKXSwapProvider) ProviderID() string { return okxProviderID }

func (p *OKXSwapProvider) ListClosedCandles(
	ctx context.Context, query domainmarket.CandleQuery,
) ([]domainmarket.Candle, error) {
	if err := validateOKXCandleQuery(query); err != nil {
		return nil, err
	}
	cursor := query.To.UTC().UnixMilli()
	candles := make([]domainmarket.Candle, 0, query.Limit)
	for len(candles) < query.Limit && cursor > query.From.UTC().UnixMilli() {
		pageLimit := min(okxMaxCandlePageSize, query.Limit-len(candles)+1)
		page, oldest, err := p.listCandlePage(ctx, query.Market, cursor, pageLimit)
		if err != nil {
			return nil, err
		}
		if len(page) == 0 || oldest == 0 {
			break
		}
		for _, row := range page {
			if !row.final || row.candle.CloseTime.After(p.now().UTC()) {
				continue
			}
			if !row.candle.OpenTime.Before(query.From) && !row.candle.CloseTime.After(query.To) {
				candles = append(candles, row.candle)
				if len(candles) == query.Limit {
					break
				}
			}
		}
		if oldest <= query.From.UTC().UnixMilli() || oldest >= cursor {
			break
		}
		cursor = oldest
		if len(page) < pageLimit {
			break
		}
	}
	sort.Slice(candles, func(i, j int) bool { return candles[i].OpenTime.Before(candles[j].OpenTime) })
	return candles, nil
}

func (p *OKXSwapProvider) listCandlePage(
	ctx context.Context,
	key domainmarket.MarketKey,
	beforeMillis int64,
	limit int,
) ([]okxCandle, int64, error) {
	if err := p.limiter.acquire(ctx, 1); err != nil {
		return nil, 0, fmt.Errorf("OKX market provider throttled: %w", err)
	}
	instrument, err := okxInstrumentID(key.Symbol)
	if err != nil {
		return nil, 0, err
	}
	endpoint, err := url.Parse(p.restBaseURL + "/api/v5/market/history-candles")
	if err != nil {
		return nil, 0, fmt.Errorf("build OKX URL: %w", err)
	}
	values := endpoint.Query()
	values.Set("instId", instrument)
	values.Set("bar", okxBar(key.Timeframe))
	values.Set("after", strconv.FormatInt(beforeMillis, 10))
	values.Set("limit", strconv.Itoa(limit))
	endpoint.RawQuery = values.Encode()
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, endpoint.String(), nil)
	if err != nil {
		return nil, 0, fmt.Errorf("build OKX request: %w", err)
	}
	resp, err := p.restClient.Do(req)
	if err != nil {
		return nil, 0, fmt.Errorf("OKX candles unavailable: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		message, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
		return nil, 0, fmt.Errorf("OKX candles returned %d: %s", resp.StatusCode, strings.TrimSpace(string(message)))
	}
	decoder := json.NewDecoder(io.LimitReader(resp.Body, okxMaxRESTBodyBytes+1))
	var payload struct {
		Code string              `json:"code"`
		Msg  string              `json:"msg"`
		Data [][]json.RawMessage `json:"data"`
	}
	if err := decoder.Decode(&payload); err != nil {
		return nil, 0, fmt.Errorf("decode OKX candles: %w", err)
	}
	if payload.Code != "0" {
		return nil, 0, fmt.Errorf("OKX candles returned code %s: %s", payload.Code, payload.Msg)
	}
	result := make([]okxCandle, 0, len(payload.Data))
	var oldest int64
	for index, row := range payload.Data {
		normalized, err := normalizeOKXCandle(key, row)
		if err != nil {
			return nil, 0, fmt.Errorf("normalize OKX candle %d: %w", index, err)
		}
		if oldest == 0 || normalized.openMillis < oldest {
			oldest = normalized.openMillis
		}
		result = append(result, normalized)
	}
	return result, oldest, nil
}

func (p *OKXSwapProvider) StreamKlines(
	ctx context.Context,
	keys []domainmarket.StreamKey,
	publish func(domainmarket.KlineUpdate),
) (domainmarket.Subscription, error) {
	return p.StreamMarket(ctx, keys, publish, nil, nil)
}

func (p *OKXSwapProvider) StreamMarket(
	ctx context.Context,
	keys []domainmarket.StreamKey,
	publishKline func(domainmarket.KlineUpdate),
	publishBBO func(domainmarket.BBO),
	publishStatus func(domainmarket.StreamStatus),
) (domainmarket.Subscription, error) {
	if len(keys) == 0 || len(keys) > 512 {
		return nil, fmt.Errorf("%w: stream key count must be 1..512", errInvalidMarketRequest)
	}
	candleArgs := make([]okxSubscribeArg, 0, len(keys))
	bboArgs := make([]okxSubscribeArg, 0)
	seenBBO := make(map[string]struct{})
	for _, key := range keys {
		if err := validateOKXMarketKey(key); err != nil {
			return nil, err
		}
		instrument, err := okxInstrumentID(key.Symbol)
		if err != nil {
			return nil, err
		}
		candleArgs = append(candleArgs, okxSubscribeArg{
			Channel: "candle" + okxBar(key.Timeframe),
			InstID:  instrument,
		})
		if publishBBO != nil {
			if _, exists := seenBBO[instrument]; !exists {
				bboArgs = append(bboArgs, okxSubscribeArg{Channel: "bbo-tbt", InstID: instrument})
				seenBBO[instrument] = struct{}{}
			}
		}
	}
	sort.Slice(candleArgs, func(i, j int) bool {
		return candleArgs[i].Channel+"|"+candleArgs[i].InstID < candleArgs[j].Channel+"|"+candleArgs[j].InstID
	})
	sort.Slice(bboArgs, func(i, j int) bool { return bboArgs[i].InstID < bboArgs[j].InstID })
	endpoints := []okxStreamEndpoint{{
		url:           p.wsBusinessURL,
		args:          candleArgs,
		reportsStatus: true,
	}}
	if len(bboArgs) > 0 {
		endpoints = append(endpoints, okxStreamEndpoint{url: p.wsPublicURL, args: bboArgs})
	}
	subscriptionCtx, cancel := context.WithCancel(ctx)
	subscription := &okxSubscription{
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

type okxCandle struct {
	candle     domainmarket.Candle
	final      bool
	openMillis int64
}

type okxSubscribeArg struct {
	Channel string `json:"channel"`
	InstID  string `json:"instId"`
}

type okxStreamEndpoint struct {
	url           string
	args          []okxSubscribeArg
	reportsStatus bool
}

type okxSubscription struct {
	cancel        context.CancelFunc
	done          chan struct{}
	closeOnce     sync.Once
	provider      *OKXSwapProvider
	endpoints     []okxStreamEndpoint
	publishKline  func(domainmarket.KlineUpdate)
	publishBBO    func(domainmarket.BBO)
	publishStatus func(domainmarket.StreamStatus)
	sequence      atomic.Uint64
}

func (s *okxSubscription) Close() error {
	s.closeOnce.Do(s.cancel)
	<-s.done
	return nil
}

func (s *okxSubscription) run(ctx context.Context) {
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

func (s *okxSubscription) runEndpoint(ctx context.Context, endpoint okxStreamEndpoint) {
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
			err = s.subscribe(ctx, connection, endpoint.args)
			if err == nil {
				if endpoint.reportsStatus {
					s.publishState(domainmarket.StreamConnected, attempt, "")
				}
				connection.SetReadLimit(okxMaxWSMessageBytes)
				err = s.readConnection(ctx, connection)
			}
			connection.CloseNow()
		}
		if ctx.Err() != nil {
			return
		}
		if endpoint.reportsStatus {
			s.publishState(domainmarket.StreamStale, attempt+1, "connection_lost")
		}
		timer := time.NewTimer(okxReconnectBackoff(attempt))
		select {
		case <-ctx.Done():
			timer.Stop()
			return
		case <-timer.C:
		}
		_ = err
	}
}

func (s *okxSubscription) subscribe(ctx context.Context, connection *websocket.Conn, args []okxSubscribeArg) error {
	if len(args) == 0 {
		return nil
	}
	payload, err := json.Marshal(map[string]any{
		"op":   "subscribe",
		"args": args,
	})
	if err != nil {
		return err
	}
	writeCtx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()
	return connection.Write(writeCtx, websocket.MessageText, payload)
}

func (s *okxSubscription) publishState(
	state domainmarket.StreamState, reconnectNo int, reason string,
) {
	if s.publishStatus != nil {
		s.publishStatus(domainmarket.StreamStatus{
			State: state, OccurredAt: time.Now().UTC(), Reason: reason, ReconnectNo: reconnectNo,
		})
	}
}

func (s *okxSubscription) readConnection(ctx context.Context, connection *websocket.Conn) error {
	sessionCtx, cancel := context.WithCancel(ctx)
	defer cancel()
	pingErrors := make(chan error, 1)
	go func() {
		ticker := time.NewTicker(25 * time.Second)
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
		if string(payload) == "ping" {
			writeCtx, cancelWrite := context.WithTimeout(sessionCtx, 5*time.Second)
			err := connection.Write(writeCtx, websocket.MessageText, []byte("pong"))
			cancelWrite()
			if err != nil {
				return err
			}
			continue
		}
		if err := s.handleMessage(payload); err != nil {
			continue
		}
	}
}

func (s *okxSubscription) handleMessage(payload []byte) error {
	if string(payload) == "pong" {
		return nil
	}
	var envelope struct {
		Event string          `json:"event"`
		Code  string          `json:"code"`
		Msg   string          `json:"msg"`
		Arg   okxSubscribeArg `json:"arg"`
		Data  json.RawMessage `json:"data"`
	}
	if err := json.Unmarshal(payload, &envelope); err != nil {
		return err
	}
	if envelope.Event != "" {
		if envelope.Event == "error" {
			return fmt.Errorf("OKX stream error %s: %s", envelope.Code, envelope.Msg)
		}
		return nil
	}
	if len(envelope.Data) == 0 {
		return nil
	}
	if strings.HasPrefix(envelope.Arg.Channel, "candle") {
		var rows [][]json.RawMessage
		if err := json.Unmarshal(envelope.Data, &rows); err != nil {
			return err
		}
		key, err := okxMarketKey(envelope.Arg)
		if err != nil {
			return err
		}
		for _, row := range rows {
			candle, err := normalizeOKXCandle(key, row)
			if err != nil {
				return err
			}
			if s.publishKline != nil {
				s.publishKline(domainmarket.KlineUpdate{
					Market: key, OpenTime: candle.candle.OpenTime, CloseTime: candle.candle.CloseTime,
					Open: candle.candle.Open, High: candle.candle.High, Low: candle.candle.Low,
					Close: candle.candle.Close, Volume: candle.candle.Volume,
					TradeCount: candle.candle.TradeCount, Final: candle.final,
				})
			}
		}
		return nil
	}
	if envelope.Arg.Channel == "bbo-tbt" {
		var rows []struct {
			Asks  [][]string `json:"asks"`
			Bids  [][]string `json:"bids"`
			TS    string     `json:"ts"`
			SeqID uint64     `json:"seqId"`
		}
		if err := json.Unmarshal(envelope.Data, &rows); err != nil {
			return err
		}
		for _, row := range rows {
			quote, err := normalizeOKXBBO(envelope.Arg, row.Asks, row.Bids, row.TS, row.SeqID, s.sequence.Add(1))
			if err != nil {
				return err
			}
			if s.publishBBO != nil {
				s.publishBBO(quote)
			}
		}
	}
	return nil
}

func normalizeOKXCandle(key domainmarket.MarketKey, row []json.RawMessage) (okxCandle, error) {
	if len(row) < 9 {
		return okxCandle{}, fmt.Errorf("expected at least 9 fields")
	}
	openMillis, err := okxRawInt64(row[0])
	if err != nil {
		return okxCandle{}, err
	}
	open, err := okxRawDecimal(row[1])
	if err != nil {
		return okxCandle{}, err
	}
	high, err := okxRawDecimal(row[2])
	if err != nil {
		return okxCandle{}, err
	}
	low, err := okxRawDecimal(row[3])
	if err != nil {
		return okxCandle{}, err
	}
	closeValue, err := okxRawDecimal(row[4])
	if err != nil {
		return okxCandle{}, err
	}
	volume, err := okxRawDecimal(row[6])
	if err != nil {
		volume, err = okxRawDecimal(row[5])
		if err != nil {
			return okxCandle{}, err
		}
	}
	confirm, err := okxRawString(row[8])
	if err != nil {
		return okxCandle{}, err
	}
	duration := okxTimeframeDuration(key.Timeframe)
	candle := domainmarket.Candle{
		Provider: key.Provider, Symbol: strings.ToUpper(key.Symbol), Timeframe: key.Timeframe,
		OpenTime: time.UnixMilli(openMillis).UTC(), CloseTime: time.UnixMilli(openMillis).UTC().Add(duration - time.Millisecond),
		Open: open, High: high, Low: low, Close: closeValue, Volume: volume,
	}
	if err := validateCandle(candle); err != nil {
		return okxCandle{}, err
	}
	return okxCandle{candle: candle, final: confirm == "1", openMillis: openMillis}, nil
}

func normalizeOKXBBO(
	arg okxSubscribeArg,
	asks [][]string,
	bids [][]string,
	timestamp string,
	updateID uint64,
	sequence uint64,
) (domainmarket.BBO, error) {
	if len(asks) == 0 || len(asks[0]) < 2 || len(bids) == 0 || len(bids[0]) < 2 {
		return domainmarket.BBO{}, fmt.Errorf("OKX BBO requires one bid and ask")
	}
	bid, err := decimal.NewFromString(bids[0][0])
	if err != nil {
		return domainmarket.BBO{}, err
	}
	bidQty, err := decimal.NewFromString(bids[0][1])
	if err != nil {
		return domainmarket.BBO{}, err
	}
	ask, err := decimal.NewFromString(asks[0][0])
	if err != nil {
		return domainmarket.BBO{}, err
	}
	askQty, err := decimal.NewFromString(asks[0][1])
	if err != nil {
		return domainmarket.BBO{}, err
	}
	eventMillis, err := strconv.ParseInt(timestamp, 10, 64)
	if err != nil {
		return domainmarket.BBO{}, err
	}
	if bid.IsNegative() || ask.IsNegative() || bid.GreaterThan(ask) || bidQty.IsNegative() || askQty.IsNegative() {
		return domainmarket.BBO{}, fmt.Errorf("invalid OKX BBO values")
	}
	symbol, err := okxSymbolFromInstrument(arg.InstID)
	if err != nil {
		return domainmarket.BBO{}, err
	}
	return domainmarket.BBO{
		Provider: okxProviderID, Symbol: symbol, EventTime: time.UnixMilli(eventMillis).UTC(),
		Bid: bid, BidQty: bidQty, Ask: ask, AskQty: askQty, UpdateID: &updateID, SourceSequence: sequence,
	}, nil
}

func validateOKXCandleQuery(query domainmarket.CandleQuery) error {
	if err := validateOKXMarketKey(query.Market); err != nil {
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

func validateOKXMarketKey(key domainmarket.MarketKey) error {
	if key.Provider != okxProviderID || strings.TrimSpace(key.Symbol) == "" || !validTimeframe(string(key.Timeframe)) {
		return fmt.Errorf("%w: unsupported OKX provider, symbol, or timeframe", errInvalidMarketRequest)
	}
	if _, err := okxInstrumentID(key.Symbol); err != nil {
		return err
	}
	return nil
}

func okxMarketKey(arg okxSubscribeArg) (domainmarket.MarketKey, error) {
	symbol, err := okxSymbolFromInstrument(arg.InstID)
	if err != nil {
		return domainmarket.MarketKey{}, err
	}
	timeframe, err := okxTimeframeFromChannel(arg.Channel)
	if err != nil {
		return domainmarket.MarketKey{}, err
	}
	return domainmarket.MarketKey{Provider: okxProviderID, Symbol: symbol, Timeframe: timeframe}, nil
}

func okxInstrumentID(symbol string) (string, error) {
	cleaned := strings.ToUpper(strings.ReplaceAll(strings.TrimSpace(symbol), "-", ""))
	if len(cleaned) <= len("USDT") || !strings.HasSuffix(cleaned, "USDT") {
		return "", fmt.Errorf("%w: OKX swap symbol must end in USDT", errInvalidMarketRequest)
	}
	return cleaned[:len(cleaned)-len("USDT")] + "-USDT-SWAP", nil
}

func okxSymbolFromInstrument(instrument string) (string, error) {
	parts := strings.Split(strings.ToUpper(strings.TrimSpace(instrument)), "-")
	if len(parts) != 3 || parts[1] != "USDT" || parts[2] != "SWAP" || parts[0] == "" {
		return "", fmt.Errorf("%w: unsupported OKX instrument", errInvalidMarketRequest)
	}
	return parts[0] + "USDT", nil
}

func okxBar(timeframe common.Timeframe) string {
	switch timeframe {
	case common.Timeframe1h:
		return "1H"
	case common.Timeframe2h:
		return "2H"
	case common.Timeframe4h:
		return "4H"
	case common.Timeframe1d:
		return "1Dutc"
	default:
		return string(timeframe)
	}
}

func okxTimeframeFromChannel(channel string) (common.Timeframe, error) {
	switch strings.TrimPrefix(channel, "candle") {
	case "1m":
		return common.Timeframe1m, nil
	case "5m":
		return common.Timeframe5m, nil
	case "15m":
		return common.Timeframe15m, nil
	case "30m":
		return common.Timeframe30m, nil
	case "1H":
		return common.Timeframe1h, nil
	case "2H":
		return common.Timeframe2h, nil
	case "4H":
		return common.Timeframe4h, nil
	case "1Dutc":
		return common.Timeframe1d, nil
	default:
		return "", fmt.Errorf("%w: unsupported OKX candle channel", errInvalidMarketRequest)
	}
}

func okxTimeframeDuration(timeframe common.Timeframe) time.Duration {
	switch timeframe {
	case common.Timeframe5m:
		return 5 * time.Minute
	case common.Timeframe15m:
		return 15 * time.Minute
	case common.Timeframe30m:
		return 30 * time.Minute
	case common.Timeframe1h:
		return time.Hour
	case common.Timeframe2h:
		return 2 * time.Hour
	case common.Timeframe4h:
		return 4 * time.Hour
	case common.Timeframe1d:
		return 24 * time.Hour
	default:
		return time.Minute
	}
}

func okxRawString(raw json.RawMessage) (string, error) {
	var value string
	if err := json.Unmarshal(raw, &value); err != nil {
		return "", err
	}
	return value, nil
}

func okxRawInt64(raw json.RawMessage) (int64, error) {
	value, err := okxRawString(raw)
	if err != nil {
		return 0, err
	}
	return strconv.ParseInt(value, 10, 64)
}

func okxRawDecimal(raw json.RawMessage) (decimal.Decimal, error) {
	value, err := okxRawString(raw)
	if err != nil {
		return decimal.Zero, err
	}
	if strings.TrimSpace(value) == "" {
		return decimal.Zero, errors.New("empty decimal")
	}
	return decimal.NewFromString(value)
}

func okxReconnectBackoff(attempt int) time.Duration {
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
