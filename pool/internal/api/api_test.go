package api

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"
	"time"

	"github.com/jQrgen/nordic-crypto/pool/internal/nexa"
	"github.com/jQrgen/nordic-crypto/pool/internal/pool"
	"github.com/jQrgen/nordic-crypto/pool/internal/store"
)

func TestStatsOmitsLiveNumbersWhenNodeIsDown(t *testing.T) {
	svc := openSvc(t, &downNode{})
	rr := httptest.NewRecorder()
	Handler(svc, "", nil).ServeHTTP(rr, httptest.NewRequest(http.MethodGet, "/api/v1/stats", nil))
	if rr.Code != 200 {
		t.Fatal(rr.Body.String())
	}
	var body map[string]any
	if err := json.Unmarshal(rr.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	if body["node_online"] != false || body["pool_hashrate"] != nil || body["miners"] != nil || body["network_hashrate"] != nil {
		t.Fatalf("%s", rr.Body.String())
	}
	if body["min_payout"] != "1000000.00" || body["fee_percent"] != float64(1) {
		t.Fatalf("%s", rr.Body.String())
	}
}

func TestAddressRejectsTheHelpTextExample(t *testing.T) {
	svc := openSvc(t, &downNode{})
	rr := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/api/v1/address/nexa:qq9rw090p2eu9drv6ptztwx4ghpftwfa0gyqvlvx2q", nil)
	req.SetPathValue("address", "nexa:qq9rw090p2eu9drv6ptztwx4ghpftwfa0gyqvlvx2q")
	Handler(svc, "", nil).ServeHTTP(rr, req)
	if rr.Code != http.StatusBadRequest {
		t.Fatalf("status %d %s", rr.Code, rr.Body.String())
	}
}

func TestHealth(t *testing.T) {
	svc := openSvc(t, &downNode{})
	rr := httptest.NewRecorder()
	Handler(svc, "", nil).ServeHTTP(rr, httptest.NewRequest(http.MethodGet, "/api/v1/health", nil))
	if rr.Code != 200 || rr.Body.String() == "" {
		t.Fatal(rr.Body.String())
	}
}

func openSvc(t *testing.T, node pool.Chain) *pool.Service {
	t.Helper()
	db, err := store.Open(filepath.Join(t.TempDir(), "pool.sqlite"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { db.Close() })
	svc, err := pool.New(pool.Config{
		FeePercent: 1, FeeAddress: "nexa:qqqqzqsrqszsvpcgpy9qkrqdpc83qygjzv5cxgkyhm",
		CoinbaseAddress: "nexa:qqqqzqsrqszsvpcgpy9qkrqdpc83qygjzv5cxgkyhm",
		MinPayout:       100_000_000, Maturity: 5001, PPLNSBlocks: 2, HotWalletMax: 1,
		HashrateWindow: time.Minute, PayoutEvery: time.Hour,
	}, db, node, nil)
	if err != nil {
		t.Fatal(err)
	}
	return svc
}

type downNode struct{}

func (downNode) GetMiningCandidate(string) (nexa.Candidate, error) {
	return nexa.Candidate{}, errDown
}
func (downNode) SubmitSolution(int64, string) (int64, string, error) { return 0, "", errDown }
func (downNode) GetMiningInfo() (nexa.MiningInfo, error)             { return nexa.MiningInfo{}, errDown }
func (downNode) GetBlock(string) (nexa.Block, error)                 { return nexa.Block{}, errDown }
func (downNode) CreatePayout(string, int64, []string) (nexa.SignedTx, error) {
	return nexa.SignedTx{}, errDown
}
func (downNode) SendRaw(string) error { return errDown }
func (downNode) LookupTx(string) (nexa.TxView, error) {
	return nexa.TxView{}, errDown
}
func (downNode) LockOutpoints([]string, bool) error { return errDown }
func (downNode) WalletBalance() (int64, error)      { return 0, errDown }
func (downNode) Unlock(string, int) error           { return nil }
func (downNode) Lock(string) error                  { return nil }
func (downNode) MedianTime() (int64, error)         { return 0, errDown }

type errDownT string

func (e errDownT) Error() string { return string(e) }

var errDown = errDownT("connection refused")
