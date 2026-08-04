package httpapi

import (
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestHealth(t *testing.T) {
	router := NewRouter(NewHandler("http://localhost:8000", nil), "http://localhost:3000")
	recorder := httptest.NewRecorder()
	request := httptest.NewRequest(http.MethodGet, "/health", nil)

	router.ServeHTTP(recorder, request)

	if recorder.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", recorder.Code)
	}
	if !strings.Contains(recorder.Body.String(), `"service":"api"`) {
		t.Fatalf("expected api health payload, got %s", recorder.Body.String())
	}
}

func TestPredictProxiesRequestToAIService(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/predict" {
			t.Errorf("expected /predict, got %s", r.URL.Path)
		}
		body, _ := io.ReadAll(r.Body)
		if string(body) != `{"text":"hello"}` {
			t.Errorf("unexpected request body: %s", body)
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusCreated)
		_, _ = w.Write([]byte(`{"label":"neutral"}`))
	}))
	defer upstream.Close()

	router := NewRouter(NewHandler(upstream.URL, upstream.Client()), "http://localhost:3000")
	recorder := httptest.NewRecorder()
	request := httptest.NewRequest(
		http.MethodPost,
		"/api/v1/ai/predict",
		strings.NewReader(`{"text":"hello"}`),
	)
	request.Header.Set("Content-Type", "application/json")

	router.ServeHTTP(recorder, request)

	if recorder.Code != http.StatusCreated {
		t.Fatalf("expected status 201, got %d", recorder.Code)
	}
	if recorder.Body.String() != `{"label":"neutral"}` {
		t.Fatalf("unexpected response body: %s", recorder.Body.String())
	}
}
