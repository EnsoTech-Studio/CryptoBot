package httpapi

import (
	"context"
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strconv"
	"strings"
	"sync"
	"time"

	authservice "github.com/EnsoTech-Studio/CryptoBot/server/internal/auth"
	"github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/common"
	domainmarket "github.com/EnsoTech-Studio/CryptoBot/server/internal/domain/market"
	researchclient "github.com/EnsoTech-Studio/CryptoBot/server/internal/infrastructure/research"
)

const maxRequestBodySize = 1 << 20

type Handler struct {
	research            *researchclient.Client
	allowedOrigins      map[string]struct{}
	marketStreamHandler http.Handler
	marketReader        marketReader
	datasetCreator      datasetCreator
	authService         *authservice.Service
	authLimiter         *authservice.Limiter
	commandLimiter      *authservice.Limiter
	secureCookies       bool
	metricsMu           sync.Mutex
	requestCounts       map[int]uint64
	requestDuration     time.Duration
}

type marketReader interface {
	Ready(context.Context) error
	ListPairs(context.Context) ([]domainmarket.Pair, error)
	ListCandles(context.Context, domainmarket.MarketKey, int) ([]domainmarket.Candle, error)
	ListDatasets(context.Context, domainmarket.MarketKey, int) ([]domainmarket.Dataset, error)
	LoadCheckpoint(context.Context, domainmarket.MarketKey) (domainmarket.Checkpoint, error)
}

type datasetCreator interface {
	CreateDataset(context.Context, domainmarket.MarketKey, time.Time, time.Time, int) (domainmarket.Dataset, error)
}

func (h *Handler) SetMarketStreamHandler(handler http.Handler) {
	h.marketStreamHandler = handler
}

func (h *Handler) SetMarketGateway(reader marketReader, creator datasetCreator) {
	h.marketReader = reader
	h.datasetCreator = creator
}

func (h *Handler) SetAuthService(service *authservice.Service, secureCookies bool) {
	h.authService = service
	h.authLimiter = authservice.NewLimiter(10, time.Minute)
	h.commandLimiter = authservice.NewLimiter(60, time.Minute)
	h.secureCookies = secureCookies
}

func NewHandler(allowedOrigins []string) *Handler {
	origins := make(map[string]struct{}, len(allowedOrigins))
	for _, origin := range allowedOrigins {
		origin = strings.TrimSpace(origin)
		if origin != "" {
			origins[origin] = struct{}{}
		}
	}
	return &Handler{allowedOrigins: origins, requestCounts: make(map[int]uint64)}
}

func NewHandlerWithResearch(
	allowedOrigins []string,
	client *researchclient.Client,
) *Handler {
	handler := NewHandler(allowedOrigins)
	handler.research = client
	return handler
}

func (h *Handler) callResearch(
	w http.ResponseWriter,
	r *http.Request,
	method string,
	path string,
	body any,
	principal *principal,
) bool {
	if h.research == nil {
		writeError(w, http.StatusBadGateway, "research_unavailable", "Research service is unavailable")
		return false
	}
	userID, userRole := "", ""
	if principal != nil {
		userID, userRole = principal.ID, principal.Role
	}
	response, err := h.research.CallWithMetadata(
		r.Context(), method, path, r.URL.Query(), body,
		r.Header.Get("X-Request-ID"), userID, userRole,
		r.Header.Get("Idempotency-Key"), r.Header.Get("X-Correlation-ID"),
	)
	if err != nil {
		writeError(w, http.StatusBadGateway, "research_unavailable", "Research service is unavailable")
		return false
	}
	contentType := response.ContentType
	if contentType == "" {
		contentType = "application/json"
	}
	w.Header().Set("Content-Type", contentType)
	if response.ContentDisposition != "" {
		w.Header().Set("Content-Disposition", response.ContentDisposition)
	}
	w.WriteHeader(response.StatusCode)
	_, _ = w.Write(response.Body)
	return true
}

func (h *Handler) streamResearch(w http.ResponseWriter, r *http.Request, path string, principal *principal) bool {
	if h.research == nil {
		writeError(w, http.StatusBadGateway, "research_unavailable", "Research service is unavailable")
		return false
	}
	userID, userRole := "", ""
	if principal != nil {
		userID, userRole = principal.ID, principal.Role
	}
	response, err := h.research.StreamWithMetadata(
		r.Context(), http.MethodGet, path, r.URL.Query(), r.Header.Get("X-Request-ID"), userID, userRole, r.Header.Get("X-Correlation-ID"),
	)
	if err != nil {
		writeError(w, http.StatusBadGateway, "research_unavailable", "Research service is unavailable")
		return false
	}
	defer response.Body.Close()
	contentType := response.ContentType
	if contentType == "" {
		contentType = "application/octet-stream"
	}
	w.Header().Set("Content-Type", contentType)
	if response.ContentDisposition != "" {
		w.Header().Set("Content-Disposition", response.ContentDisposition)
	}
	w.WriteHeader(response.StatusCode)
	_, _ = io.Copy(w, response.Body)
	return true
}

func NewRouter(handler *Handler) http.Handler {
	mux := http.NewServeMux()

	mux.HandleFunc("/health", handler.health)
	mux.HandleFunc("/ready", handler.ready)
	mux.HandleFunc("/metrics", handler.metrics)

	mux.HandleFunc("/api/v1/auth/register", handler.register)
	mux.HandleFunc("/api/v1/auth/login", handler.login)
	mux.HandleFunc("/api/v1/auth/refresh", handler.refresh)
	mux.HandleFunc("/api/v1/auth/logout", handler.logout)
	mux.HandleFunc("/api/v1/auth/me", handler.me)

	mux.HandleFunc("/api/v1/markets/pairs", handler.marketPairs)
	mux.HandleFunc("/api/v1/markets/candles", handler.marketCandles)
	mux.HandleFunc("/api/v1/markets/datasets", handler.marketDatasets)
	mux.HandleFunc("/api/v1/markets/chart-overlays", handler.chartOverlays)
	mux.HandleFunc("/api/v1/markets/status", handler.marketStatus)
	mux.HandleFunc("/api/v1/markets/stream", handler.marketStream)
	mux.HandleFunc("/api/v1/strategies", handler.strategies)
	mux.HandleFunc("/api/v1/strategy-drafts", handler.strategyDrafts)
	mux.HandleFunc("/api/v1/strategy-drafts/", handler.strategyDraftByID)
	mux.HandleFunc("/api/v1/experiments", handler.experiments)
	mux.HandleFunc("/api/v1/experiments/", handler.experimentByID)
	mux.HandleFunc("/api/v1/search-runs", handler.searchRuns)
	mux.HandleFunc("/api/v1/search-runs/", handler.searchRunByID)
	mux.HandleFunc("/api/v1/leaderboard", handler.leaderboard)
	mux.HandleFunc("/api/v1/leaderboard/", handler.leaderboardByID)
	mux.HandleFunc("/api/v1/news", handler.news)
	mux.HandleFunc("/api/v1/news/aggregate", handler.newsAggregate)
	mux.HandleFunc("/api/v1/admin/news/collect", handler.newsCollect)
	mux.HandleFunc("/api/v1/ai/predict", handler.predict)

	return handler.withRequestID(handler.withCORS(handler.withMetrics(mux)))
}

func (h *Handler) health(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodGet) {
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok", "service": "api"})
}

func (h *Handler) ready(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodGet) {
		return
	}
	components := map[string]bool{"database": false, "research": false, "market": false}
	if h.marketReader != nil && h.marketReader.Ready(r.Context()) == nil {
		components["database"] = true
		components["market"] = true
	}
	if h.research != nil {
		response, err := h.research.Call(
			r.Context(), http.MethodGet, "/ready", nil, nil,
			r.Header.Get("X-Request-ID"), "", "",
		)
		components["research"] = err == nil && response.StatusCode == http.StatusOK
	}
	ready := components["database"] && components["research"] && components["market"]
	status := http.StatusOK
	if !ready {
		status = http.StatusServiceUnavailable
	}
	writeJSON(w, status, map[string]any{"ready": ready, "components": components})
}

func (h *Handler) metrics(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodGet) {
		return
	}
	principal, ok := h.requireAuth(w, r)
	if !ok {
		return
	}
	if principal.Role != "OPERATOR" && principal.Role != "ADMIN" {
		writeError(w, http.StatusForbidden, "forbidden", "Metrics require OPERATOR or ADMIN")
		return
	}
	w.Header().Set("Content-Type", "text/plain; version=0.0.4")
	h.metricsMu.Lock()
	counts := make(map[int]uint64, len(h.requestCounts))
	for responseStatus, count := range h.requestCounts {
		counts[responseStatus] = count
	}
	duration := h.requestDuration.Seconds()
	h.metricsMu.Unlock()
	var output strings.Builder
	output.WriteString("# TYPE cryptobot_api_up gauge\ncryptobot_api_up 1\n")
	output.WriteString("# TYPE cryptobot_api_http_requests_total counter\n")
	for responseStatus, count := range counts {
		_, _ = fmt.Fprintf(
			&output, "cryptobot_api_http_requests_total{status=\"%d\"} %d\n",
			responseStatus, count,
		)
	}
	output.WriteString("# TYPE cryptobot_api_http_request_duration_seconds_total counter\n")
	_, _ = fmt.Fprintf(
		&output, "cryptobot_api_http_request_duration_seconds_total %.9f\n", duration,
	)
	_, _ = w.Write([]byte(output.String()))
}

func (h *Handler) register(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodPost) {
		return
	}
	var body struct {
		Email       string `json:"email"`
		Password    string `json:"password"`
		DisplayName string `json:"display_name"`
	}
	if err := readJSON(r, &body); err != nil {
		writeError(w, http.StatusBadRequest, "invalid_json", err.Error())
		return
	}
	if h.authService == nil {
		writeError(w, http.StatusServiceUnavailable, "auth_unavailable", "Authentication is unavailable")
		return
	}
	if !h.allowAuthAttempt(w, r, strings.ToLower(strings.TrimSpace(body.Email))) {
		return
	}
	principal, session, err := h.authService.Register(
		r.Context(), body.Email, body.Password, body.DisplayName,
	)
	if err != nil {
		status := http.StatusUnprocessableEntity
		if errors.Is(err, authservice.ErrEmailExists) {
			status = http.StatusConflict
		}
		writeError(w, status, "registration_failed", "Email or password is invalid")
		return
	}
	h.issueAuthCookies(w, session)
	writeJSON(w, http.StatusCreated, map[string]any{"user": principal})
}

func (h *Handler) login(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodPost) {
		return
	}
	var body struct {
		Email    string `json:"email"`
		Password string `json:"password"`
	}
	if err := readJSON(r, &body); err != nil {
		writeError(w, http.StatusBadRequest, "invalid_json", err.Error())
		return
	}
	if h.authService == nil {
		writeError(w, http.StatusServiceUnavailable, "auth_unavailable", "Authentication is unavailable")
		return
	}
	if !h.allowAuthAttempt(w, r, strings.ToLower(strings.TrimSpace(body.Email))) {
		return
	}
	principal, session, err := h.authService.Login(r.Context(), body.Email, body.Password)
	if err != nil {
		writeError(w, http.StatusUnauthorized, "invalid_credentials", "Invalid email or password")
		return
	}
	h.issueAuthCookies(w, session)
	writeJSON(w, http.StatusOK, map[string]any{"user": principal})
}

func (h *Handler) logout(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodPost) {
		return
	}
	if !h.requireCSRF(w, r) {
		return
	}
	if h.authService != nil {
		if cookie, err := r.Cookie("refresh_token"); err == nil {
			_ = h.authService.Logout(r.Context(), cookie.Value)
		}
		clearCookie(w, "refresh_token", true)
	}
	clearCookie(w, "access_token", true)
	clearCookie(w, "csrf_token", false)
	writeJSON(w, http.StatusOK, map[string]any{"status": "logged_out"})
}

func (h *Handler) refresh(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodPost) {
		return
	}
	if h.authService == nil {
		writeError(w, http.StatusServiceUnavailable, "auth_unavailable", "Authentication is unavailable")
		return
	}
	if !h.requireCSRF(w, r) {
		return
	}
	cookie, err := r.Cookie("refresh_token")
	if err != nil || cookie.Value == "" {
		writeError(w, http.StatusUnauthorized, "invalid_session", "Refresh session is missing")
		return
	}
	principal, session, err := h.authService.Rotate(r.Context(), cookie.Value)
	if err != nil {
		clearCookie(w, "access_token", true)
		clearCookie(w, "refresh_token", true)
		code := "invalid_session"
		if errors.Is(err, authservice.ErrRefreshReuse) {
			code = "refresh_reuse_detected"
		}
		writeError(w, http.StatusUnauthorized, code, "Refresh session is invalid")
		return
	}
	h.issueAuthCookies(w, session)
	writeJSON(w, http.StatusOK, map[string]any{"user": principal})
}

func (h *Handler) me(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodGet) {
		return
	}
	p, ok := h.requireAuth(w, r)
	if !ok {
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"user": p})
}

func (h *Handler) marketPairs(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodGet) {
		return
	}
	if h.marketReader == nil {
		writeError(w, http.StatusServiceUnavailable, "market_gateway_unavailable", "Market gateway is unavailable")
		return
	}
	pairs, err := h.marketReader.ListPairs(r.Context())
	if err != nil {
		writeError(w, http.StatusServiceUnavailable, "market_pairs_unavailable", "Market pairs are unavailable")
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"pairs": pairs})
}

func (h *Handler) marketCandles(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodGet) {
		return
	}
	limit := intQuery(r, "limit", 180)
	if limit > 1000 {
		writeError(w, http.StatusUnprocessableEntity, "range_too_large", "Candles response is limited to 1000 rows")
		return
	}
	provider := q(r, "provider", defaultProvider)
	symbol := q(r, "symbol", defaultSymbol)
	timeframe := q(r, "timeframe", "5m")
	if h.marketReader == nil {
		writeError(w, http.StatusServiceUnavailable, "market_gateway_unavailable", "Market gateway is unavailable")
		return
	}
	candles, err := h.marketReader.ListCandles(r.Context(), marketKey(provider, symbol, timeframe), limit)
	if err != nil {
		writeError(w, http.StatusBadGateway, "market_data_unavailable", "Market data is unavailable")
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"candles": candles, "limit_applied": limit})
}

func (h *Handler) marketDatasets(w http.ResponseWriter, r *http.Request) {
	if h.marketReader == nil {
		writeError(w, http.StatusServiceUnavailable, "market_gateway_unavailable", "Market gateway is unavailable")
		return
	}
	key := marketKey(
		q(r, "provider", defaultProvider), q(r, "symbol", defaultSymbol),
		q(r, "timeframe", "5m"),
	)
	switch r.Method {
	case http.MethodGet:
		datasets, err := h.marketReader.ListDatasets(r.Context(), key, intQuery(r, "limit", 20))
		if err != nil {
			writeError(w, http.StatusServiceUnavailable, "datasets_unavailable", "Datasets are unavailable")
			return
		}
		writeJSON(w, http.StatusOK, map[string]any{"datasets": datasets})
	case http.MethodPost:
		if _, ok := h.requireCommandAuth(w, r); !ok {
			return
		}
		if h.datasetCreator == nil {
			writeError(w, http.StatusServiceUnavailable, "dataset_creation_unavailable", "Dataset creation is unavailable")
			return
		}
		var body struct {
			Provider  string    `json:"provider"`
			Symbol    string    `json:"symbol"`
			Timeframe string    `json:"timeframe"`
			RangeFrom time.Time `json:"range_from"`
			RangeTo   time.Time `json:"range_to"`
			Revision  int       `json:"revision_no"`
		}
		if err := readJSON(r, &body); err != nil {
			writeError(w, http.StatusBadRequest, "invalid_json", err.Error())
			return
		}
		if body.Provider != "" {
			key.Provider = body.Provider
		}
		if body.Symbol != "" {
			key.Symbol = strings.ToUpper(body.Symbol)
		}
		if body.Timeframe != "" {
			key.Timeframe = common.Timeframe(body.Timeframe)
		}
		if body.RangeTo.IsZero() {
			body.RangeTo = time.Now().UTC()
		}
		if body.RangeFrom.IsZero() {
			body.RangeFrom = body.RangeTo.Add(-200 * marketTimeframeDuration(string(key.Timeframe)))
		}
		if body.Revision == 0 {
			body.Revision = 1
		}
		dataset, err := h.datasetCreator.CreateDataset(
			r.Context(), key, body.RangeFrom, body.RangeTo, body.Revision,
		)
		if err != nil {
			writeError(w, http.StatusUnprocessableEntity, "dataset_not_ready", "A complete candle and BBO window is not ready")
			return
		}
		writeJSON(w, http.StatusCreated, dataset)
	default:
		w.Header().Set("Allow", "GET, POST")
		writeError(w, http.StatusMethodNotAllowed, "method_not_allowed", "Method not allowed")
	}
}

func (h *Handler) chartOverlays(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodGet) {
		return
	}
	h.callResearch(w, r, http.MethodGet, "/api/v1/markets/chart-overlays", nil, nil)
}

func (h *Handler) marketStatus(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodGet) {
		return
	}
	if h.marketReader == nil {
		writeError(w, http.StatusServiceUnavailable, "market_gateway_unavailable", "Market gateway is unavailable")
		return
	}
	key := marketKey(q(r, "provider", defaultProvider), q(r, "symbol", defaultSymbol), q(r, "timeframe", "5m"))
	checkpoint, err := h.marketReader.LoadCheckpoint(r.Context(), key)
	if err != nil {
		writeError(w, http.StatusServiceUnavailable, "market_status_unavailable", "Market status is unavailable")
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"provider": key.Provider, "symbol": key.Symbol, "timeframe": key.Timeframe,
		"stale": marketCheckpointStale(checkpoint, string(key.Timeframe), time.Now().UTC()), "last_closed_at": checkpoint.LastClosedAt,
		"last_sequence": checkpoint.LastSourceSequence, "reconnect_count": checkpoint.ReconnectCount,
	})
}

func marketCheckpointStale(checkpoint domainmarket.Checkpoint, timeframe string, now time.Time) bool {
	if checkpoint.IsStale || checkpoint.LastClosedAt == nil {
		return true
	}
	interval := marketTimeframeDuration(timeframe)
	return now.Sub(*checkpoint.LastClosedAt) > 2*interval+time.Minute
}

func marketKey(provider, symbol, timeframe string) domainmarket.MarketKey {
	return domainmarket.MarketKey{
		Provider: provider, Symbol: strings.ToUpper(symbol), Timeframe: common.Timeframe(timeframe),
	}
}

func marketTimeframeDuration(value string) time.Duration {
	switch value {
	case "1m":
		return time.Minute
	case "5m":
		return 5 * time.Minute
	case "15m":
		return 15 * time.Minute
	case "30m":
		return 30 * time.Minute
	case "1h":
		return time.Hour
	case "2h":
		return 2 * time.Hour
	case "4h":
		return 4 * time.Hour
	case "1d":
		return 24 * time.Hour
	default:
		return 5 * time.Minute
	}
}

func (h *Handler) resolveDatasetVersion(
	ctx context.Context, provider, symbol, timeframe, current string,
) (string, error) {
	if strings.TrimSpace(current) != "" {
		return current, nil
	}
	if h.marketReader == nil {
		return "", errors.New("market dataset repository is unavailable")
	}
	datasets, err := h.marketReader.ListDatasets(ctx, marketKey(provider, symbol, timeframe), 1)
	if err != nil {
		return "", err
	}
	if len(datasets) == 0 {
		return "", errors.New("no immutable market dataset is ready")
	}
	return datasets[0].DatasetVersion, nil
}

func (h *Handler) strategies(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodGet) {
		return
	}
	h.callResearch(w, r, http.MethodGet, "/api/v1/strategies", nil, nil)
}

func (h *Handler) strategyDrafts(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodGet {
		principal, ok := h.requireAuth(w, r)
		if !ok {
			return
		}
		query := r.URL.Query()
		query.Set("owner_id", principal.ID)
		r.URL.RawQuery = query.Encode()
		h.callResearch(w, r, http.MethodGet, "/api/v1/strategy-drafts", nil, &principal)
		return
	}
	if !allowMethod(w, r, http.MethodPost) {
		return
	}
	principal, ok := h.requireCommandAuth(w, r)
	if !ok {
		return
	}
	var body strategyDraftRequest
	if err := readJSON(r, &body); err != nil {
		writeError(w, http.StatusBadRequest, "invalid_json", err.Error())
		return
	}
	if body.Mode == "" {
		body.Mode = "dsl"
	}
	if body.Source.Type == "" {
		writeError(w, http.StatusUnprocessableEntity, "invalid_source", "source.type is required")
		return
	}
	if body.IdempotencyKey != "" && r.Header.Get("Idempotency-Key") == "" {
		r.Header.Set("Idempotency-Key", body.IdempotencyKey)
	}
	h.callResearch(w, r, http.MethodPost, "/api/v1/strategy-drafts", map[string]any{
		"owner_id":        principal.ID,
		"mode":            body.Mode,
		"source":          body.Source,
		"name_hint":       body.NameHint,
		"idempotency_key": body.IdempotencyKey,
	}, &principal)
}

func (h *Handler) strategyDraftByID(w http.ResponseWriter, r *http.Request) {
	path := strings.Trim(strings.TrimPrefix(r.URL.Path, "/api/v1/strategy-drafts/"), "/")
	parts := strings.Split(path, "/")
	if len(parts) == 0 || parts[0] == "" {
		writeError(w, http.StatusNotFound, "not_found", "Strategy draft not found")
		return
	}
	principal, ok := h.requireAuth(w, r)
	if !ok {
		return
	}
	if len(parts) == 1 {
		if !allowMethod(w, r, http.MethodGet) {
			return
		}
		h.callResearch(w, r, http.MethodGet, "/api/v1/strategy-drafts/"+parts[0], nil, &principal)
		return
	}
	if len(parts) != 2 || !allowMethod(w, r, http.MethodPost) || !h.requireCSRF(w, r) {
		return
	}
	if parts[1] == "actions" {
		var body strategyDraftActionRequest
		if err := readJSON(r, &body); err != nil {
			writeError(w, http.StatusBadRequest, "invalid_json", err.Error())
			return
		}
		if body.Action != "cancel" {
			writeError(w, http.StatusUnprocessableEntity, "invalid_action", "action must be cancel")
			return
		}
		h.callResearch(w, r, http.MethodPost, "/api/v1/strategy-drafts/"+parts[0]+"/actions", map[string]any{
			"action": body.Action,
		}, &principal)
		return
	}
	if parts[1] != "approval" {
		writeError(w, http.StatusNotFound, "not_found", "Strategy draft action not found")
		return
	}
	var body strategyApprovalRequest
	if err := readJSON(r, &body); err != nil {
		writeError(w, http.StatusBadRequest, "invalid_json", err.Error())
		return
	}
	h.callResearch(w, r, http.MethodPost, "/api/v1/strategy-drafts/"+parts[0]+"/approval", map[string]any{
		"reviewer_id":         principal.ID,
		"revision":            body.Revision,
		"spec_hash":           body.SpecHash,
		"artifact_hash":       body.ArtifactHash,
		"sandbox_report_hash": body.SandboxReportHash,
		"decision":            body.Decision,
		"reason":              body.Reason,
		"idempotency_key":     body.IdempotencyKey,
	}, &principal)
}

func (h *Handler) experiments(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodGet {
		principal, ok := h.requireAuth(w, r)
		if !ok {
			return
		}
		h.callResearch(w, r, http.MethodGet, "/api/v1/experiments", nil, &principal)
		return
	}
	if !allowMethod(w, r, http.MethodPost) {
		return
	}
	principal, ok := h.requireCommandAuth(w, r)
	if !ok {
		return
	}
	var req experimentRequest
	if err := readJSON(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid_json", err.Error())
		return
	}
	{
		// Keep the public request backward compatible while always sending the
		// complete immutable execution snapshot required by research. Zero values
		// are indistinguishable from omitted fields after JSON decoding, and none
		// of these execution settings legitimately accept zero.
		if req.StrategyVersion == "" || req.StrategyVersion == "1.0.0" {
			req.StrategyVersion = "v1"
		}
		if req.InitialEquity <= 0 {
			req.InitialEquity = 100
		}
		if req.FixedNotional <= 0 {
			req.FixedNotional = 10
		}
		if req.Leverage <= 0 {
			req.Leverage = 1
		}
		if req.FeeBps < 0 {
			writeError(w, http.StatusUnprocessableEntity, "invalid_fee_bps", "fee_bps must not be negative")
			return
		}
		if req.IntrabarPriority == "" {
			req.IntrabarPriority = "stop_loss_first"
		}
		if req.Provider == "" {
			req.Provider = defaultProvider
		}
		if req.Symbol == "" {
			req.Symbol = defaultSymbol
		}
		if req.Timeframe == "" {
			req.Timeframe = "5m"
		}
		var err error
		req.DatasetVersion, err = h.resolveDatasetVersion(
			r.Context(), req.Provider, req.Symbol, req.Timeframe, req.DatasetVersion,
		)
		if err != nil {
			writeError(w, http.StatusUnprocessableEntity, "dataset_not_ready", "Create an immutable market dataset before running an experiment")
			return
		}
		if req.IdempotencyKey != "" && r.Header.Get("Idempotency-Key") == "" {
			r.Header.Set("Idempotency-Key", req.IdempotencyKey)
		}
		candidate := req.CandidateDefinition
		if candidate == nil {
			candidate = map[string]any{}
		}
		if len(candidate) == 0 {
			candidate = map[string]any{
				"strategy_id": req.StrategyID,
				"version":     req.StrategyVersion,
				"parameters":  map[string]any{},
			}
		} else {
			// Preserve the public client's parameter snapshot. Previously this
			// field was silently discarded and every single-strategy run was
			// persisted with parameters: {}.
			candidate["strategy_id"] = req.StrategyID
			candidate["version"] = req.StrategyVersion
			if _, ok := candidate["parameters"]; !ok {
				candidate["parameters"] = map[string]any{}
			}
		}
		if len(req.Children) > 0 {
			for index := range req.Children {
				if req.Children[index].Version == "" || req.Children[index].Version == "1.0.0" {
					req.Children[index].Version = "v1"
				}
			}
			candidate = map[string]any{
				"strategy_id": "composite",
				"version":     req.StrategyVersion,
				"children":    req.Children,
				"policy": map[string]any{
					"name":      req.Combination.Policy,
					"threshold": req.Combination.Threshold,
					"encoding":  map[string]int{"BUY": 1, "HOLD": 0, "SELL": -1},
				},
			}
		}
		body := map[string]any{
			"owner_id":             principal.ID,
			"strategy_id":          req.StrategyID,
			"strategy_version":     req.StrategyVersion,
			"candidate_definition": candidate,
			"dataset_version":      req.DatasetVersion,
			"range_from":           req.RangeFrom,
			"range_to":             req.RangeTo,
			"initial_equity":       req.InitialEquity,
			"fixed_notional":       req.FixedNotional,
			"leverage":             req.Leverage,
			"fee_bps":              req.FeeBps,
			"slippage_bps":         req.SlippageBps,
			"stop_loss_pct":        req.StopLossPct,
			"take_profit_pct":      req.TakeProfitPct,
			"intrabar_priority":    req.IntrabarPriority,
			"idempotency_key":      req.IdempotencyKey,
		}
		h.callResearch(w, r, http.MethodPost, "/api/v1/experiments", body, &principal)
		return
	}
}

func (h *Handler) experimentByID(w http.ResponseWriter, r *http.Request) {
	path := strings.TrimPrefix(r.URL.Path, "/api/v1/experiments/")
	parts := strings.Split(strings.Trim(path, "/"), "/")
	if len(parts) == 0 || parts[0] == "" {
		writeError(w, http.StatusNotFound, "not_found", "Experiment not found")
		return
	}
	principal, ok := h.requireAuth(w, r)
	if !ok {
		return
	}
	if !allowMethod(w, r, http.MethodGet) {
		return
	}
	if len(parts) == 2 && parts[1] == "trades" && r.URL.Query().Get("format") == "csv" {
		h.streamResearch(w, r, "/api/v1/experiments/"+strings.Join(parts, "/"), &principal)
		return
	}
	h.callResearch(w, r, http.MethodGet, "/api/v1/experiments/"+strings.Join(parts, "/"), nil, &principal)
}

func (h *Handler) searchRuns(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodGet {
		principal, ok := h.requireAuth(w, r)
		if !ok {
			return
		}
		h.callResearch(w, r, http.MethodGet, "/api/v1/search-runs", nil, &principal)
		return
	}
	if !allowMethod(w, r, http.MethodPost) {
		return
	}
	principal, ok := h.requireCommandAuth(w, r)
	if !ok {
		return
	}
	var req searchRunRequest
	if err := readJSON(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, "invalid_json", err.Error())
		return
	}
	if err := req.validate(); err != nil {
		writeError(w, http.StatusUnprocessableEntity, "invalid_search_request", err.Error())
		return
	}
	{
		if req.Market.Provider == "" {
			req.Market.Provider = defaultProvider
		}
		if req.Market.Symbol == "" {
			req.Market.Symbol = defaultSymbol
		}
		if req.Market.Timeframe == "" {
			req.Market.Timeframe = "5m"
		}
		var err error
		req.Market.DatasetVersion, err = h.resolveDatasetVersion(
			r.Context(), req.Market.Provider, req.Market.Symbol, req.Market.Timeframe,
			req.Market.DatasetVersion,
		)
		if err != nil {
			writeError(w, http.StatusUnprocessableEntity, "dataset_not_ready", "Create an immutable market dataset before starting search")
			return
		}
		if req.IdempotencyKey != "" && r.Header.Get("Idempotency-Key") == "" {
			r.Header.Set("Idempotency-Key", req.IdempotencyKey)
		}
		body := map[string]any{
			"owner_id":        principal.ID,
			"generator_id":    req.GeneratorID,
			"search_space":    req.SearchSpace,
			"stop_conditions": req.StopConditions,
			"dataset_version": req.Market.DatasetVersion,
			"seed":            req.Seed,
			"idempotency_key": req.IdempotencyKey,
		}
		h.callResearch(w, r, http.MethodPost, "/api/v1/search-runs", body, &principal)
		return
	}
}

func (h *Handler) searchRunByID(w http.ResponseWriter, r *http.Request) {
	path := strings.TrimPrefix(r.URL.Path, "/api/v1/search-runs/")
	parts := strings.Split(strings.Trim(path, "/"), "/")
	if len(parts) == 0 || parts[0] == "" {
		writeError(w, http.StatusNotFound, "not_found", "Search run not found")
		return
	}
	principal, ok := h.requireAuth(w, r)
	if !ok {
		return
	}
	if len(parts) == 1 {
		if !allowMethod(w, r, http.MethodGet) {
			return
		}
		h.callResearch(w, r, http.MethodGet, "/api/v1/search-runs/"+parts[0], nil, &principal)
		return
	}
	if parts[1] == "archive" {
		if len(parts) != 2 || !allowMethod(w, r, http.MethodGet) {
			return
		}
		h.callResearch(w, r, http.MethodGet, "/api/v1/search-runs/"+parts[0]+"/archive", nil, &principal)
		return
	}
	if parts[1] == "actions" {
		if !allowMethod(w, r, http.MethodPost) {
			return
		}
		if !h.requireCSRF(w, r) {
			return
		}
		var body struct {
			Action    string `json:"action"`
			CommandID string `json:"command_id"`
		}
		if err := readJSON(r, &body); err != nil {
			writeError(w, http.StatusBadRequest, "invalid_json", err.Error())
			return
		}
		h.callResearch(w, r, http.MethodPost, "/api/v1/search-runs/"+parts[0]+"/actions", map[string]any{
			"actor_id":   principal.ID,
			"command_id": body.CommandID,
			"action":     body.Action,
		}, &principal)
		return
	}
	writeError(w, http.StatusNotFound, "not_found", "Search run resource not found")
}

func (h *Handler) leaderboard(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodGet) {
		return
	}
	if r.URL.Query().Get("dataset_version") == "" {
		version, err := h.resolveDatasetVersion(
			r.Context(), q(r, "provider", defaultProvider),
			q(r, "symbol", defaultSymbol), q(r, "timeframe", "5m"), "",
		)
		if err != nil {
			writeJSON(w, http.StatusOK, map[string]any{"entries": []any{}, "limit_applied": 0})
			return
		}
		query := r.URL.Query()
		query.Set("dataset_version", version)
		r.URL.RawQuery = query.Encode()
	}
	h.callResearch(w, r, http.MethodGet, "/api/v1/leaderboard", nil, nil)
}

func (h *Handler) leaderboardByID(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodGet) {
		return
	}
	path := strings.TrimPrefix(r.URL.Path, "/api/v1/leaderboard/")
	parts := strings.Split(strings.Trim(path, "/"), "/")
	if len(parts) >= 2 && parts[1] == "provenance" {
		h.callResearch(w, r, http.MethodGet, "/api/v1/leaderboard/"+parts[0]+"/provenance", nil, nil)
		return
	}
	writeError(w, http.StatusNotFound, "not_found", "Leaderboard resource not found")
}

func (h *Handler) news(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/api/v1/news" {
		h.newsAggregate(w, r)
		return
	}
	if !allowMethod(w, r, http.MethodGet) {
		return
	}
	h.callResearch(w, r, http.MethodGet, "/api/v1/news", nil, nil)
}

func (h *Handler) newsAggregate(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodGet) {
		return
	}
	h.callResearch(w, r, http.MethodGet, "/api/v1/news/aggregate", nil, nil)
}

func (h *Handler) newsCollect(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodPost) {
		return
	}
	principal, ok := h.requireCommandAuth(w, r)
	if !ok {
		return
	}
	var body struct {
		SourceID *string `json:"source_id,omitempty"`
	}
	if err := readJSON(r, &body); err != nil {
		writeError(w, http.StatusBadRequest, "invalid_json", err.Error())
		return
	}
	h.callResearch(w, r, http.MethodPost, "/api/v1/admin/news/collect", map[string]any{
		"source_id": body.SourceID,
	}, &principal)
}

func (h *Handler) predict(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodPost) {
		return
	}
	principal, ok := h.requireCommandAuth(w, r)
	if !ok {
		return
	}
	var body struct {
		Text string `json:"text"`
	}
	if err := readJSON(r, &body); err != nil {
		writeError(w, http.StatusBadRequest, "invalid_json", err.Error())
		return
	}
	if strings.TrimSpace(body.Text) == "" || len(body.Text) > 10000 {
		writeError(w, http.StatusUnprocessableEntity, "invalid_text", "Text must be 1-10000 characters")
		return
	}
	h.callResearch(
		w, r, http.MethodPost, "/api/v1/sentiment/predict",
		map[string]any{"text": body.Text}, &principal,
	)
}

func (h *Handler) marketStream(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		methodNotAllowed(w, http.MethodGet)
		return
	}
	if h.marketStreamHandler != nil {
		h.marketStreamHandler.ServeHTTP(w, r)
		return
	}
	writeError(w, http.StatusServiceUnavailable, "market_stream_unavailable", "Market stream is unavailable")
}

func (h *Handler) issueAuthCookies(w http.ResponseWriter, session authservice.Session) {
	csrf := newCSRFToken()
	http.SetCookie(w, &http.Cookie{
		Name: "access_token", Value: session.AccessToken, Path: "/api/v1", HttpOnly: true,
		Secure: h.secureCookies, SameSite: http.SameSiteStrictMode, MaxAge: int(session.AccessTTL.Seconds()),
	})
	http.SetCookie(w, &http.Cookie{
		Name: "refresh_token", Value: session.RefreshToken, Path: "/api/v1/auth", HttpOnly: true,
		Secure: h.secureCookies, SameSite: http.SameSiteStrictMode, MaxAge: int(session.RefreshTTL.Seconds()),
	})
	http.SetCookie(w, &http.Cookie{
		Name: "csrf_token", Value: csrf, Path: "/", HttpOnly: false,
		Secure: h.secureCookies, SameSite: http.SameSiteStrictMode, MaxAge: int(session.RefreshTTL.Seconds()),
	})
}

func (h *Handler) requireAuth(w http.ResponseWriter, r *http.Request) (principal, bool) {
	cookie, err := r.Cookie("access_token")
	if err != nil || cookie.Value == "" {
		writeError(w, http.StatusUnauthorized, "unauthorized", "Login is required")
		return principal{}, false
	}
	if h.authService == nil {
		writeError(w, http.StatusServiceUnavailable, "auth_unavailable", "Authentication is unavailable")
		return principal{}, false
	}
	authenticated, err := h.authService.Authenticate(r.Context(), cookie.Value)
	if err != nil {
		writeError(w, http.StatusUnauthorized, "unauthorized", "Session is invalid or expired")
		return principal{}, false
	}
	return principal{
		ID: authenticated.UserID.String(), Email: authenticated.Email,
		DisplayName: authenticated.DisplayName, Role: string(authenticated.Role),
	}, true
}

func (h *Handler) allowAuthAttempt(w http.ResponseWriter, r *http.Request, identity string) bool {
	if h.authLimiter == nil {
		return true
	}
	retryAfter, err := h.authLimiter.Allow(r.RemoteAddr + "|" + identity)
	if err == nil {
		return true
	}
	w.Header().Set("Retry-After", strconv.Itoa(max(1, int(retryAfter.Seconds()))))
	writeError(w, http.StatusTooManyRequests, "rate_limited", "Too many authentication attempts")
	return false
}

func (h *Handler) requireCommandAuth(w http.ResponseWriter, r *http.Request) (principal, bool) {
	p, ok := h.requireAuth(w, r)
	if !ok {
		return p, false
	}
	if !h.requireCSRF(w, r) {
		return p, false
	}
	if h.commandLimiter != nil {
		retryAfter, err := h.commandLimiter.Allow(p.ID + "|" + r.URL.Path)
		if err != nil {
			w.Header().Set("Retry-After", strconv.Itoa(max(1, int(retryAfter.Seconds()))))
			writeError(w, http.StatusTooManyRequests, "rate_limited", "Command rate limit exceeded")
			return p, false
		}
	}
	return p, true
}

func newCSRFToken() string {
	payload := make([]byte, 32)
	if _, err := rand.Read(payload); err != nil {
		panic("crypto/rand unavailable")
	}
	return base64.RawURLEncoding.EncodeToString(payload)
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
			w.Header().Set("Access-Control-Allow-Headers", "Content-Type, X-CSRF-Token, X-Request-ID, X-Correlation-ID, Idempotency-Key")
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

type metricResponseWriter struct {
	http.ResponseWriter
	status int
}

func (writer *metricResponseWriter) WriteHeader(status int) {
	writer.status = status
	writer.ResponseWriter.WriteHeader(status)
}

func (writer *metricResponseWriter) Write(payload []byte) (int, error) {
	if writer.status == 0 {
		writer.WriteHeader(http.StatusOK)
	}
	return writer.ResponseWriter.Write(payload)
}

func (h *Handler) withMetrics(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Keep the websocket transport's native ResponseWriter capabilities intact.
		if r.URL.Path == "/api/v1/markets/stream" {
			next.ServeHTTP(w, r)
			return
		}
		started := time.Now()
		writer := &metricResponseWriter{ResponseWriter: w}
		next.ServeHTTP(writer, r)
		responseStatus := writer.status
		if responseStatus == 0 {
			responseStatus = http.StatusOK
		}
		h.metricsMu.Lock()
		h.requestCounts[responseStatus]++
		h.requestDuration += time.Since(started)
		h.metricsMu.Unlock()
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
	requestID := w.Header().Get("X-Request-ID")
	if requestID == "" {
		requestID = "req_" + strconv.FormatInt(time.Now().UnixNano(), 36)
		w.Header().Set("X-Request-ID", requestID)
	}
	writeJSON(w, status, map[string]any{"error": map[string]any{"code": code, "message": message, "request_id": requestID}})
}

func (h *Handler) withRequestID(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requestID := strings.TrimSpace(r.Header.Get("X-Request-ID"))
		if requestID == "" || len(requestID) > 128 {
			requestID = "req_" + strconv.FormatInt(time.Now().UnixNano(), 36)
		}
		r.Header.Set("X-Request-ID", requestID)
		if r.Header.Get("X-Correlation-ID") == "" {
			r.Header.Set("X-Correlation-ID", requestID)
		}
		w.Header().Set("X-Request-ID", requestID)
		next.ServeHTTP(w, r)
	})
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
	if value := strings.TrimSpace(r.URL.Query().Get(key)); value != "" {
		return value
	}
	return fallback
}

func intQuery(r *http.Request, key string, fallback int) int {
	value, err := strconv.Atoi(r.URL.Query().Get(key))
	if err != nil || value <= 0 {
		return fallback
	}
	return value
}

func clearCookie(w http.ResponseWriter, name string, httpOnly bool) {
	path := "/api/v1"
	if name == "csrf_token" {
		path = "/"
	} else if name == "refresh_token" {
		path = "/api/v1/auth"
	}
	http.SetCookie(w, &http.Cookie{Name: name, Value: "", Path: path, HttpOnly: httpOnly, SameSite: http.SameSiteStrictMode, MaxAge: -1})
}
