package events

import (
	"context"
	"encoding/json"
	"time"

	"github.com/google/uuid"

	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/common"
)

type Metadata struct {
	EventID       uuid.UUID  `json:"event_id"`
	CorrelationID string     `json:"correlation_id"`
	CausationID   *uuid.UUID `json:"causation_id,omitempty"`
	SchemaVersion int        `json:"schema_version"`
	OccurredAt    time.Time  `json:"occurred_at"`
}

type DomainEvent struct {
	Metadata      Metadata        `json:"metadata"`
	EventType     string          `json:"event_type"`
	AggregateType string          `json:"aggregate_type"`
	AggregateID   uuid.UUID       `json:"aggregate_id"`
	Payload       json.RawMessage `json:"payload"`
}

type Dispatcher interface {
	Publish(context.Context, DomainEvent) error
	Subscribe(string, Consumer) error
}

type Consumer interface {
	ConsumerID() string
	Handle(context.Context, DomainEvent) error
}

type IdempotentConsumer struct{}

func (IdempotentConsumer) ConsumerID() string                        { return "" }
func (IdempotentConsumer) Handle(context.Context, DomainEvent) error { return common.ErrNotImplemented }
