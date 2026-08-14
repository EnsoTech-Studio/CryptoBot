package indicator

import (
	"github.com/shopspring/decimal"

	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/common"
)

type IndicatorView struct{}

func NewView(map[string][]decimal.Decimal, int) (IndicatorView, error) {
	return IndicatorView{}, common.ErrNotImplemented
}
func (IndicatorView) At(string, int) (decimal.Decimal, error) {
	return decimal.Zero, common.ErrNotImplemented
}
func (IndicatorView) Current(string) (decimal.Decimal, error) {
	return decimal.Zero, common.ErrNotImplemented
}

type Library interface {
	Precompute([]decimal.Decimal, []string) (map[string][]decimal.Decimal, error)
}

type DeterministicLibrary struct{}

func (DeterministicLibrary) Precompute([]decimal.Decimal, []string) (map[string][]decimal.Decimal, error) {
	return nil, common.ErrNotImplemented
}
