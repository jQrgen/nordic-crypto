package nexa

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
)

func TestRPCCandidateAndSubmit(t *testing.T) {
	var gotAuth string
	var gotMethod string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		user, pass, _ := r.BasicAuth()
		gotAuth = user + ":" + pass
		body, _ := io.ReadAll(r.Body)
		var req struct {
			Method string          `json:"method"`
			Params json.RawMessage `json:"params"`
		}
		json.Unmarshal(body, &req)
		gotMethod = req.Method
		switch req.Method {
		case "getminingcandidate":
			if !strings.Contains(string(req.Params), "nexa:qqqqzqsrqszsvpcgpy9qkrqdpc83qygjzv5cxgkyhm") {
				t.Errorf("candidate params %s", req.Params)
			}
			fmtResult(w, `{"id":14,"headerCommitment":"aabb","nBits":"207fffff","previousBlockHash":"`+strings.Repeat("0", 64)+`"}`)
		case "submitminingsolution":
			fmtResult(w, `{"height":20,"hash":"cc","result":null}`)
		case "getblock":
			fmtResult(w, `{"hash":"cc","height":20,"confirmations":3,"time":1700000000,"tx":[{"vout":[
				{"value":"1000000.50","scriptPubKey":{"addresses":["nexa:qqqqzqsrqszsvpcgpy9qkrqdpc83qygjzv5cxgkyhm"]}},
				{"value":"9.00","scriptPubKey":{"addresses":["nexa:nq2qqqgzqvzq2ps8pqys5zcvp58q7yq3zgfsalz92rn6"]}}
			]}]}`)
		case "sendtoaddress":
			if !strings.Contains(string(req.Params), "1000000.50") || !strings.Contains(string(req.Params), "nexapool:") {
				t.Errorf("send params %s", req.Params)
			}
			// nexad returns the idem, not the txid.
			fmtResult(w, `"idem1"`)
		case "gettransaction":
			fmtResult(w, `{"txid":"txid-real","txidem":"idem1","confirmations":2}`)
		case "listtransactions":
			t.Errorf("listtransactions is the 200-row window and must not be used")
			http.Error(w, "no", 500)
		case "listtransactionsfrom":
			fmtResult(w, `[{"txid":"txid-real","txidem":"idem1","comment":"nexapool:abc","confirmations":2}]`)
		default:
			http.Error(w, "no", 500)
		}
	}))
	defer srv.Close()
	c, err := NewClient(srv.URL, "rpc", "secret", "")
	if err != nil {
		t.Fatal(err)
	}
	c.PoolAddress = "nexa:qqqqzqsrqszsvpcgpy9qkrqdpc83qygjzv5cxgkyhm"
	cand, err := c.GetMiningCandidate("nexa:qqqqzqsrqszsvpcgpy9qkrqdpc83qygjzv5cxgkyhm")
	if err != nil || cand.ID != 14 || gotAuth != "rpc:secret" {
		t.Fatalf("candidate %+v %v auth %s", cand, err, gotAuth)
	}
	h, hash, err := c.SubmitSolution(14, "abcd")
	if err != nil || h != 20 || hash != "cc" || gotMethod != "submitminingsolution" {
		t.Fatalf("submit %d %s %v", h, hash, err)
	}
	blk, err := c.GetBlock("cc")
	if err != nil || blk.Reward != 100_000_050 || blk.Confirmations != 3 {
		t.Fatalf("block %+v %v", blk, err)
	}
	pay, err := c.SendToAddress("nexa:qqqqzqsrqszsvpcgpy9qkrqdpc83qygjzv5cxgkyhm", 100_000_050, "nexapool:abc")
	if err != nil || pay.TxID != "txid-real" || pay.TxIdem != "idem1" || pay.Confirmations != 2 {
		t.Fatalf("payment %+v %v", pay, err)
	}
	found, ok, err := c.LookupPayment("nexapool:abc", "")
	if err != nil || !ok || found.TxID != "txid-real" || found.TxIdem != "idem1" {
		t.Fatal(found, ok, err)
	}
}

func TestSubmitRejection(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		fmtResult(w, `"id not found (stale candidate)"`)
	}))
	defer srv.Close()
	c, _ := NewClient(srv.URL, "", "", "")
	_, _, err := c.SubmitSolution(1, "aa")
	if err == nil || !strings.Contains(err.Error(), "stale") {
		t.Fatal(err)
	}
}

func TestFindCommentScansPastTheLatest200(t *testing.T) {
	var methods []string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		var req struct {
			Method string `json:"method"`
			Params []any  `json:"params"`
		}
		json.Unmarshal(body, &req)
		methods = append(methods, req.Method)
		if req.Method == "listtransactions" {
			t.Errorf("fixed 200-row listtransactions was called")
		}
		if req.Method != "listtransactionsfrom" {
			http.Error(w, "no", 500)
			return
		}
		from := 0
		if len(req.Params) > 2 {
			from = int(req.Params[2].(float64))
		}
		if from == 0 {
			var b strings.Builder
			b.WriteByte('[')
			for i := 0; i < 1000; i++ {
				if i > 0 {
					b.WriteByte(',')
				}
				fmt.Fprintf(&b, `{"txid":"old-%d","txidem":"idem-old-%d","comment":"other","confirmations":1}`, i, i)
			}
			b.WriteByte(']')
			fmtResult(w, b.String())
			return
		}
		if from < 1000 {
			t.Errorf("page did not advance past the first thousand, from %d", from)
		}
		fmtResult(w, `[{"txid":"txid-buried","txidem":"idem-buried","comment":"nexapool:buried","confirmations":4}]`)
	}))
	defer srv.Close()
	c, err := NewClient(srv.URL, "rpc", "secret", "")
	if err != nil {
		t.Fatal(err)
	}
	pay, ok, err := c.LookupPayment("nexapool:buried", "")
	if err != nil || !ok || pay.TxID != "txid-buried" || pay.TxIdem != "idem-buried" {
		t.Fatalf("%+v %v %v", pay, ok, err)
	}
	for _, m := range methods {
		if m == "listtransactions" {
			t.Fatal("reconcile used the 200-row window")
		}
	}
}

func TestRPCRefusesRedirect(t *testing.T) {
	var leaked string
	other := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		user, pass, _ := r.BasicAuth()
		leaked = user + ":" + pass
		fmtResult(w, `"stolen"`)
	}))
	defer other.Close()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, other.URL, http.StatusFound)
	}))
	defer srv.Close()
	c, err := NewClient(srv.URL, "rpc", "secret", "")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := c.WalletBalance(); err == nil {
		t.Fatal("redirect was followed")
	}
	if leaked == "rpc:secret" {
		t.Fatal("rpc credential followed the redirect")
	}
}

func TestCookieFileMode(t *testing.T) {
	dir := t.TempDir()
	path := dir + "/.cookie"
	if err := os.WriteFile(path, []byte("__cookie__:secret"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.Chmod(path, 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := NewClient("http://127.0.0.1:7227/", "", "", path); err == nil {
		t.Fatal("group-readable cookie was accepted")
	}
	if err := os.Chmod(path, 0o600); err != nil {
		t.Fatal(err)
	}
	c, err := NewClient("http://127.0.0.1:7227/", "", "", path)
	if err != nil {
		t.Fatal(err)
	}
	if c.User != "__cookie__" || c.Password != "secret" {
		t.Fatalf("cookie auth %s", c.User)
	}
}

func TestNodeURLMustBeLoopback(t *testing.T) {
	if _, err := NewClient("http://example.com:7227/", "u", "p", ""); err == nil {
		t.Fatal("public node url was accepted")
	}
}

func fmtResult(w http.ResponseWriter, result string) {
	w.Header().Set("Content-Type", "application/json")
	io.WriteString(w, `{"result":`+result+`,"error":null,"id":"nexapool"}`)
}
