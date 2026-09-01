package httpapi

import (
	"net/http"
	"net/http/httptest"
	"testing"

	researchclient "github.com/EnsoTech-Studio/CryptoBot/server/internal/infrastructure/research"
)

func TestChartOverlaysAreProxiedToResearch(t *testing.T) {
	research := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/v1/markets/chart-overlays" || r.URL.Query().Get("strategy") != "ma_cross@v1" {
			t.Fatalf("unexpected research request %s?%s", r.URL.Path, r.URL.RawQuery)
		}
		if r.Header.Get("Authorization") != "Bearer internal-token" {
			t.Fatal("missing internal authorization")
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"series":[{"name":"sma:20"}],"markers":[],"seq":7}`))
	}))
	defer research.Close()

	client, err := researchclient.NewClient(research.URL, "internal-token", research.Client(), 1<<20)
	if err != nil {
		t.Fatal(err)
	}
	request := httptest.NewRequest(http.MethodGet, "/api/v1/markets/chart-overlays?strategy=ma_cross@v1", nil)
	response := httptest.NewRecorder()
	NewRouter(NewHandlerWithResearch(nil, client)).ServeHTTP(response, request)

	if response.Code != http.StatusOK {
		t.Fatalf("status = %d, body = %s", response.Code, response.Body.String())
	}
	if response.Body.String() != `{"series":[{"name":"sma:20"}],"markers":[],"seq":7}` {
		t.Fatalf("unexpected response body %s", response.Body.String())
	}
}

func TestResearchProxyPreservesCSVDownloadHeaders(t *testing.T) {
	research := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/csv; charset=utf-8")
		w.Header().Set("Content-Disposition", `attachment; filename="experiment-123-trades.csv"`)
		_, _ = w.Write([]byte("# experiment=123\nsequence_no,symbol\n1,ETHUSDT\n"))
	}))
	defer research.Close()

	client, err := researchclient.NewClient(research.URL, "internal-token", research.Client(), 1024)
	if err != nil {
		t.Fatal(err)
	}
	request := httptest.NewRequest(http.MethodGet, "/api/v1/experiments/123/trades?format=csv", nil)
	response := httptest.NewRecorder()
	NewHandlerWithResearch(nil, client).streamResearch(response, request, "/api/v1/experiments/123/trades", nil)

	if response.Code != http.StatusOK || response.Header().Get("Content-Disposition") != `attachment; filename="experiment-123-trades.csv"` {
		t.Fatalf("CSV download headers were not preserved: status=%d headers=%v", response.Code, response.Header())
	}
}
