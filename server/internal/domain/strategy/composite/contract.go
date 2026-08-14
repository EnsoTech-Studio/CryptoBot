package composite

import (
	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/common"
	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/strategy"
)

type ResolvedSignal = strategy.ResolvedSignal
type CombinationPolicy = strategy.CombinationPolicy
type CompositeDefinition = strategy.CompositeDefinition

type SignalCombiner interface {
	Combine([]ResolvedSignal, CombinationPolicy) (strategy.Signal, error)
}

type WeightedVoteCombiner struct{}
type MajorityVoteCombiner struct{}

func (WeightedVoteCombiner) Combine([]ResolvedSignal, CombinationPolicy) (strategy.Signal, error) {
	return strategy.Signal{}, common.ErrNotImplemented
}

func (MajorityVoteCombiner) Combine([]ResolvedSignal, CombinationPolicy) (strategy.Signal, error) {
	return strategy.Signal{}, common.ErrNotImplemented
}
