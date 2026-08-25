package ws

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"sync"
	"time"

	"github.com/coder/websocket"

	domainmarket "github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/market"
)

const (
	clientBuffer = 256
	historyLimit = 512
	maxFrameSize = 1 << 20
)

type outboundFrame struct {
	key      string
	sequence uint64
	payload  []byte
}

type hubClient struct {
	id            string
	send          chan []byte
	subscriptions map[string]struct{}
}

type MemoryHub struct {
	mu             sync.RWMutex
	clients        map[string]*hubClient
	history        map[string][]outboundFrame
	sequences      map[string]uint64
	allowedOrigins map[string]struct{}
}

func NewMemoryHub(allowedOrigins []string) *MemoryHub {
	origins := make(map[string]struct{}, len(allowedOrigins))
	for _, origin := range allowedOrigins {
		origin = strings.TrimSpace(origin)
		if origin != "" {
			origins[origin] = struct{}{}
		}
	}
	return &MemoryHub{
		clients: make(map[string]*hubClient), history: make(map[string][]outboundFrame),
		sequences: make(map[string]uint64), allowedOrigins: origins,
	}
}

func (h *MemoryHub) ServeHTTP(writer http.ResponseWriter, request *http.Request) {
	origin := request.Header.Get("Origin")
	if _, allowed := h.allowedOrigins[origin]; origin == "" || !allowed {
		http.Error(writer, "websocket origin is not allowed", http.StatusForbidden)
		return
	}
	connection, err := websocket.Accept(writer, request, &websocket.AcceptOptions{
		InsecureSkipVerify: true, // exact Origin allowlist was checked above
	})
	if err != nil {
		return
	}
	connection.SetReadLimit(maxFrameSize)
	ctx, cancel := context.WithCancel(request.Context())
	defer cancel()
	defer connection.Close(websocket.StatusNormalClosure, "")

	client := &hubClient{
		id: fmt.Sprintf("ws-%d", time.Now().UnixNano()), send: make(chan []byte, clientBuffer),
		subscriptions: make(map[string]struct{}),
	}
	h.mu.Lock()
	h.clients[client.id] = client
	h.mu.Unlock()
	defer func() {
		h.mu.Lock()
		delete(h.clients, client.id)
		h.mu.Unlock()
	}()

	writeDone := make(chan struct{})
	go func() {
		defer close(writeDone)
		for {
			select {
			case <-ctx.Done():
				return
			case payload := <-client.send:
				writeCtx, stop := context.WithTimeout(ctx, 5*time.Second)
				err := connection.Write(writeCtx, websocket.MessageText, payload)
				stop()
				if err != nil {
					cancel()
					return
				}
			}
		}
	}()

	for ctx.Err() == nil {
		_, payload, err := connection.Read(ctx)
		if err != nil {
			break
		}
		if err := h.handleCommand(client, payload); err != nil {
			h.enqueue(client, mustJSON(map[string]any{
				"type": "error", "error": map[string]any{"code": "invalid_subscription", "message": err.Error()},
			}))
		}
	}
	cancel()
	<-writeDone
}

func (h *MemoryHub) handleCommand(client *hubClient, payload []byte) error {
	var command struct {
		Action       string `json:"action"`
		Key          string `json:"key"`
		RequestID    string `json:"req"`
		LastSequence uint64 `json:"last_sequence"`
	}
	if err := json.Unmarshal(payload, &command); err != nil {
		return fmt.Errorf("invalid JSON command")
	}
	if err := validatePublicKey(command.Key); err != nil {
		return err
	}
	h.mu.Lock()
	switch command.Action {
	case "subscribe":
		if len(client.subscriptions) >= MaxSubscriptionsPerConnection {
			h.mu.Unlock()
			return fmt.Errorf("subscription limit exceeded")
		}
		client.subscriptions[command.Key] = struct{}{}
		history := append([]outboundFrame(nil), h.history[command.Key]...)
		sequence := h.sequences[command.Key]
		h.mu.Unlock()
		h.enqueue(client, mustJSON(map[string]any{
			"type": "subscribed", "key": command.Key, "req": command.RequestID,
			"sequence": sequence, "seq": sequence,
		}))
		if command.LastSequence > 0 {
			h.replay(client, command.Key, command.LastSequence, history)
		}
		return nil
	case "unsubscribe":
		delete(client.subscriptions, command.Key)
		h.mu.Unlock()
		h.enqueue(client, mustJSON(map[string]any{
			"type": "unsubscribed", "key": command.Key, "req": command.RequestID,
		}))
		return nil
	default:
		h.mu.Unlock()
		return fmt.Errorf("action must be subscribe or unsubscribe")
	}
}

func (h *MemoryHub) replay(
	client *hubClient, key string, lastSequence uint64, history []outboundFrame,
) {
	if len(history) > 0 && lastSequence+1 < history[0].sequence {
		h.enqueue(client, mustJSON(map[string]any{
			"type": "resync_required", "key": key, "last_sequence": lastSequence,
			"available_from": history[0].sequence,
		}))
		return
	}
	for _, frame := range history {
		if frame.sequence > lastSequence {
			h.enqueue(client, frame.payload)
		}
	}
}

func (h *MemoryHub) PublishKline(update domainmarket.KlineUpdate) {
	h.publishMatching(update.Market, "kline", func(key string, sequence uint64) map[string]any {
		return map[string]any{
			"type": "kline", "key": key, "sequence": sequence, "seq": sequence,
			"server_time": time.Now().UTC(), "final": update.Final,
			"kline": map[string]any{
				"open_time": update.OpenTime, "close_time": update.CloseTime,
				"open": update.Open.String(), "high": update.High.String(),
				"low": update.Low.String(), "close": update.Close.String(),
				"volume": update.Volume.String(), "trade_count": update.TradeCount,
			},
		}
	})
}

func (h *MemoryHub) PublishBBO(quote domainmarket.BBO) {
	h.mu.RLock()
	keys := h.matchingKeys(quote.Provider, quote.Symbol, "")
	h.mu.RUnlock()
	for _, key := range keys {
		h.publish(key, map[string]any{
			"type": "bbo", "key": key, "event_time": quote.EventTime,
			"bid": quote.Bid.String(), "bid_qty": quote.BidQty.String(),
			"ask": quote.Ask.String(), "ask_qty": quote.AskQty.String(),
			"update_id": quote.UpdateID, "source_sequence": quote.SourceSequence,
		})
	}
}

func (h *MemoryHub) PublishStatus(status domainmarket.StreamStatus) {
	h.mu.RLock()
	keys := make(map[string]struct{})
	for _, client := range h.clients {
		for key := range client.subscriptions {
			keys[key] = struct{}{}
		}
	}
	h.mu.RUnlock()
	for key := range keys {
		h.publish(key, map[string]any{
			"type": "stream_status", "key": key, "state": status.State,
			"occurred_at": status.OccurredAt, "reason": status.Reason,
			"reconnect_no": status.ReconnectNo,
		})
	}
}

func (h *MemoryHub) publishMatching(
	market domainmarket.MarketKey,
	_ string,
	build func(string, uint64) map[string]any,
) {
	h.mu.RLock()
	keys := h.matchingKeys(market.Provider, market.Symbol, string(market.Timeframe))
	h.mu.RUnlock()
	for _, key := range keys {
		sequence := h.nextSequence(key)
		h.publishWithSequence(key, sequence, build(key, sequence))
	}
}

func (h *MemoryHub) publish(key string, payload map[string]any) {
	sequence := h.nextSequence(key)
	payload["sequence"] = sequence
	payload["seq"] = sequence
	payload["server_time"] = time.Now().UTC()
	h.publishWithSequence(key, sequence, payload)
}

func (h *MemoryHub) nextSequence(key string) uint64 {
	h.mu.Lock()
	h.sequences[key]++
	sequence := h.sequences[key]
	h.mu.Unlock()
	return sequence
}

func (h *MemoryHub) publishWithSequence(key string, sequence uint64, payload map[string]any) {
	encoded := mustJSON(payload)
	h.mu.Lock()
	history := append(h.history[key], outboundFrame{key: key, sequence: sequence, payload: encoded})
	if len(history) > historyLimit {
		history = append([]outboundFrame(nil), history[len(history)-historyLimit:]...)
	}
	h.history[key] = history
	clients := make([]*hubClient, 0)
	for _, client := range h.clients {
		if _, subscribed := client.subscriptions[key]; subscribed {
			clients = append(clients, client)
		}
	}
	h.mu.Unlock()
	for _, client := range clients {
		h.enqueue(client, encoded)
	}
}

func (h *MemoryHub) matchingKeys(provider, symbol, timeframe string) []string {
	seen := make(map[string]struct{})
	for _, client := range h.clients {
		for key := range client.subscriptions {
			parts := strings.Split(key, "|")
			if len(parts) < 3 || !strings.EqualFold(parts[0], provider) ||
				!strings.EqualFold(parts[1], symbol) ||
				(timeframe != "" && parts[2] != timeframe) {
				continue
			}
			seen[key] = struct{}{}
		}
	}
	keys := make([]string, 0, len(seen))
	for key := range seen {
		keys = append(keys, key)
	}
	return keys
}

func (h *MemoryHub) enqueue(client *hubClient, payload []byte) {
	select {
	case client.send <- payload:
	default:
		select {
		case <-client.send:
		default:
		}
		select {
		case client.send <- mustJSON(map[string]any{"type": "resync_required", "reason": "client_buffer_overflow"}):
		default:
		}
	}
}

func validatePublicKey(key string) error {
	parts := strings.Split(key, "|")
	if len(parts) < 3 || len(parts) > 5 || parts[0] != "binance_usdm" ||
		strings.TrimSpace(parts[1]) == "" {
		return fmt.Errorf("invalid subscription key")
	}
	switch parts[2] {
	case "1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d":
		return nil
	default:
		return fmt.Errorf("unsupported timeframe")
	}
}

func mustJSON(value any) []byte {
	payload, _ := json.Marshal(value)
	return payload
}
