package httpapi

import (
	"net/http"
	"net/http/httptest"
	"testing"

	researchclient "github.com/EnsoTech-Studio/CryptoBot/server/internal/infrastructure/research"
)

func TestNewsSourcesAreProxiedToResearch(t *testing.T) {
	research := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/v1/news/sources" {
			t.Fatalf("unexpected research request %s", r.URL.Path)
		}
		if r.Header.Get("Authorization") != "Bearer internal-token" {
			t.Fatal("missing internal authorization")
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"sources":[{"id":"source-1","display_name":"CoinDesk"}]}`))
	}))
	defer research.Close()

	client, err := researchclient.NewClient(research.URL, "internal-token", research.Client(), 1<<20)
	if err != nil {
		t.Fatal(err)
	}
	request := httptest.NewRequest(http.MethodGet, "/api/v1/news/sources", nil)
	response := httptest.NewRecorder()
	NewRouter(NewHandlerWithResearch(nil, client)).ServeHTTP(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, body = %s", response.Code, response.Body.String())
	}
	if response.Body.String() != `{"sources":[{"id":"source-1","display_name":"CoinDesk"}]}` {
		t.Fatalf("unexpected response body %s", response.Body.String())
	}
}
