package job

import (
	"time"

	"github.com/google/uuid"

	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/backtest"
	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/common"
)

type BacktestJob struct {
	ID             uuid.UUID                   `json:"id"`
	ExperimentID   uuid.UUID                   `json:"experiment_id"`
	Snapshot       backtest.ExperimentSnapshot `json:"snapshot"`
	Status         common.JobStatus            `json:"status"`
	Priority       int                         `json:"priority"`
	Attempt        int                         `json:"attempt"`
	MaxAttempts    int                         `json:"max_attempts"`
	LeasedBy       string                      `json:"leased_by,omitempty"`
	LeaseToken     uuid.UUID                   `json:"lease_token,omitempty"`
	LeaseExpiresAt time.Time                   `json:"lease_expires_at,omitempty"`
}
