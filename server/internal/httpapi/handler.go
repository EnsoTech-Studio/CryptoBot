package httpapi

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"strings"
	"time"
)

const maxRequestBodySize = 1 << 20

type Handler struct {
	aiServiceURL string
	client       *http.Client
}

func NewHandler(aiServiceURL string, client *http.Client) *Handler {
	if client == nil {
		client = http.DefaultClient
	}

	return &Handler{
		aiServiceURL: strings.TrimRight(aiServiceURL, "/"),
		client:       client,
	}
}

func NewRouter(handler *Handler, corsOrigin string) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/health", handler.Health)
	mux.HandleFunc("/api/v1/health", handler.Health)
	mux.HandleFunc("/api/v1/ai/predict", handler.Predict)

	return withCORS(corsOrigin, mux)
}

func (h *Handler) Health(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		methodNotAllowed(w, http.MethodGet)
		return
	}

	writeJSON(w, http.StatusOK, map[string]any{
		"status":  "ok",
		"service": "api",
		"time":    time.Now().UTC(),
	})
}

func (h *Handler) Predict(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		methodNotAllowed(w, http.MethodPost)
		return
	}

	r.Body = http.MaxBytesReader(w, r.Body, maxRequestBodySize)
	body, err := io.ReadAll(r.Body)
	if err != nil {
		writeError(w, http.StatusBadRequest, "request body is invalid or too large")
		return
	}
	if len(bytes.TrimSpace(body)) == 0 {
		writeError(w, http.StatusBadRequest, "request body is required")
		return
	}

	upstream, err := http.NewRequestWithContext(
		r.Context(),
		http.MethodPost,
		h.aiServiceURL+"/predict",
		bytes.NewReader(body),
	)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "AI service URL is invalid")
		return
	}

	contentType := r.Header.Get("Content-Type")
	if contentType == "" {
		contentType = "application/json"
	}
	upstream.Header.Set("Content-Type", contentType)

	response, err := h.client.Do(upstream)
	if err != nil {
		writeError(w, http.StatusBadGateway, "AI service is unavailable")
		return
	}
	defer response.Body.Close()

	if contentType := response.Header.Get("Content-Type"); contentType != "" {
		w.Header().Set("Content-Type", contentType)
	}
	w.WriteHeader(response.StatusCode)
	_, _ = io.Copy(w, response.Body)
}

func withCORS(origin string, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", origin)
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		w.Header().Set("Vary", "Origin")

		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}

		next.ServeHTTP(w, r)
	})
}

func methodNotAllowed(w http.ResponseWriter, allowed string) {
	w.Header().Set("Allow", allowed)
	writeError(w, http.StatusMethodNotAllowed, "method not allowed")
}

func writeError(w http.ResponseWriter, status int, message string) {
	writeJSON(w, status, map[string]string{"error": message})
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}
