package application

import "context"

import "github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/common"

type Worker interface{ Run(context.Context) error }

type SkeletonWorker struct{}

func (SkeletonWorker) Run(context.Context) error { return common.ErrNotImplemented }
