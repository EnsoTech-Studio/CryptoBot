package httpapi

import (
	"bufio"
	"context"
	"crypto/sha1"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/EnsoTech-Studio/CryptoBot/server/internal/lab"
)

const maxRequestBodySize = 1 << 20

type Handler struct {
	app            *lab.App
	allowedOrigins map[string]struct{}
}

func NewHandler(app *lab.App, allowedOrigins []string) *Handler {
	origins := make(map[string]struct{}, len(allowedOrigins))
	for _, origin := range allowedOrigins {
		origin = strings.TrimSpace(origin)
		if origin != "" {
			origins[origin] = struct{}{}
		}
	}
	return &Handler{app: app, allowedOrigins: origins}
}

func NewRouter(handler *Handler) http.Handler {
	mux := http.NewServeMux()

	mux.HandleFunc("/health", handler.health)
	mux.HandleFunc("/ready", handler.ready)
	mux.HandleFunc("/metrics", handler.metrics)

	mux.HandleFunc("/api/v1/auth/register", handler.register)
	mux.HandleFunc("/api/v1/auth/login", handler.login)
	mux.HandleFunc("/api/v1/auth/logout", handler.logout)
	mux.HandleFunc("/api/v1/auth/me", handler.me)

	mux.HandleFunc("/api/v1/markets/pairs", handler.marketPairs)
	mux.HandleFunc("/api/v1/markets/candles", handler.marketCandles)
	mux.HandleFunc("/api/v1/markets/chart-overlays", handler.chartOverlays)
	mux.HandleFunc("/api/v1/markets/status", handler.marketStatus)
	mux.HandleFunc("/api/v1/markets/stream", handler.marketStream)
	mux.HandleFunc("/api/v1/strategies", handler.strategies)
	mux.HandleFunc("/api/v1/experiments", handler.experiments)
	mux.HandleFunc("/api/v1/experiments/", handler.experimentByID)
	mux.HandleFunc("/api/v1/search-runs", handler.searchRuns)
	mux.HandleFunc("/api/v1/search-runs/", handler.searchRunByID)
	mux.HandleFunc("/api/v1/leaderboard", handler.leaderboard)
	mux.HandleFunc("/api/v1/leaderboard/", handler.leaderboardByID)
	mux.HandleFunc("/api/v1/news", handler.news)
	mux.HandleFunc("/api/v1/news/aggregate", handler.newsAggregate)
	mux.HandleFunc("/api/v1/ai/predict", handler.predict)
	mux.HandleFunc("/internal/events", handler.internalEvents)

	return handler.withCORS(mux)
}

func (h *Handler) health(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodGet) { return }
	writeJSON(w, http.StatusOK, h.app.Health())
}

func (h *Handler) ready(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodGet) { return }
	payload, status := h.app.Ready(r.Context())
	writeJSON(w, status, payload)
}

func (h *Handler) metrics(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodGet) { return }
	principal, ok := h.requireAuth(w, r)
	if !ok { return }
	if principal.Role != "OPERATOR" && principal.Role != "ADMIN" {
		writeError(w, http.StatusForbidden, "forbidden", "Metrics require OPERATOR or ADMIN")
		return
	}
	w.Header().Set("Content-Type", "text/plain; version=0.0.4")
	_, _ = w.Write([]byte(h.app.Metrics(r.Context())))
}

func (h *Handler) register(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodPost) { return }
	var body struct {
		Email       string `json:"email"`
		Password    string `json:"password"`
		DisplayName string `json:"display_name"`
	}
	if err := readJSON(r, &body); err != nil { writeError(w, http.StatusBadRequest, "invalid_json", err.Error()); return }
	principal, err := lab.RegisterUser(r.Context(), h.app.DB, body.Email, body.Password, body.DisplayName)
	if err != nil { writeError(w, http.StatusConflict, "registration_failed", "Email is invalid or already registered"); return }
	h.issueCookies(w, principal)
	writeJSON(w, http.StatusCreated, map[string]any{"user": principal})
}

func (h *Handler) login(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodPost) { return }
	var body struct {
		Email    string `json:"email"`
		Password string `json:"password"`
	}
	if err := readJSON(r, &body); err != nil { writeError(w, http.StatusBadRequest, "invalid_json", err.Error()); return }
	principal, err := lab.Authenticate(r.Context(), h.app.DB, body.Email, body.Password)
	if err != nil { writeError(w, http.StatusUnauthorized, "invalid_credentials", "Invalid email or password"); return }
	h.issueCookies(w, principal)
	writeJSON(w, http.StatusOK, map[string]any{"user": principal})
}

func (h *Handler) logout(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodPost) { return }
	clearCookie(w, "access_token", true)
	clearCookie(w, "csrf_token", false)
	writeJSON(w, http.StatusOK, map[string]any{"status": "logged_out"})
}

func (h *Handler) me(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodGet) { return }
	p, ok := h.requireAuth(w, r)
	if !ok { return }
	writeJSON(w, http.StatusOK, map[string]any{"user": p})
}

func (h *Handler) marketPairs(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodGet) { return }
	pairs, err := h.app.MarketPairs(r.Context())
	if err != nil { writeError(w, http.StatusInternalServerError, "market_pairs_unavailable", err.Error()); return }
	writeJSON(w, http.StatusOK, map[string]any{"pairs": pairs})
}

func (h *Handler) marketCandles(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodGet) { return }
	limit := intQuery(r, "limit", 180)
	if limit > 1000 {
		writeError(w, http.StatusUnprocessableEntity, "range_too_large", "Candles response is limited to 1000 rows")
		return
	}
	candles, err := h.app.Candles(r.Context(), q(r, "provider", lab.ProviderBinance), q(r, "symbol", lab.SymbolETHUSDT), q(r, "timeframe", "5m"), limit)
	if err != nil { writeError(w, http.StatusBadGateway, "market_data_unavailable", err.Error()); return }
	writeJSON(w, http.StatusOK, map[string]any{"candles": candles, "limit_applied": limit})
}

func (h *Handler) chartOverlays(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodGet) { return }
	payload, err := h.app.ChartOverlayPayload(r.Context(), q(r, "provider", lab.ProviderBinance), q(r, "symbol", lab.SymbolETHUSDT), q(r, "timeframe", "5m"), q(r, "strategy", "composite@1.0.0"), intQuery(r, "limit", 180))
	if err != nil { writeError(w, http.StatusBadGateway, "overlay_unavailable", err.Error()); return }
	writeJSON(w, http.StatusOK, payload)
}

func (h *Handler) marketStatus(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodGet) { return }
	writeJSON(w, http.StatusOK, map[string]any{"provider": lab.ProviderBinance, "symbol": lab.SymbolETHUSDT, "stale": false, "last_closed_at": time.Now().UTC(), "reconnect_count": 0})
}

func (h *Handler) strategies(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodGet) { return }
	strategies, err := h.app.Strategies(r.Context())
	if err != nil { writeError(w, http.StatusInternalServerError, "strategies_unavailable", err.Error()); return }
	writeJSON(w, http.StatusOK, map[string]any{"strategies": strategies})
}

func (h *Handler) experiments(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodPost) { return }
	principal, ok := h.requireCommandAuth(w, r)
	if !ok { return }
	var req lab.ExperimentRequest
	if err := readJSON(r, &req); err != nil { writeError(w, http.StatusBadRequest, "invalid_json", err.Error()); return }
	accepted, err := h.app.CreateExperiment(r.Context(), principal.ID, req)
	if err != nil { writeError(w, http.StatusUnprocessableEntity, "experiment_rejected", err.Error()); return }
	status := http.StatusAccepted
	if accepted.Reused { status = http.StatusOK }
	writeJSON(w, status, accepted)
}

func (h *Handler) experimentByID(w http.ResponseWriter, r *http.Request) {
	path := strings.TrimPrefix(r.URL.Path, "/api/v1/experiments/")
	parts := strings.Split(strings.Trim(path, "/"), "/")
	if len(parts) == 0 || parts[0] == "" { writeError(w, http.StatusNotFound, "not_found", "Experiment not found"); return }
	principal, ok := h.requireAuth(w, r)
	if !ok { return }
	id := parts[0]
	if len(parts) == 1 {
		if !allowMethod(w, r, http.MethodGet) { return }
		summary, err := h.app.ExperimentSummary(r.Context(), id, &principal)
		if err != nil { writeError(w, http.StatusNotFound, "not_found", "Experiment not found"); return }
		writeJSON(w, http.StatusOK, summary)
		return
	}
	if !allowMethod(w, r, http.MethodGet) { return }
	if _, err := h.app.ExperimentSummary(r.Context(), id, &principal); err != nil {
		writeError(w, http.StatusNotFound, "not_found", "Experiment not found")
		return
	}
	switch parts[1] {
	case "candles":
		candles, err := h.app.ExperimentCandles(r.Context(), id)
		if err != nil { writeError(w, http.StatusNotFound, "not_found", "Experiment not found"); return }
		writeJSON(w, http.StatusOK, map[string]any{"candles": candles})
	case "trades":
		trades, err := h.app.ExperimentTrades(r.Context(), id)
		if err != nil { writeError(w, http.StatusInternalServerError, "trades_unavailable", err.Error()); return }
		writeJSON(w, http.StatusOK, map[string]any{"trades": trades})
	case "equity":
		equity, err := h.app.ExperimentEquity(r.Context(), id)
		if err != nil { writeError(w, http.StatusInternalServerError, "equity_unavailable", err.Error()); return }
		writeJSON(w, http.StatusOK, equity)
	case "overlays":
		overlays, err := h.app.ExperimentOverlays(r.Context(), id)
		if err != nil { writeError(w, http.StatusInternalServerError, "overlays_unavailable", err.Error()); return }
		writeJSON(w, http.StatusOK, overlays)
	default:
		writeError(w, http.StatusNotFound, "not_found", "Experiment resource not found")
	}
}

func (h *Handler) searchRuns(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodPost) { return }
	principal, ok := h.requireCommandAuth(w, r)
	if !ok { return }
	var req lab.SearchRunRequest
	if err := readJSON(r, &req); err != nil { writeError(w, http.StatusBadRequest, "invalid_json", err.Error()); return }
	id, err := lab.CreateSearchRun(r.Context(), h.app.DB, principal.ID, req)
	if err != nil { writeError(w, http.StatusUnprocessableEntity, "search_rejected", err.Error()); return }
	writeJSON(w, http.StatusAccepted, map[string]any{"search_run_id": id})
}

func (h *Handler) searchRunByID(w http.ResponseWriter, r *http.Request) {
	path := strings.TrimPrefix(r.URL.Path, "/api/v1/search-runs/")
	parts := strings.Split(strings.Trim(path, "/"), "/")
	if len(parts) == 0 || parts[0] == "" { writeError(w, http.StatusNotFound, "not_found", "Search run not found"); return }
	principal, ok := h.requireAuth(w, r)
	if !ok { return }
	if len(parts) == 1 {
		if !allowMethod(w, r, http.MethodGet) { return }
		run, err := h.app.SearchRun(r.Context(), parts[0], &principal)
		if err != nil { writeError(w, http.StatusNotFound, "not_found", "Search run not found"); return }
		writeJSON(w, http.StatusOK, run)
		return
	}
	if parts[1] == "actions" {
		if !allowMethod(w, r, http.MethodPost) { return }
		if !h.requireCSRF(w, r) { return }
		var body struct {
			Action    string `json:"action"`
			CommandID string `json:"command_id"`
		}
		if err := readJSON(r, &body); err != nil { writeError(w, http.StatusBadRequest, "invalid_json", err.Error()); return }
		payload, status := h.app.SearchAction(r.Context(), parts[0], principal, body.Action, body.CommandID)
		writeJSON(w, status, payload)
		return
	}
	writeError(w, http.StatusNotFound, "not_found", "Search run resource not found")
}

func (h *Handler) leaderboard(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodGet) { return }
	entries, err := h.app.Leaderboard(r.Context(), intQuery(r, "limit", 10), r.URL.Query().Get("sort_by"))
	if err != nil { writeError(w, http.StatusInternalServerError, "leaderboard_unavailable", err.Error()); return }
	writeJSON(w, http.StatusOK, map[string]any{"entries": entries, "limit_applied": len(entries)})
}

func (h *Handler) leaderboardByID(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodGet) { return }
	path := strings.TrimPrefix(r.URL.Path, "/api/v1/leaderboard/")
	parts := strings.Split(strings.Trim(path, "/"), "/")
	if len(parts) >= 2 && parts[1] == "provenance" {
		payload, err := h.app.Provenance(r.Context(), parts[0])
		if err != nil { writeError(w, http.StatusNotFound, "not_found", "Leaderboard entry not found"); return }
		writeJSON(w, http.StatusOK, payload)
		return
	}
	writeError(w, http.StatusNotFound, "not_found", "Leaderboard resource not found")
}

func (h *Handler) news(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/api/v1/news" { h.newsAggregate(w, r); return }
	if !allowMethod(w, r, http.MethodGet) { return }
	payload, err := h.app.News(r.Context())
	if err != nil { writeError(w, http.StatusInternalServerError, "news_unavailable", err.Error()); return }
	writeJSON(w, http.StatusOK, payload)
}

func (h *Handler) newsAggregate(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodGet) { return }
	payload, err := h.app.NewsAggregate(r.Context())
	if err != nil { writeError(w, http.StatusInternalServerError, "news_aggregate_unavailable", err.Error()); return }
	writeJSON(w, http.StatusOK, payload)
}

func (h *Handler) predict(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodPost) { return }
	if _, ok := h.requireCommandAuth(w, r); !ok { return }
	var body struct { Text string `json:"text"` }
	if err := readJSON(r, &body); err != nil { writeError(w, http.StatusBadRequest, "invalid_json", err.Error()); return }
	if strings.TrimSpace(body.Text) == "" || len(body.Text) > 10000 {
		writeError(w, http.StatusUnprocessableEntity, "invalid_text", "Text must be 1-10000 characters")
		return
	}
	payload, status := h.app.Predict(r.Context(), body.Text)
	writeJSON(w, status, payload)
}

func (h *Handler) internalEvents(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodPost) { return }
	writeJSON(w, http.StatusAccepted, map[string]any{"status": "accepted"})
}

func (h *Handler) marketStream(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		methodNotAllowed(w, http.MethodGet)
		return
	}
	conn, rw, err := acceptWebSocket(w, r)
	if err != nil {
		return
	}
	defer conn.Close()
	key := fmt.Sprintf("%s|%s|5m|composite@1.0.0|sha256:%s", lab.ProviderBinance, lab.SymbolETHUSDT, strings.Repeat("4", 64))
	_ = conn.SetReadDeadline(time.Now().Add(8 * time.Second))
	if payload, err := readWSFrame(rw); err == nil {
		var msg map[string]any
		if json.Unmarshal(payload, &msg) == nil {
			if k, ok := msg["key"].(string); ok && k != "" { key = k }
			ack, _ := json.Marshal(map[string]any{"type": "subscribed", "key": key, "req": msg["req"], "seq": time.Now().Unix()})
			_ = writeWSFrame(conn, ack)
		}
	}
	_ = conn.SetReadDeadline(time.Time{})
	ticker := time.NewTicker(3 * time.Second)
	defer ticker.Stop()
	for {
		select {
		case <-r.Context().Done():
			return
		case <-ticker.C:
			kline, delta, err := h.app.LatestKlinePayload(context.Background(), key)
			if err != nil { continue }
			data, _ := json.Marshal(kline)
			if err := writeWSFrame(conn, data); err != nil { return }
			data, _ = json.Marshal(delta)
			if err := writeWSFrame(conn, data); err != nil { return }
		}
	}
}

func (h *Handler) issueCookies(w http.ResponseWriter, p lab.Principal) {
	token, _ := h.app.Signer.Issue(p, 15*time.Minute)
	csrf := lab.NewCSRFToken()
	http.SetCookie(w, &http.Cookie{Name: "access_token", Value: token, Path: "/api/v1", HttpOnly: true, SameSite: http.SameSiteStrictMode, MaxAge: 900})
	http.SetCookie(w, &http.Cookie{Name: "csrf_token", Value: csrf, Path: "/", HttpOnly: false, SameSite: http.SameSiteStrictMode, MaxAge: 900})
}

func (h *Handler) requireAuth(w http.ResponseWriter, r *http.Request) (lab.Principal, bool) {
	cookie, err := r.Cookie("access_token")
	if err != nil || cookie.Value == "" {
		writeError(w, http.StatusUnauthorized, "unauthorized", "Login is required")
		return lab.Principal{}, false
	}
	p, err := h.app.Signer.Verify(cookie.Value)
	if err != nil {
		writeError(w, http.StatusUnauthorized, "unauthorized", "Session is invalid or expired")
		return lab.Principal{}, false
	}
	return p, true
}

func (h *Handler) requireCommandAuth(w http.ResponseWriter, r *http.Request) (lab.Principal, bool) {
	p, ok := h.requireAuth(w, r)
	if !ok { return p, false }
	if !h.requireCSRF(w, r) { return p, false }
	return p, true
}

func (h *Handler) requireCSRF(w http.ResponseWriter, r *http.Request) bool {
	cookie, err := r.Cookie("csrf_token")
	if err != nil || cookie.Value == "" || r.Header.Get("X-CSRF-Token") != cookie.Value {
		writeError(w, http.StatusForbidden, "csrf_failed", "Missing or invalid CSRF token")
		return false
	}
	return true
}

func (h *Handler) withCORS(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		origin := r.Header.Get("Origin")
		if _, ok := h.allowedOrigins[origin]; ok {
			w.Header().Set("Access-Control-Allow-Origin", origin)
			w.Header().Set("Access-Control-Allow-Credentials", "true")
			w.Header().Set("Access-Control-Allow-Headers", "Content-Type, X-CSRF-Token")
			w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		}
		w.Header().Set("Vary", "Origin")
		w.Header().Set("X-Content-Type-Options", "nosniff")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func readJSON(r *http.Request, target any) error {
	defer r.Body.Close()
	data, err := io.ReadAll(io.LimitReader(r.Body, maxRequestBodySize+1))
	if err != nil {
		return err
	}
	if len(data) > maxRequestBodySize {
		return fmt.Errorf("payload_too_large")
	}
	return json.Unmarshal(data, target)
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}

func writeError(w http.ResponseWriter, status int, code, message string) {
	writeJSON(w, status, map[string]any{"error": map[string]any{"code": code, "message": message, "request_id": "req_" + strconv.FormatInt(time.Now().UnixNano(), 36)}})
}

func allowMethod(w http.ResponseWriter, r *http.Request, method string) bool {
	if r.Method != method {
		methodNotAllowed(w, method)
		return false
	}
	return true
}

func methodNotAllowed(w http.ResponseWriter, allowed string) {
	w.Header().Set("Allow", allowed)
	writeError(w, http.StatusMethodNotAllowed, "method_not_allowed", "Method not allowed")
}

func q(r *http.Request, key, fallback string) string {
	if value := strings.TrimSpace(r.URL.Query().Get(key)); value != "" { return value }
	return fallback
}

func intQuery(r *http.Request, key string, fallback int) int {
	value, err := strconv.Atoi(r.URL.Query().Get(key))
	if err != nil || value <= 0 { return fallback }
	return value
}

func clearCookie(w http.ResponseWriter, name string, httpOnly bool) {
	path := "/api/v1"
	if name == "csrf_token" { path = "/" }
	http.SetCookie(w, &http.Cookie{Name: name, Value: "", Path: path, HttpOnly: httpOnly, SameSite: http.SameSiteStrictMode, MaxAge: -1})
}

func acceptWebSocket(w http.ResponseWriter, r *http.Request) (net.Conn, *bufio.ReadWriter, error) {
	if !strings.EqualFold(r.Header.Get("Upgrade"), "websocket") {
		writeError(w, http.StatusUpgradeRequired, "upgrade_required", "WebSocket upgrade required")
		return nil, nil, errors.New("not websocket")
	}
	key := r.Header.Get("Sec-WebSocket-Key")
	if key == "" {
		writeError(w, http.StatusBadRequest, "invalid_websocket", "Missing Sec-WebSocket-Key")
		return nil, nil, errors.New("missing key")
	}
	hijacker, ok := w.(http.Hijacker)
	if !ok {
		writeError(w, http.StatusInternalServerError, "websocket_unavailable", "Response writer cannot hijack")
		return nil, nil, errors.New("hijack unavailable")
	}
	conn, rw, err := hijacker.Hijack()
	if err != nil { return nil, nil, err }
	accept := websocketAccept(key)
	_, _ = fmt.Fprintf(conn, "HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: %s\r\n\r\n", accept)
	return conn, rw, nil
}

func websocketAccept(key string) string {
	sum := sha1.Sum([]byte(key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"))
	return base64.StdEncoding.EncodeToString(sum[:])
}

func readWSFrame(rw *bufio.ReadWriter) ([]byte, error) {
	header := make([]byte, 2)
	if _, err := io.ReadFull(rw, header); err != nil { return nil, err }
	length := int(header[1] & 0x7f)
	if length == 126 {
		ext := make([]byte, 2)
		if _, err := io.ReadFull(rw, ext); err != nil { return nil, err }
		length = int(binary.BigEndian.Uint16(ext))
	} else if length == 127 {
		ext := make([]byte, 8)
		if _, err := io.ReadFull(rw, ext); err != nil { return nil, err }
		length = int(binary.BigEndian.Uint64(ext))
	}
	masked := header[1]&0x80 != 0
	mask := make([]byte, 4)
	if masked {
		if _, err := io.ReadFull(rw, mask); err != nil { return nil, err }
	}
	payload := make([]byte, length)
	if _, err := io.ReadFull(rw, payload); err != nil { return nil, err }
	if masked {
		for i := range payload { payload[i] ^= mask[i%4] }
	}
	return payload, nil
}

func writeWSFrame(conn net.Conn, payload []byte) error {
	header := []byte{0x81}
	if len(payload) < 126 {
		header = append(header, byte(len(payload)))
	} else if len(payload) <= 65535 {
		header = append(header, 126, byte(len(payload)>>8), byte(len(payload)))
	} else {
		header = append(header, 127, 0, 0, 0, 0, byte(len(payload)>>24), byte(len(payload)>>16), byte(len(payload)>>8), byte(len(payload)))
	}
	if _, err := conn.Write(header); err != nil { return err }
	_, err := conn.Write(payload)
	return err
}
