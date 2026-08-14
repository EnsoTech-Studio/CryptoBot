package strategy

import "github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/common"

type Factory func() Strategy

type Registry struct{}

func NewRegistry() *Registry                               { return &Registry{} }
func (*Registry) Register(Factory) error                   { return common.ErrNotImplemented }
func (*Registry) Resolve(string, string) (Strategy, error) { return nil, common.ErrNotImplemented }
func (*Registry) List() []Definition                       { return nil }
