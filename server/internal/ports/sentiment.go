package ports

import (
	"context"

	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/sentiment"
)

type SentimentAnalyzer interface {
	ModelVersion() string
	Analyze(context.Context, string) (sentiment.Result, error)
}
