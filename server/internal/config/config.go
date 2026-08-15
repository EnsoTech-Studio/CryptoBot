package config

import (
	"os"
	"strings"
	"time"
)

type Config struct {
	Port            string
	AIServiceURL    string
	DatabaseURL     string
	CORSAllowedOrigins []string
	ShutdownTimeout time.Duration
}

func Load() Config {
	return Config{
		Port:            envOrDefault("PORT", "8080"),
		AIServiceURL:    strings.TrimRight(envOrDefault("AI_SERVICE_URL", "http://localhost:8000"), "/"),
		DatabaseURL:     envOrDefault("DATABASE_URL", "postgres://cryptobot:cryptobot@localhost:5432/cryptobot?sslmode=disable"),
		CORSAllowedOrigins: splitCSV(envOrDefault("CORS_ALLOWED_ORIGINS", envOrDefault("CORS_ORIGIN", "http://localhost:3000"))),
		ShutdownTimeout: durationOrDefault("SHUTDOWN_TIMEOUT", 10*time.Second),
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
