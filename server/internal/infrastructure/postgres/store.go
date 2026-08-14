package postgres

import (
	"context"

	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/common"
)

type NotImplementedStore struct{}

func NewNotImplementedStore() *NotImplementedStore       { return &NotImplementedStore{} }
func (*NotImplementedStore) Ready(context.Context) error { return common.ErrNotImplemented }
