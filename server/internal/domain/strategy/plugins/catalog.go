package plugins

import (
	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/common"
	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/strategy"
)

// RegisterAll is the package-owned bootstrap seam for MA, RSI, Bollinger,
// support/resistance, sentiment, and future plugins.
func RegisterAll(*strategy.Registry) error { return common.ErrNotImplemented }
