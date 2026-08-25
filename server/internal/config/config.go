package config

import (
	"fmt"
	"os"
	"strings"
	"time"
)

type Config struct {
	Port                    string
	ResearchServiceURL      string
	InternalServiceToken    string
	CORSAllowedOrigins      []string
	ShutdownTimeout         time.Duration
	ResearchTimeout         time.Duration
	ResearchMaxBodyBytes    int64
	MarketDatabaseURL       string
	JWTPrivateKeyFile       string
	CookieSecure            bool
}

func Load() Config {
	return Config{
		Port:                    envOrDefault("PORT", "8080"),
		ResearchServiceURL:      strings.TrimRight(envOrDefault("RESEARCH_SERVICE_URL", "http://localhost:8001"), "/"),
		InternalServiceToken:    envOrDefault("INTERNAL_SERVICE_TOKEN", "development-internal-token"),
		CORSAllowedOrigins:      splitCSV(envOrDefault("CORS_ALLOWED_ORIGINS", envOrDefault("CORS_ORIGIN", "http://localhost:3000"))),
		ShutdownTimeout:         durationOrDefault("SHUTDOWN_TIMEOUT", 10*time.Second),
		ResearchTimeout:         durationOrDefault("RESEARCH_REQUEST_TIMEOUT", 15*time.Second),
		ResearchMaxBodyBytes:    int64OrDefault("RESEARCH_MAX_BODY_BYTES", 4<<20),
		MarketDatabaseURL:       envOrDefault("MARKET_DATABASE_URL", envOrDefault("DATABASE_URL", "postgres://cryptobot:cryptobot@localhost:5432/cryptobot?sslmode=disable")),
		JWTPrivateKeyFile:       envOrDefault("JWT_PRIVATE_KEY_FILE", ".runtime/jwt-private.pem"),
		CookieSecure:            boolOrDefault("COOKIE_SECURE", false),
	}
}

func envOrDefault(key, fallback string) string {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback
	}
	return value
}

func durationOrDefault(key string, fallback time.Duration) time.Duration {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback
	}

	duration, err := time.ParseDuration(value)
	if err != nil || duration <= 0 {
		return fallback
	}
	return duration
}

func splitCSV(value string) []string {
	parts := strings.Split(value, ",")
	out := make([]string, 0, len(parts))
	for _, part := range parts {
		part = strings.TrimSpace(part)
		if part != "" {
			out = append(out, part)
		}
	}
	if len(out) == 0 {
		return []string{"http://localhost:3000"}
	}
	return out
}

func int64OrDefault(key string, fallback int64) int64 {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback
	}
	var parsed int64
	if _, err := fmt.Sscan(value, &parsed); err != nil || parsed <= 0 {
		return fallback
	}
	return parsed
}

func boolOrDefault(key string, fallback bool) bool {
	value := strings.TrimSpace(strings.ToLower(os.Getenv(key)))
	switch value {
	case "1", "true", "yes", "on":
		return true
	case "0", "false", "no", "off":
		return false
	default:
		return fallback
	}
}
