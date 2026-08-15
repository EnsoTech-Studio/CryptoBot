package main

import (
	"context"
	"errors"
	"log/slog"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/EnsoTech-Studio/CryptoBot/server/internal/config"
	"github.com/EnsoTech-Studio/CryptoBot/server/internal/lab"
)

func main() {
	cfg := config.Load()
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	workerID := os.Getenv("WORKER_ID")
	if workerID == "" {
		workerID = "worker-" + time.Now().UTC().Format("150405")
	}

	bootCtx, bootCancel := context.WithTimeout(context.Background(), 90*time.Second)
	defer bootCancel()

	db, err := lab.OpenDatabase(bootCtx, cfg.DatabaseURL)
	if err != nil {
		logger.Error("database is unavailable", "error", err)
		os.Exit(1)
	}
	defer db.Close()
	if err := lab.MigrateAndSeed(bootCtx, db); err != nil {
		logger.Error("migration or seed failed", "error", err)
		os.Exit(1)
	}
	signer, _ := lab.NewSigner()
	app := lab.NewApp(db, cfg.AIServiceURL, nil, signer)
	if err := lab.AnalyzeNewsSentiment(bootCtx, db, cfg.AIServiceURL); err != nil {
		logger.Warn("news sentiment unavailable", "error", err)
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	logger.Info("worker started", "worker_id", workerID)
	ticker := time.NewTicker(900 * time.Millisecond)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			logger.Info("worker shutting down", "worker_id", workerID)
			return
		case <-ticker.C:
			claimed, err := app.ClaimAndRunOne(ctx, workerID)
			if err != nil && !errors.Is(err, context.Canceled) {
				logger.Error("job failed", "worker_id", workerID, "error", err)
			}
			if claimed {
				logger.Info("job processed", "worker_id", workerID)
			}
		}
	}
}
