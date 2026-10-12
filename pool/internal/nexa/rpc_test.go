package nexa

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
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
			fmtResult(w, `{"hash":"cc","height":20,"confirmations":3,"time":1700000000,"tx":[{"vout":[{"value":"1000000.50"}]}]}`)
		case "sendtoaddress":
			if !strings.Contains(string(req.Params), "1000000.50") || !strings.Contains(string(req.Params), "nexapool:") {
				t.Errorf("send params %s", req.Params)
			}
			fmtResult(w, `"txid1"`)
		case "listtransactions":
			fmtResult(w, `[{"txid":"txid1","comment":"nexapool:abc"}]`)
		default:
			http.Error(w, "no", 500)
		}
	}))
	defer srv.Close()
	c, err := NewClient(srv.URL, "rpc", "secret", "")
	if err != nil {
		t.Fatal(err)
	}
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
	txid, err := c.SendToAddress("nexa:qqqqzqsrqszsvpcgpy9qkrqdpc83qygjzv5cxgkyhm", 100_000_050, "nexapool:abc")
	if err != nil || txid != "txid1" {
		t.Fatal(txid, err)
	}
	found, ok, err := c.FindComment("nexapool:abc")
	if err != nil || !ok || found != "txid1" {
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

func fmtResult(w http.ResponseWriter, result string) {
	w.Header().Set("Content-Type", "application/json")
	io.WriteString(w, `{"result":`+result+`,"error":null,"id":"nexapool"}`)
}
