package nexa

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
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
	found, ok, err := c.LookupPayment("", "txid-real")
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
	pay, ok, err := c.FindComment("nexapool:buried")
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

func TestGetBlockRequiresPoolAddress(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		fmtResult(w, `{"hash":"cc","height":20,"confirmations":3,"time":1700000000,"tx":[{"vout":[
			{"value":"1.00","scriptPubKey":{"addresses":["nexa:qqqqzqsrqszsvpcgpy9qkrqdpc83qygjzv5cxgkyhm"]}}
		]}]}`)
	}))
	defer srv.Close()
	c, err := NewClient(srv.URL, "u", "p", "")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := c.GetBlock("cc"); err == nil {
		t.Fatal("empty coinbase address counted a reward")
	}
}

type walletItem struct {
	rows int
	tx   walletTx
}

// nexadList counts from and count as wallet items. Each item emits `rows`
// JSON objects, which is what ListTransactions does per output.
func nexadList(items []walletItem, txcount *int) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		var req struct {
			Method string `json:"method"`
			Params []any  `json:"params"`
		}
		if err := json.Unmarshal(body, &req); err != nil {
			http.Error(w, err.Error(), 500)
			return
		}
		switch req.Method {
		case "getwalletinfo":
			if txcount == nil {
				w.Header().Set("Content-Type", "application/json")
				io.WriteString(w, `{"result":null,"error":{"code":-32601,"message":"Method not found"},"id":"nexapool"}`)
				return
			}
			fmtResult(w, fmt.Sprintf(`{"txcount":%d}`, *txcount))
			return
		case "listtransactionsfrom":
		default:
			http.Error(w, "no", 500)
			return
		}
		count, from := 10, 0
		if len(req.Params) > 1 {
			count = int(req.Params[1].(float64))
		}
		if len(req.Params) > 2 {
			from = int(req.Params[2].(float64))
		}
		if from > len(items) {
			fmtResult(w, `[]`)
			return
		}
		end := from + count
		if end > len(items) {
			end = len(items)
		}
		var out []walletTx
		for _, item := range items[from:end] {
			for i := 0; i < item.rows; i++ {
				out = append(out, item.tx)
			}
		}
		if out == nil {
			fmtResult(w, `[]`)
			return
		}
		raw, err := json.Marshal(out)
		if err != nil {
			http.Error(w, err.Error(), 500)
			return
		}
		fmtResult(w, string(raw))
	})
}

func TestFindCommentPagesByWalletItemCount(t *testing.T) {
	const comment = "nexapool:crashed"
	items := make([]walletItem, 1000)
	for i := range items {
		items[i] = walletItem{rows: 2, tx: walletTx{
			TxID: fmt.Sprintf("tx-%d", i), TxIdem: fmt.Sprintf("idem-%d", i), Comment: "other", Confirmations: 1,
		}}
	}
	items = append(items, walletItem{rows: 2, tx: walletTx{
		TxID: "txid-new", TxIdem: "idem-new", Comment: comment, Confirmations: 1,
	}})
	// No txcount. Two JSON rows per item used to skip this comment.
	srv := httptest.NewServer(nexadList(items, nil))
	defer srv.Close()
	c, err := NewClient(srv.URL, "u", "p", "")
	if err != nil {
		t.Fatal(err)
	}
	pay, found, err := c.FindComment(comment)
	if err != nil || !found || pay.TxID != "txid-new" {
		t.Fatalf("comment past the first item page: %+v found %v err %v", pay, found, err)
	}

	// One silent item used to make a short JSON page look like the end.
	gapped := make([]walletItem, 1000)
	copy(gapped, items[:1000])
	gapped[0].rows = 0
	gapped = append(gapped, items[len(items)-1])
	srv2 := httptest.NewServer(nexadList(gapped, nil))
	defer srv2.Close()
	c2, err := NewClient(srv2.URL, "u", "p", "")
	if err != nil {
		t.Fatal(err)
	}
	pay, found, err = c2.FindComment(comment)
	if err != nil || !found || pay.TxID != "txid-new" {
		t.Fatalf("comment after a silent item: %+v found %v err %v", pay, found, err)
	}

	// One page of silent items returns no JSON rows. A single empty page
	// is not the end, so the comment on the next page is still read.
	silent := make([]walletItem, 1000)
	for i := range silent {
		silent[i] = walletItem{rows: 0, tx: walletTx{Comment: "quiet"}}
	}
	silent = append(silent, walletItem{rows: 1, tx: walletTx{
		TxID: "txid-after", TxIdem: "idem-after", Comment: comment, Confirmations: 2,
	}})
	n := len(silent)
	srv3 := httptest.NewServer(nexadList(silent, &n))
	defer srv3.Close()
	c3, err := NewClient(srv3.URL, "u", "p", "")
	if err != nil {
		t.Fatal(err)
	}
	pay, found, err = c3.FindComment(comment)
	if err != nil || !found || pay.TxID != "txid-after" || pay.Confirmations != 2 {
		t.Fatalf("comment after a silent page: %+v found %v err %v", pay, found, err)
	}
}

// nexad's getwalletinfo.txcount is mapWallet.size()/3, not wtxOrdered.size()
// (src/wallet/rpcwallet.cpp). A no-change send adds the id and the idem and
// no wallet output, so the reported count can sit on a page boundary below
// the real item count. That count is not where the scan stops.
func TestFindCommentTrustsTxCountPastTheLastPage(t *testing.T) {
	const comment = "nexapool:no-change"
	items := make([]walletItem, 1001)
	for i := range items {
		items[i] = walletItem{rows: 2, tx: walletTx{
			TxID: fmt.Sprintf("tx-%d", i), TxIdem: fmt.Sprintf("idem-%d", i), Comment: "other", Confirmations: 1,
		}}
	}
	items[1000] = walletItem{rows: 1, tx: walletTx{
		TxID: "txid-pay", TxIdem: "idem-pay", Comment: comment, Confirmations: 1,
	}}
	short := 1000 // mapWallet.size()/3 floors away the newest item
	srv := httptest.NewServer(nexadList(items, &short))
	defer srv.Close()
	c, err := NewClient(srv.URL, "u", "p", "")
	if err != nil {
		t.Fatal(err)
	}
	pay, found, err := c.FindComment(comment)
	if err != nil || !found || pay.TxID != "txid-pay" {
		t.Fatalf("txcount 1000 hid item 1000: %+v found %v err %v", pay, found, err)
	}

	// txcount 0 used to return not found without listing. The only item
	// is still read.
	zero := 0
	one := []walletItem{{rows: 1, tx: walletTx{
		TxID: "txid-pay", TxIdem: "idem-pay", Comment: comment, Confirmations: 1,
	}}}
	srv0 := httptest.NewServer(nexadList(one, &zero))
	defer srv0.Close()
	c0, err := NewClient(srv0.URL, "u", "p", "")
	if err != nil {
		t.Fatal(err)
	}
	pay, found, err = c0.FindComment(comment)
	if err != nil || !found || pay.TxID != "txid-pay" {
		t.Fatalf("txcount 0 hid the only item: %+v found %v err %v", pay, found, err)
	}
}

// listtransactionsfrom walks `count` wtxOrdered items and may append no
// JSON object for an item. One silent item in a page of single-row
// transactions makes the JSON array shorter than the requested count
// while later items still exist. A short page does not end the scan.
func TestFindCommentStopsOnAShortPageBeforeTheWalletEnds(t *testing.T) {
	const comment = "nexapool:after-short"
	items := make([]walletItem, 1001)
	for i := range items {
		items[i] = walletItem{rows: 1, tx: walletTx{
			TxID: fmt.Sprintf("tx-%d", i), TxIdem: fmt.Sprintf("idem-%d", i), Comment: "other", Confirmations: 1,
		}}
	}
	items[0].rows = 0
	items[1000] = walletItem{rows: 1, tx: walletTx{
		TxID: "txid-pay", TxIdem: "idem-pay", Comment: comment, Confirmations: 1,
	}}
	srv := httptest.NewServer(nexadList(items, nil))
	defer srv.Close()
	c, err := NewClient(srv.URL, "u", "p", "")
	if err != nil {
		t.Fatal(err)
	}
	pay, found, err := c.FindComment(comment)
	if err != nil || !found || pay.TxID != "txid-pay" {
		t.Fatalf("short page hid item 1000: %+v found %v err %v", pay, found, err)
	}

	// Two consecutive empty pages are not enough on their own. The
	// comment after 2000 silent items is still inside txcount*3.
	silent := make([]walletItem, 2000)
	for i := range silent {
		silent[i] = walletItem{rows: 0, tx: walletTx{Comment: "quiet"}}
	}
	silent = append(silent, walletItem{rows: 1, tx: walletTx{
		TxID: "txid-later", TxIdem: "idem-later", Comment: comment, Confirmations: 3,
	}})
	n := 1000
	srv2 := httptest.NewServer(nexadList(silent, &n))
	defer srv2.Close()
	c2, err := NewClient(srv2.URL, "u", "p", "")
	if err != nil {
		t.Fatal(err)
	}
	pay, found, err = c2.FindComment(comment)
	if err != nil || !found || pay.TxID != "txid-later" || pay.Confirmations != 3 {
		t.Fatalf("two empty pages hid a later comment: %+v found %v err %v", pay, found, err)
	}
}

// A completed miss needs two empty pages and from past txcount*3 plus the
// margin. Without a txcount the same empty wallet is an unfinished scan.
func TestFindCommentMissNeedsTheItemBound(t *testing.T) {
	const comment = "nexapool:absent"
	txcount := 0
	var buf bytes.Buffer
	srv := httptest.NewServer(nexadList(nil, &txcount))
	defer srv.Close()
	c, err := NewClient(srv.URL, "u", "p", "")
	if err != nil {
		t.Fatal(err)
	}
	c.Log = log.New(&buf, "", 0)
	pay, found, err := c.FindComment(comment)
	if err != nil || found || pay.TxID != "" {
		t.Fatalf("empty wallet: %+v found %v err %v", pay, found, err)
	}
	if !strings.Contains(buf.String(), "miss from=") || !strings.Contains(buf.String(), "bound=") {
		t.Fatalf("scan log %q", buf.String())
	}

	buf.Reset()
	srv2 := httptest.NewServer(nexadList(nil, nil))
	defer srv2.Close()
	c2, err := NewClient(srv2.URL, "u", "p", "")
	if err != nil {
		t.Fatal(err)
	}
	c2.Log = log.New(&buf, "", 0)
	pay, found, err = c2.FindComment(comment)
	if err == nil || found {
		t.Fatalf("missing txcount was a completed miss: %+v found %v err %v", pay, found, err)
	}
	if !strings.Contains(buf.String(), "unfinished from=") {
		t.Fatalf("scan log %q", buf.String())
	}
}

func TestCreatePayoutSignsBeforeBroadcast(t *testing.T) {
	const addr = "nexa:qqqqzqsrqszsvpcgpy9qkrqdpc83qygjzv5cxgkyhm"
	var methods []string
	srv := rpcScript(t, func(method string, params []any) (string, string) {
		methods = append(methods, method)
		switch method {
		case "listunspent":
			return `[{"outpoint":"prevout","amount":2.00,"confirmations":1}]`, ""
		case "createrawtransaction":
			if len(params) != 2 {
				t.Errorf("createrawtransaction params %#v", params)
			}
			in, _ := params[0].([]any)
			outs, _ := params[1].(map[string]any)
			if len(in) != 1 || outs[addr] != "1.00" {
				t.Errorf("createrawtransaction %#v", params)
			}
			coin, _ := in[0].(map[string]any)
			if coin["outpoint"] != "prevout" || coin["amount"] != "2.00" {
				t.Errorf("explicit input %#v", coin)
			}
			return `"created"`, ""
		case "fundrawtransaction":
			if len(params) != 1 || params[0] != "created" {
				t.Errorf("fundrawtransaction %#v", params)
			}
			return `{"hex":"funded","fee":0.01,"changepos":0}`, ""
		case "decoderawtransaction":
			if params[0] != "funded" {
				t.Errorf("decoderawtransaction %#v", params)
			}
			return `{"txid":"txid-unsigned","txidem":"idem-pay","vin":[{"outpoint":"prevout"}]}`, ""
		case "lockunspent":
			if len(params) != 2 || params[0] != false {
				t.Errorf("lockunspent %#v", params)
			}
			locked, _ := params[1].([]any)
			if len(locked) != 1 || locked[0] != "prevout" {
				t.Errorf("locked %#v", params[1])
			}
			return `true`, ""
		case "signrawtransaction":
			if len(params) != 1 || params[0] != "funded" {
				t.Errorf("signrawtransaction %#v", params)
			}
			return `{"hex":"signed","txid":"txid-pay","txidem":"idem-pay","complete":true}`, ""
		default:
			t.Errorf("create called %s", method)
			return `null`, "unexpected"
		}
	})
	defer srv.Close()
	c, err := NewClient(srv.URL, "u", "p", "")
	if err != nil {
		t.Fatal(err)
	}
	signed, err := c.CreatePayout(addr, 100, nil)
	if err != nil {
		t.Fatal(err)
	}
	if signed.TxID != "txid-pay" || signed.TxIdem != "idem-pay" || signed.Raw != "signed" || len(signed.Inputs) != 1 || signed.Inputs[0] != "prevout" {
		t.Fatalf("%+v", signed)
	}
	if strings.Join(methods, ",") != "listunspent,createrawtransaction,fundrawtransaction,decoderawtransaction,lockunspent,signrawtransaction" {
		t.Fatalf("methods %v", methods)
	}
	for _, m := range methods {
		if m == "sendrawtransaction" {
			t.Fatal("signed payout was broadcast")
		}
	}

	methods = nil
	srv2 := rpcScript(t, func(method string, params []any) (string, string) {
		methods = append(methods, method)
		switch method {
		case "listunspent":
			return `[{"outpoint":"prevout","amount":"2.00"}]`, ""
		case "createrawtransaction":
			return `"created"`, ""
		case "fundrawtransaction":
			if len(params) != 1 {
				t.Errorf("fundrawtransaction %#v", params)
			}
			return `{"hex":"funded"}`, ""
		case "decoderawtransaction":
			if params[0] == "funded" {
				return `{"vin":[{"outpoint":"prevout"}]}`, ""
			}
			if params[0] != "signed" {
				t.Errorf("decoderawtransaction %#v", params)
			}
			return `{"txid":"txid-dec","txidem":"idem-dec","vin":[{"outpoint":"prevout"}]}`, ""
		case "lockunspent":
			return `true`, ""
		case "signrawtransaction":
			return `{"hex":"signed","complete":true}`, ""
		default:
			t.Errorf("create called %s", method)
			return `null`, "unexpected"
		}
	})
	defer srv2.Close()
	c2, err := NewClient(srv2.URL, "u", "p", "")
	if err != nil {
		t.Fatal(err)
	}
	signed, err = c2.CreatePayout(addr, 100, nil)
	if err != nil || signed.TxID != "txid-dec" || signed.TxIdem != "idem-dec" || signed.Raw != "signed" || signed.Inputs[0] != "prevout" {
		t.Fatalf("%+v %v", signed, err)
	}
	if strings.Join(methods, ",") != "listunspent,createrawtransaction,fundrawtransaction,decoderawtransaction,lockunspent,signrawtransaction,decoderawtransaction" {
		t.Fatalf("methods %v", methods)
	}

	methods = nil
	srv3 := rpcScript(t, func(method string, params []any) (string, string) {
		methods = append(methods, method)
		switch method {
		case "lockunspent":
			if params[0] != false {
				t.Errorf("avoid lock %#v", params)
			}
			return `true`, ""
		case "listunspent":
			return `[{"outpoint":"prevout","amount":2}]`, ""
		default:
			t.Errorf("avoided coin reached %s", method)
			return `null`, "unexpected"
		}
	})
	defer srv3.Close()
	c3, err := NewClient(srv3.URL, "u", "p", "")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := c3.CreatePayout(addr, 100, []string{"prevout"}); err == nil {
		t.Fatal("reserved outpoint was spent")
	}
	if strings.Join(methods, ",") != "lockunspent,listunspent" {
		t.Fatalf("methods %v", methods)
	}
}

func TestLookupTxUsesTheStoredTransaction(t *testing.T) {
	wallet := `{"txid":"txid-pay","txidem":"idem-pay","confirmations":2}`

	t.Run("wallet", func(t *testing.T) {
		var got []string
		srv := rpcScript(t, func(method string, params []any) (string, string) {
			got = append(got, method+":"+fmt.Sprint(params[0]))
			if method == "gettransaction" && params[0] == "idem-pay" {
				return wallet, ""
			}
			t.Errorf("unexpected %s %#v", method, params)
			return `null`, "unexpected"
		})
		defer srv.Close()
		c, _ := NewClient(srv.URL, "u", "p", "")
		view, err := c.LookupTx("idem-pay")
		if err != nil || !view.InWallet || view.Conflict || view.TxID != "txid-pay" || view.TxIdem != "idem-pay" || view.Confirmations != 2 {
			t.Fatalf("%+v %v", view, err)
		}
		if strings.Join(got, ",") != "gettransaction:idem-pay" {
			t.Fatalf("calls %v", got)
		}
	})

	t.Run("idem", func(t *testing.T) {
		var got []string
		srv := rpcScript(t, func(method string, params []any) (string, string) {
			got = append(got, method+":"+fmt.Sprint(params[0]))
			if method == "gettransaction" && params[0] == "idem-pay" {
				return `{"txid":"txid-new","txidem":"idem-pay","confirmations":3}`, ""
			}
			t.Errorf("unexpected %s %#v", method, params)
			return `null`, "unexpected"
		})
		defer srv.Close()
		c, _ := NewClient(srv.URL, "u", "p", "")
		view, err := c.LookupTx("idem-pay")
		if err != nil || !view.InWallet || view.Conflict || view.TxID != "txid-new" || view.TxIdem != "idem-pay" || view.Confirmations != 3 {
			t.Fatalf("%+v %v calls %v", view, err, got)
		}
		if strings.Join(got, ",") != "gettransaction:idem-pay" {
			t.Fatalf("calls %v", got)
		}
	})

	t.Run("mempool", func(t *testing.T) {
		var got []string
		srv := rpcScript(t, func(method string, params []any) (string, string) {
			got = append(got, method+":"+fmt.Sprint(params[0]))
			switch method {
			case "gettransaction":
				return `null`, "Invalid or non-wallet transaction id"
			case "gettxpoolentry":
				if params[0] != "idem-pay" {
					t.Errorf("pool id %#v", params)
				}
				return `{"size":100}`, ""
			default:
				t.Errorf("unexpected %s", method)
				return `null`, "unexpected"
			}
		})
		defer srv.Close()
		c, _ := NewClient(srv.URL, "u", "p", "")
		view, err := c.LookupTx("idem-pay")
		if err != nil || !view.InMempool || view.InWallet || view.Conflict || view.OnChain {
			t.Fatalf("%+v %v", view, err)
		}
		if strings.Join(got, ",") != "gettransaction:idem-pay,gettxpoolentry:idem-pay" {
			t.Fatalf("calls %v", got)
		}
	})

	t.Run("chain", func(t *testing.T) {
		var methods []string
		srv := rpcScript(t, func(method string, params []any) (string, string) {
			methods = append(methods, method+":"+fmt.Sprint(params[0]))
			switch method {
			case "gettransaction":
				return `null`, "Invalid or non-wallet transaction id"
			case "gettxpoolentry":
				return `null`, "Transaction not in txpool"
			case "getrawtransaction":
				if params[0] != "idem-pay" {
					t.Errorf("chain id %#v", params)
				}
				return `{"txid":"txid-pay","txidem":"idem-pay","confirmations":4,"blockhash":"aa"}`, ""
			default:
				t.Errorf("chain lookup called %s", method)
				return `null`, "unexpected"
			}
		})
		defer srv.Close()
		c, _ := NewClient(srv.URL, "u", "p", "")
		view, err := c.LookupTx("idem-pay")
		if err != nil || !view.OnChain || view.Conflict || view.Confirmations != 4 || view.TxID != "txid-pay" {
			t.Fatalf("%+v %v methods %v", view, err, methods)
		}
	})

	t.Run("missing is not a conflict", func(t *testing.T) {
		srv := rpcScript(t, func(method string, _ []any) (string, string) {
			switch method {
			case "gettransaction":
				return `null`, "Invalid or non-wallet transaction id"
			case "gettxpoolentry":
				return `null`, "Transaction not in txpool"
			case "getrawtransaction":
				return `null`, "No such mempool or blockchain transaction"
			default:
				t.Errorf("unexpected %s", method)
				return `null`, "unexpected"
			}
		})
		defer srv.Close()
		c, _ := NewClient(srv.URL, "u", "p", "")
		view, err := c.LookupTx("idem-pay")
		if err != nil || view.Conflict || view.InWallet || view.InMempool || view.OnChain {
			t.Fatalf("%+v %v", view, err)
		}
	})

	t.Run("negative confirmations", func(t *testing.T) {
		var got []string
		srv := rpcScript(t, func(method string, params []any) (string, string) {
			got = append(got, fmt.Sprint(params[0]))
			if method != "gettransaction" {
				t.Errorf("conflicted wallet tx called %s", method)
			}
			if params[0] == "other" {
				return `{"txid":"other","txidem":"idem-pay","confirmations":-1}`, ""
			}
			return `{"txid":"txid-pay","txidem":"idem-pay","confirmations":-1,"walletconflicts":["other"]}`, ""
		})
		defer srv.Close()
		c, _ := NewClient(srv.URL, "u", "p", "")
		view, err := c.LookupTx("idem-pay")
		if err != nil || view.Conflict || view.InWallet || view.SpendTxIdem != "" {
			t.Fatalf("%+v %v calls %v", view, err, got)
		}
	})

	t.Run("nexad omits abandoned", func(t *testing.T) {
		var got []string
		srv := rpcScript(t, func(method string, params []any) (string, string) {
			got = append(got, method+":"+fmt.Sprint(params[0]))
			if method == "gettransaction" && params[0] == "idem-pay" {
				return `{"txid":"txid-pay","txidem":"idem-pay","confirmations":0}`, ""
			}
			t.Errorf("unexpected %s %#v", method, params)
			return `null`, "unexpected"
		})
		defer srv.Close()
		c, _ := NewClient(srv.URL, "u", "p", "")
		view, err := c.LookupTx("idem-pay")
		if err != nil || view.Conflict || !view.InWallet || view.Confirmations != 0 {
			t.Fatalf("%+v %v", view, err)
		}
		if strings.Join(got, ",") != "gettransaction:idem-pay" {
			t.Fatalf("calls %v", got)
		}
	})

	t.Run("conflicted txid hides confirmed idem", func(t *testing.T) {
		var got []string
		srv := rpcScript(t, func(method string, params []any) (string, string) {
			got = append(got, method+":"+fmt.Sprint(params[0]))
			if method == "gettransaction" && params[0] == "idem-pay" {
				return `{"txid":"txid-new","txidem":"idem-pay","confirmations":6}`, ""
			}
			t.Errorf("lookup used %s %#v", method, params)
			return `null`, "unexpected"
		})
		defer srv.Close()
		c, _ := NewClient(srv.URL, "u", "p", "")
		view, err := c.LookupTx("idem-pay")
		if err != nil || view.Conflict || !view.InWallet || view.TxID != "txid-new" || view.Confirmations != 6 {
			t.Fatalf("%+v %v calls %v", view, err, got)
		}
		if strings.Join(got, ",") != "gettransaction:idem-pay" {
			t.Fatalf("calls %v", got)
		}
	})

	t.Run("different txidem spend", func(t *testing.T) {
		srv := rpcScript(t, func(method string, params []any) (string, string) {
			if method != "gettransaction" {
				t.Errorf("unexpected %s", method)
			}
			switch params[0] {
			case "idem-pay":
				return `{"txid":"txid-old","txidem":"idem-pay","confirmations":-10,"walletconflicts":["other-txid"]}`, ""
			case "other-txid":
				return `{"txid":"other-txid","txidem":"other-idem","confirmations":10}`, ""
			default:
				t.Errorf("unexpected id %#v", params)
				return `null`, "unexpected"
			}
		})
		defer srv.Close()
		c, _ := NewClient(srv.URL, "u", "p", "")
		view, err := c.LookupTx("idem-pay")
		if err != nil || !view.Conflict || view.InWallet || view.SpendTxIdem != "other-idem" || view.SpendConfs != 10 {
			t.Fatalf("%+v %v", view, err)
		}
	})

	t.Run("shallow different txidem", func(t *testing.T) {
		srv := rpcScript(t, func(method string, params []any) (string, string) {
			switch params[0] {
			case "idem-pay":
				return `{"txid":"txid-old","txidem":"idem-pay","confirmations":-4,"walletconflicts":["other-txid"]}`, ""
			case "other-txid":
				return `{"txid":"other-txid","txidem":"other-idem","confirmations":4}`, ""
			default:
				return `null`, "unexpected"
			}
		})
		defer srv.Close()
		c, _ := NewClient(srv.URL, "u", "p", "")
		view, err := c.LookupTx("idem-pay")
		if err != nil || !view.Conflict || view.SpendConfs != 4 || view.SpendTxIdem != "other-idem" {
			t.Fatalf("%+v %v", view, err)
		}
	})
}

func rpcScript(t *testing.T, fn func(method string, params []any) (result, rpcError string)) *httptest.Server {
	t.Helper()
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		var req struct {
			Method string `json:"method"`
			Params []any  `json:"params"`
		}
		if err := json.Unmarshal(body, &req); err != nil {
			http.Error(w, "bad", 500)
			return
		}
		result, rpcErr := fn(req.Method, req.Params)
		w.Header().Set("Content-Type", "application/json")
		if rpcErr != "" {
			fmt.Fprintf(w, `{"result":null,"error":{"code":-5,"message":%q},"id":"nexapool"}`, rpcErr)
			return
		}
		io.WriteString(w, `{"result":`+result+`,"error":null,"id":"nexapool"}`)
	}))
}

func fmtResult(w http.ResponseWriter, result string) {
	w.Header().Set("Content-Type", "application/json")
	io.WriteString(w, `{"result":`+result+`,"error":null,"id":"nexapool"}`)
}
