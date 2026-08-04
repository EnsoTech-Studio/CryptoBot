package config

import (
	"os"
	"strings"
	"time"
)

type Config struct {
	Port            string
	AIServiceURL    string
	CORSOrigin      string
	ShutdownTimeout time.Duration
}

func Load() Config {
	return Config{
		Port:            envOrDefault("PORT", "8080"),
		AIServiceURL:    strings.TrimRight(envOrDefault("AI_SERVICE_URL", "http://localhost:8000"), "/"),
		CORSOrigin:      envOrDefault("CORS_ORIGIN", "http://localhost:3000"),
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
