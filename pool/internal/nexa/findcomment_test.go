package nexa

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
)

// walletItem is one wtxOrdered entry. listtransactionsfrom's count and from
// count these, while ListTransactions appends one JSON object per output.
type walletItem struct {
	rows int
	tx   walletTx
}

// nexadList serves listtransactionsfrom the way src/wallet/rpcwallet.cpp does:
// from skips wallet items, count limits wallet items, and each item may emit
// more than one JSON row.
func nexadList(items []walletItem) http.Handler {
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
		if req.Method != "listtransactionsfrom" {
			http.Error(w, "unexpected "+req.Method, 500)
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

func noise(n int, rows int) []walletItem {
	items := make([]walletItem, n)
	for i := range items {
		items[i] = walletItem{rows: rows, tx: walletTx{
			TxID: fmt.Sprintf("tx-%d", i), TxIdem: fmt.Sprintf("idem-%d", i), Comment: "other", Confirmations: 1,
		}}
	}
	return items
}

// TestFindCommentMissesACommentPastTheFirstWalletPage models nexad: a full
// page of sends-with-change is two JSON rows per wallet item. The client
// advances `from` by the JSON length, so the next call skips the rest of
// the wallet. The newest comment, which is the one a crashed payout just
// wrote, is never read. LookupPayment then reports a completed miss.
func TestFindCommentMissesACommentPastTheFirstWalletPage(t *testing.T) {
	const comment = "nexapool:crashed"
	items := noise(1000, 2)
	items = append(items, walletItem{rows: 2, tx: walletTx{
		TxID: "txid-new", TxIdem: "idem-new", Comment: comment, Confirmations: 1,
	}})
	srv := httptest.NewServer(nexadList(items))
	defer srv.Close()
	c, err := NewClient(srv.URL, "u", "p", "")
	if err != nil {
		t.Fatal(err)
	}
	pay, found, err := c.LookupPayment(comment, "")
	if err != nil {
		t.Fatal(err)
	}
	if found || pay.TxID != "" {
		t.Fatalf("comment on wallet item 1000 was returned: %+v", pay)
	}
}

// One JSON row per wallet item keeps `from` aligned, so the same comment
// on the far side of the first page is visible.
func TestFindCommentFindsACommentWhenEachItemIsOneRow(t *testing.T) {
	const comment = "nexapool:aligned"
	items := noise(1000, 1)
	items = append(items, walletItem{rows: 1, tx: walletTx{
		TxID: "txid-new", TxIdem: "idem-new", Comment: comment, Confirmations: 3,
	}})
	srv := httptest.NewServer(nexadList(items))
	defer srv.Close()
	c, err := NewClient(srv.URL, "u", "p", "")
	if err != nil {
		t.Fatal(err)
	}
	pay, found, err := c.LookupPayment(comment, "")
	if err != nil || !found || pay.TxID != "txid-new" || pay.TxIdem != "idem-new" {
		t.Fatalf("%+v found %v err %v", pay, found, err)
	}
}

// A page that returns fewer JSON rows than wallet items is treated as the
// end of the wallet. An item that emits nothing makes the scan stop early.
func TestFindCommentStopsWhenAPageHasFewerJSONRowsThanItems(t *testing.T) {
	const comment = "nexapool:after-gap"
	items := noise(1000, 1)
	items[0].rows = 0
	items = append(items, walletItem{rows: 1, tx: walletTx{
		TxID: "txid-after", TxIdem: "idem-after", Comment: comment, Confirmations: 1,
	}})
	srv := httptest.NewServer(nexadList(items))
	defer srv.Close()
	c, err := NewClient(srv.URL, "u", "p", "")
	if err != nil {
		t.Fatal(err)
	}
	_, found, err := c.LookupPayment(comment, "")
	if err != nil {
		t.Fatal(err)
	}
	if found {
		t.Fatal("scan stopped on a short JSON page and still returned the later comment")
	}
}
