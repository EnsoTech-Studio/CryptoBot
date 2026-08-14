package ws

import (
	"time"

	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/market"
)

type Frame struct {
	Type       string    `json:"type"`
	Sequence   uint64    `json:"sequence"`
	ServerTime time.Time `json:"server_time"`
	Payload    any       `json:"payload,omitempty"`
}

type SubscriptionRequest struct {
	Action       string                 `json:"action"`
	Key          market.SubscriptionKey `json:"key"`
	LastSequence uint64                 `json:"last_sequence,omitempty"`
}

type Hub interface {
	Subscribe(string, market.SubscriptionKey) error
	Unsubscribe(string, market.SubscriptionKey) error
	Publish(market.SubscriptionKey, Frame) error
	Resync(string, market.SubscriptionKey, uint64) ([]Frame, error)
}

const MaxSubscriptionsPerConnection = 8
