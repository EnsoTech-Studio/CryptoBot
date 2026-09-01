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

	"github.com/EnsoTech-Studio/CryptoBot/server/internal/application"
	authservice "github.com/EnsoTech-Studio/CryptoBot/server/internal/auth"
	"github.com/EnsoTech-Studio/CryptoBot/server/internal/config"
	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/common"
	domainmarket "github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/market"
	"github.com/EnsoTech-Studio/CryptoBot/server/internal/httpapi"
	marketadapter "github.com/EnsoTech-Studio/CryptoBot/server/internal/infrastructure/market"
	postgresadapter "github.com/EnsoTech-Studio/CryptoBot/server/internal/infrastructure/postgres"
	"github.com/EnsoTech-Studio/CryptoBot/server/internal/infrastructure/research"
	platformdb "github.com/EnsoTech-Studio/CryptoBot/server/internal/platform/database"
	transportws "github.com/EnsoTech-Studio/CryptoBot/server/internal/transport/ws"
)

func main() {
	// configure logger and load config
	cfg := config.Load()
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))

	// bootstrapping context for database and migration
	bootCtx, bootCancel := context.WithTimeout(context.Background(), 90*time.Second)
	defer bootCancel()

	researchClient, err := research.NewClient(
		cfg.ResearchServiceURL,
		cfg.InternalServiceToken,
		&http.Client{Timeout: cfg.ResearchTimeout},
		cfg.ResearchMaxBodyBytes,
	)
	if err != nil {
		logger.Error("research client configuration failed", "error", err)
		os.Exit(1)
	}
	runtimeCtx, runtimeCancel := context.WithCancel(context.Background())
	defer runtimeCancel()

	edgeHandler := httpapi.NewHandlerWithResearch(
		cfg.CORSAllowedOrigins,
		researchClient,
	)
	var marketPool *platformdb.Pool
	var marketSubscription domainmarket.Subscription
	marketPool, err = platformdb.Open(bootCtx, cfg.MarketDatabaseURL)
	if err != nil {
		logger.Error("market database is unavailable", "error", err)
		os.Exit(1)
	}
	defer marketPool.Close()
	targetSigner, signerErr := authservice.LoadOrCreateSigner(
		cfg.JWTPrivateKeyFile, "cryptobot", "cryptobot-web",
	)
	if signerErr != nil {
		logger.Error("persistent JWT signer failed", "error", signerErr)
		os.Exit(1)
	}
	edgeHandler.SetAuthService(
		authservice.NewService(marketPool.Pool, targetSigner), cfg.CookieSecure,
	)
	hub := transportws.NewMemoryHub(cfg.CORSAllowedOrigins)
	marketProviders := []string{"binance_usdm", "okx_swap"}
	marketSymbols := []string{"BTCUSDT", "ETHUSDT", "SOLUSDT"}
	marketTimeframes := []common.Timeframe{"1m", "5m", "15m", "1h", "4h", "1d"}
	keys := make([]domainmarket.StreamKey, 0, len(marketProviders)*len(marketSymbols)*len(marketTimeframes))
	for _, provider := range marketProviders {
		for _, symbol := range marketSymbols {
			for _, timeframe := range marketTimeframes {
				keys = append(keys, domainmarket.StreamKey{
					Provider: provider, Symbol: symbol, Timeframe: timeframe,
				})
			}
		}
	}
	providerRegistry, registryErr := marketadapter.NewProviderRegistry(
		marketadapter.NewBinanceProvider(),
		marketadapter.NewOKXSwapProvider(),
	)
	if registryErr != nil {
		logger.Error("market provider registry failed", "error", registryErr)
		os.Exit(1)
	}
	marketService, serviceErr := application.NewMarketService(
		providerRegistry,
		postgresadapter.NewStore(marketPool.Pool),
		keys,
		application.MarketCallbacks{
			Kline: func(update domainmarket.KlineUpdate) {
				sequences := hub.PublishKline(update)
				if !update.Final {
					return
				}
				for key, sequence := range sequences {
					go func(key string, sequence uint64) {
						ctx, cancel := context.WithTimeout(runtimeCtx, cfg.ResearchTimeout)
						defer cancel()
						delta, deltaErr := researchClient.ChartOverlayDelta(ctx, key)
						if deltaErr != nil {
							logger.Warn("chart overlay delta unavailable", "key", key, "error", deltaErr)
							return
						}
						hub.PublishOverlay(key, sequence, delta)
					}(key, sequence)
				}
			},
			BBO: hub.PublishBBO, ScopedStatus: hub.PublishStatusForMarkets,
		},
	)
	if serviceErr != nil {
		logger.Error("market gateway configuration failed", "error", serviceErr)
		os.Exit(1)
	}
	edgeHandler.SetMarketGateway(postgresadapter.NewStore(marketPool.Pool), marketService)
	marketSubscription, err = marketService.Start(runtimeCtx)
	if err != nil {
		logger.Error("market gateway failed to start", "error", err)
		os.Exit(1)
	}
	edgeHandler.SetMarketStreamHandler(hub)

	handler := httpapi.NewRouter(edgeHandler)

	server := &http.Server{
		Addr:              ":" + cfg.Port,
		Handler:           handler,
		ReadHeaderTimeout: 5 * time.Second,
		IdleTimeout:       60 * time.Second,
	}

	serverErrors := make(chan error, 1)
	go func() {
		logger.Info(
			"api server listening",
			"addr", server.Addr,
			"research_service_url", cfg.ResearchServiceURL,
		)
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
		if marketSubscription != nil {
			_ = marketSubscription.Close()
		}
		ctx, cancel := context.WithTimeout(context.Background(), cfg.ShutdownTimeout)
		defer cancel()

		if err := server.Shutdown(ctx); err != nil {
			logger.Error("graceful shutdown failed", "error", err)
			os.Exit(1)
		}
	}
}
