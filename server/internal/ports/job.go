package ports

import (
	"context"
	"time"

	"github.com/google/uuid"

	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/job"
)

type JobDispatcher interface {
	Enqueue(context.Context, job.BacktestJob) error
	Claim(context.Context, string, time.Duration) (job.BacktestJob, error)
	Complete(context.Context, uuid.UUID) error
	Fail(context.Context, uuid.UUID, error, bool) error
}
