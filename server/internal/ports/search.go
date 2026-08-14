package ports

import (
	"context"

	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/search"
	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/strategy"
)

type CandidateGenerator interface {
	GeneratorID() string
	GeneratorVersion() string
	Generate(context.Context, search.SearchSpace, int, *int64, search.SearchHistory) ([]strategy.CandidateStrategy, error)
}
