package ports

import (
	"context"
	"time"

	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/news"
)

type NewsProvider interface {
	Collect(context.Context, news.ApprovedSource, time.Time) ([]news.Item, error)
}
