package search

import (
	"context"

	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/common"
	domainsearch "github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/search"
	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/strategy"
)

type NotImplementedGenerator struct{}

func (*NotImplementedGenerator) GeneratorID() string      { return "not_implemented" }
func (*NotImplementedGenerator) GeneratorVersion() string { return "0" }
func (*NotImplementedGenerator) Generate(context.Context, domainsearch.SearchSpace, int, *int64, domainsearch.SearchHistory) ([]strategy.CandidateStrategy, error) {
	return nil, common.ErrNotImplemented
}
