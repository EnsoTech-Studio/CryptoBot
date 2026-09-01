package research

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"testing"
)

func TestClientStreamsDownloadWithoutResponseBufferLimit(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "text/csv; charset=utf-8")
		w.Header().Set("Content-Disposition", `attachment; filename="trades.csv"`)
		_, _ = w.Write([]byte("12345"))
	}))
	defer server.Close()
	client, err := NewClient(server.URL, "secret", server.Client(), 4)
	if err != nil {
		t.Fatal(err)
	}

	response, err := client.StreamWithMetadata(context.Background(), http.MethodGet, "/api/v1/experiments/1/trades", nil, "req-1", "owner-1", "RESEARCHER", "corr-1")
	if err != nil {
		t.Fatal(err)
	}
	defer response.Body.Close()
	if response.ContentDisposition != `attachment; filename="trades.csv"` || !bytes.Equal(mustReadAll(t, response.Body), []byte("12345")) {
		t.Fatalf("unexpected streamed response: %#v", response)
	}
}

func mustReadAll(t *testing.T, body io.Reader) []byte {
	t.Helper()
	payload, err := io.ReadAll(body)
	if err != nil {
		t.Fatal(err)
	}
	return payload
}

func TestClientRequestsChartOverlayDeltaForSubscriptionKey(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet || r.URL.Path != "/api/v1/markets/chart-overlays/delta" {
			t.Fatalf("unexpected request: %s %s", r.Method, r.URL.Path)
		}
		query := r.URL.Query()
		if query.Get("provider") != "binance_usdm" || query.Get("symbol") != "ETHUSDT" ||
			query.Get("timeframe") != "5m" || query.Get("strategy") != "ma_cross@v1" ||
			query.Get("config_hash") != "sha256:test" {
			t.Fatalf("unexpected query: %v", query)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"revised_from":"2026-01-01T00:05:00Z","series":[],"markers":[]}`))
	}))
	defer server.Close()
	client, err := NewClient(server.URL, "secret", server.Client(), 1024)
	if err != nil {
		t.Fatal(err)
	}

	payload, err := client.ChartOverlayDelta(context.Background(), "binance_usdm|ETHUSDT|5m|ma_cross@v1|sha256:test")
	if err != nil {
		t.Fatal(err)
	}
	series, ok := payload["series"].([]any)
	if payload["revised_from"] != "2026-01-01T00:05:00Z" || !ok || len(series) != 0 {
		t.Fatalf("unexpected delta payload: %#v", payload)
	}
}

func TestClientPropagatesBoundaryHeadersAndBody(t *testing.T) {
	t.Parallel()
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("Authorization"); got != "Bearer secret" {
			t.Fatalf("authorization = %q", got)
		}
		if r.Header.Get("X-Request-ID") != "req-1" || r.Header.Get("X-User-ID") != "user-1" {
			t.Fatal("correlation or user context was not propagated")
		}
		var body map[string]any
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil || body["value"] != "ok" {
			t.Fatalf("unexpected body: %#v, %v", body, err)
		}
		if r.URL.Query().Get("limit") != "10" {
			t.Fatalf("query was not propagated")
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusAccepted)
		_, _ = w.Write([]byte(`{"status":"queued"}`))
	}))
	defer server.Close()

	client, err := NewClient(server.URL, "secret", server.Client(), 1024)
	if err != nil {
		t.Fatal(err)
	}
	response, err := client.Call(
		context.Background(), http.MethodPost, "/api/v1/experiments",
		url.Values{"limit": {"10"}}, map[string]any{"value": "ok"},
		"req-1", "user-1", "RESEARCHER",
	)
	if err != nil {
		t.Fatal(err)
	}
	if response.StatusCode != http.StatusAccepted || string(response.Body) != `{"status":"queued"}` {
		t.Fatalf("unexpected response: %#v", response)
	}
}

func TestClientRejectsOversizedResponse(t *testing.T) {
	t.Parallel()
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_, _ = w.Write([]byte("12345"))
	}))
	defer server.Close()
	client, err := NewClient(server.URL, "secret", server.Client(), 4)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := client.Call(context.Background(), http.MethodGet, "/", nil, nil, "", "", ""); err != ErrResponseTooLarge {
		t.Fatalf("expected ErrResponseTooLarge, got %v", err)
	}
}

func TestClientRetriesIdempotentCommandAndForwardsMetadata(t *testing.T) {
	var attempts int
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		attempts++
		if r.Header.Get("Idempotency-Key") != "idem-1" || r.Header.Get("X-Correlation-ID") != "corr-1" {
			t.Fatal("idempotency or correlation metadata missing")
		}
		if attempts == 1 {
			w.WriteHeader(http.StatusServiceUnavailable)
			return
		}
		w.WriteHeader(http.StatusAccepted)
		_, _ = w.Write([]byte(`{"status":"queued"}`))
	}))
	defer server.Close()
	client, err := NewClient(server.URL, "secret", server.Client(), 1024)
	if err != nil {
		t.Fatal(err)
	}
	response, err := client.CallWithMetadata(
		context.Background(), http.MethodPost, "/api/v1/experiments", nil,
		map[string]string{"value": "ok"}, "req-1", "user-1", "RESEARCHER",
		"idem-1", "corr-1",
	)
	if err != nil {
		t.Fatal(err)
	}
	if attempts != 2 || response.StatusCode != http.StatusAccepted {
		t.Fatalf("expected two attempts and accepted response, got %d %#v", attempts, response)
	}
}

func TestClientPreservesServiceUnavailableResponseAfterRetry(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusServiceUnavailable)
		_, _ = w.Write([]byte(`{"code":"sentiment_unavailable"}`))
	}))
	defer server.Close()

	client, err := NewClient(server.URL, "secret", server.Client(), 1024)
	if err != nil {
		t.Fatal(err)
	}
	response, err := client.CallWithMetadata(
		context.Background(), http.MethodPost, "/api/v1/sentiment/predict", nil,
		map[string]string{"text": "news"}, "req-1", "user-1", "RESEARCHER",
		"idem-1", "corr-1",
	)
	if err != nil {
		t.Fatalf("service response must be forwarded, got %v", err)
	}
	if response.StatusCode != http.StatusServiceUnavailable || string(response.Body) != `{"code":"sentiment_unavailable"}` {
		t.Fatalf("service error contract was not preserved: %#v", response)
	}
}
