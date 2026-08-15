package main

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/EnsoTech-Studio/CryptoBot/server/internal/config"
	"github.com/EnsoTech-Studio/CryptoBot/server/internal/httpapi"
	"github.com/EnsoTech-Studio/CryptoBot/server/internal/lab"
)

func main() {
	// configure logger and load config
	cfg := config.Load()
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))

	// bootstrapping context for database and migration
	bootCtx, bootCancel := context.WithTimeout(context.Background(), 90*time.Second)
	defer bootCancel()

	// open database connection and run migrations
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

	signer, err := lab.NewSigner()
	if err != nil {
		logger.Error("jwt signer failed", "error", err)
		os.Exit(1)
	}

	app := lab.NewApp(db, cfg.AIServiceURL, &http.Client{Timeout: 30 * time.Second}, signer)
	if err := lab.AnalyzeNewsSentiment(bootCtx, db, cfg.AIServiceURL); err != nil {
		logger.Warn("news sentiment unavailable", "error", err)
	}

	runtimeCtx, runtimeCancel := context.WithCancel(context.Background())
	defer runtimeCancel()
	app.StartMarketClock(runtimeCtx)

	handler := httpapi.NewRouter(httpapi.NewHandler(app, cfg.CORSAllowedOrigins))

	server := &http.Server{
		Addr:              ":" + cfg.Port,
		Handler:           handler,
		ReadHeaderTimeout: 5 * time.Second,
		IdleTimeout:       60 * time.Second,
	}

	serverErrors := make(chan error, 1)
	go func() {
		logger.Info("api server listening", "addr", server.Addr, "ai_service_url", cfg.AIServiceURL)
		serverErrors <- server.ListenAndServe()
	}()

	shutdownContext, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	select {
	case err := <-serverErrors:
		if !errors.Is(err, http.ErrServerClosed) {
			logger.Error("api server stopped unexpectedly", "error", err)
			os.Exit(1)
		}
	case <-shutdownContext.Done():
		logger.Info("shutting down api server")
		runtimeCancel()
		ctx, cancel := context.WithTimeout(context.Background(), cfg.ShutdownTimeout)
		defer cancel()

		if err := server.Shutdown(ctx); err != nil {
			logger.Error("graceful shutdown failed", "error", err)
			os.Exit(1)
		}
	}
}
