package news

import (
	"time"

	"github.com/google/uuid"
)

type ApprovedSource struct {
	ID            int    `json:"id"`
	SourceKey     string `json:"source_key"`
	DisplayName   string `json:"display_name"`
	Kind          string `json:"kind"`
	AllowedOrigin string `json:"allowed_origin"`
	URLTemplate   string `json:"-"`
	IsActive      bool   `json:"is_active"`
}

type Item struct {
	ID           uuid.UUID `json:"id"`
	SourceID     int       `json:"source_id"`
	URL          string    `json:"url"`
	URLHash      string    `json:"url_hash"`
	Title        string    `json:"title"`
	Content      *string   `json:"content,omitempty"`
	PublishedAt  time.Time `json:"published_at"`
	RelatedCoins []string  `json:"related_coins"`
}
