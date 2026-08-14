package database

import (
	"context"

	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/common"
)

type Pool struct{}

func Open(context.Context) (*Pool, error) { return nil, common.ErrNotImplemented }
func (*Pool) Close() error                { return nil }
