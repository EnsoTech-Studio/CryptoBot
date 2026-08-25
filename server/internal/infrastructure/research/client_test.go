package research

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"testing"
)

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
