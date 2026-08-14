package httpapi

// Route is contract metadata only. No routes are registered in this phase.
type Route struct {
	Method    string
	Pattern   string
	Auth      string
	Role      string
	Ownership string
	RateLimit string
	Response  string
}

func RouteManifest() []Route {
	return []Route{
		{Method: "POST", Pattern: "/api/v1/auth/register", Auth: "public", Response: "201"},
		{Method: "POST", Pattern: "/api/v1/auth/login", Auth: "public", Response: "204"},
		{Method: "POST", Pattern: "/api/v1/auth/refresh", Auth: "refresh_cookie", Response: "204"},
		{Method: "POST", Pattern: "/api/v1/auth/logout", Auth: "authenticated+csrf", Response: "204"},
		{Method: "GET", Pattern: "/api/v1/markets/pairs", Auth: "public", Response: "200"},
		{Method: "GET", Pattern: "/api/v1/markets/candles", Auth: "public", Response: "200"},
		{Method: "GET", Pattern: "/api/v1/markets/chart-overlays", Auth: "public", Response: "200"},
		{Method: "GET", Pattern: "/api/v1/markets/stream", Auth: "public", Response: "101 websocket"},
		{Method: "GET", Pattern: "/api/v1/markets/status", Auth: "public", Response: "200"},
		{Method: "GET", Pattern: "/api/v1/strategies", Auth: "public", Response: "200"},
		{Method: "POST", Pattern: "/api/v1/experiments", Auth: "authenticated", Ownership: "owner", Response: "202"},
		{Method: "GET", Pattern: "/api/v1/experiments/{id}", Auth: "authenticated", Ownership: "owner/operator/admin", Response: "200"},
		{Method: "GET", Pattern: "/api/v1/experiments/{id}/candles", Auth: "authenticated", Ownership: "owner/operator/admin", Response: "200"},
		{Method: "GET", Pattern: "/api/v1/experiments/{id}/trades", Auth: "authenticated", Ownership: "owner/operator/admin", Response: "200"},
		{Method: "GET", Pattern: "/api/v1/experiments/{id}/equity", Auth: "authenticated", Ownership: "owner/operator/admin", Response: "200"},
		{Method: "GET", Pattern: "/api/v1/experiments/{id}/overlays", Auth: "authenticated", Ownership: "owner/operator/admin", Response: "200"},
		{Method: "POST", Pattern: "/api/v1/search-runs", Auth: "authenticated", Response: "202"},
		{Method: "GET", Pattern: "/api/v1/search-runs/{id}", Auth: "authenticated", Ownership: "owner/operator/admin", Response: "200"},
		{Method: "POST", Pattern: "/api/v1/search-runs/{id}/actions", Auth: "authenticated", Ownership: "owner/operator/admin", Response: "202"},
		{Method: "GET", Pattern: "/api/v1/leaderboard", Auth: "public", Response: "200"},
		{Method: "GET", Pattern: "/api/v1/leaderboard/{entryId}/provenance", Auth: "public", Response: "200"},
		{Method: "GET", Pattern: "/api/v1/news", Auth: "public", Response: "200"},
		{Method: "GET", Pattern: "/api/v1/news/aggregate", Auth: "public", Response: "200"},
		{Method: "POST", Pattern: "/api/v1/ai/predict", Auth: "authenticated", RateLimit: "token_bucket", Response: "200"},
		{Method: "POST", Pattern: "/api/v1/admin/users/{id}/deactivate", Auth: "authenticated", Role: "ADMIN", Response: "204"},
		{Method: "POST", Pattern: "/api/v1/admin/news-sources", Auth: "authenticated", Role: "ADMIN", Response: "201"},
		{Method: "POST", Pattern: "/api/v1/admin/score-policies", Auth: "authenticated", Role: "ADMIN", Response: "201"},
		{Method: "POST", Pattern: "/api/v1/admin/score-policies/{version}/activate", Auth: "authenticated", Role: "ADMIN", Response: "204"},
		{Method: "GET", Pattern: "/health", Auth: "public", Response: "200"},
		{Method: "GET", Pattern: "/ready", Auth: "public", Response: "200/503"},
		{Method: "GET", Pattern: "/metrics", Auth: "internal", Response: "200"},
		{Method: "POST", Pattern: "/internal/events", Auth: "internal", Response: "202"},
	}
}
