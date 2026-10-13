package api

import (
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestAPIIsReadOnlyAndHidesInternals(t *testing.T) {
	svc := openSvc(t, &downNode{})
	h := Handler(svc, "", nil)

	for _, path := range []string{"/api/v1/stats", "/api/v1/blocks", "/api/v1/miners", "/api/v1/payouts", "/api/v1/health"} {
		rr := httptest.NewRecorder()
		h.ServeHTTP(rr, httptest.NewRequest(http.MethodPost, path, nil))
		if rr.Code != http.StatusMethodNotAllowed {
			t.Fatalf("POST %s status %d", path, rr.Code)
		}
	}

	rr := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/api/v1/address/nexa:qqqq'%20OR%201=1", nil)
	req.SetPathValue("address", "nexa:qqqq' OR 1=1")
	h.ServeHTTP(rr, req)
	if rr.Code != http.StatusBadRequest {
		t.Fatalf("injection status %d %s", rr.Code, rr.Body.String())
	}
	if strings.Contains(rr.Body.String(), "SQL") || strings.Contains(rr.Body.String(), "sqlite") {
		t.Fatalf("database error leaked: %s", rr.Body.String())
	}

	rr = httptest.NewRecorder()
	h.ServeHTTP(rr, httptest.NewRequest(http.MethodGet, "/api/v1/stats", nil))
	if rr.Header().Get("Access-Control-Allow-Origin") != "" {
		t.Fatalf("CORS header %q", rr.Header().Get("Access-Control-Allow-Origin"))
	}
	body, _ := io.ReadAll(rr.Body)
	if strings.Contains(string(body), "cookie") || strings.Contains(string(body), "idempotency") {
		t.Fatalf("secrets in stats: %s", body)
	}
}
