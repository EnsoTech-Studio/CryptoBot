package ai

import (
	"context"

	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/common"
	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/sentiment"
)

type NotImplementedAnalyzer struct{}

func (*NotImplementedAnalyzer) ModelVersion() string { return "not-implemented" }
func (*NotImplementedAnalyzer) Analyze(context.Context, string) (sentiment.Result, error) {
	return sentiment.Result{}, common.ErrNotImplemented
}
