package config

import "time"

type Config struct {
	Port               string
	AIServiceURL       string
	CORSAllowedOrigins []string
	ShutdownTimeout    time.Duration
}

// Load is a configuration seam. Environment decoding will be completed with
// the API transport phase; CORS_ALLOWED_ORIGINS is canonical.
func Load() Config {
	return Config{Port: "8080", AIServiceURL: "http://ai:8000", CORSAllowedOrigins: []string{"http://localhost:3000"}, ShutdownTimeout: 10 * time.Second}
}
