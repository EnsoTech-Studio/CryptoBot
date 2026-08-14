package application

import (
	"context"
	"github.com/google/uuid"

	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/backtest"
	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/common"
)

type ExperimentCommand struct {
	OwnerID  uuid.UUID
	Snapshot backtest.ExperimentSnapshot
}

type AcceptedRun struct {
	RunID  uuid.UUID `json:"run_id"`
	Status string    `json:"status"`
}

type ExperimentService interface {
	Create(context.Context, ExperimentCommand) (AcceptedRun, error)
}

type SkeletonExperimentService struct{}

func (SkeletonExperimentService) Create(context.Context, ExperimentCommand) (AcceptedRun, error) {
	return AcceptedRun{}, common.ErrNotImplemented
}
