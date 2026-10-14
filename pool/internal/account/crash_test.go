package account

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/jQrgen/nordic-crypto/pool/internal/nexa"
)

// memLedger is an in-memory book that can die at each payout step.
type memLedger struct {
	credit map[string]int64
	rows   []Payout
	next   int64
}

func newMem(addr string, amount int64) *memLedger {
	return &memLedger{credit: map[string]int64{addr: amount}}
}

func (m *memLedger) held(addr string) int64 {
	var n int64
	for _, p := range m.rows {
		if p.Address == addr && (p.Status == "reserved" || p.Status == "sent" || p.Status == "review") {
			n += p.Amount
		}
	}
	return n
}

func (m *memLedger) Payable(min int64) ([]Balance, error) {
	var out []Balance
	for addr, amt := range m.credit {
		left := amt - m.held(addr)
		if left >= min {
			out = append(out, Balance{Address: addr, Amount: left})
		}
	}
	return out, nil
}

func (m *memLedger) Reserve(address string, amount int64, key string) (int64, error) {
	if amount <= 0 || m.credit[address]-m.held(address) < amount {
		return 0, ErrBelowMin
	}
	m.next++
	m.rows = append(m.rows, Payout{
		ID: m.next, Address: address, Amount: amount, Key: key, Status: "reserved",
	})
	return m.next, nil
}

func (m *memLedger) row(id int64) *Payout {
	for i := range m.rows {
		if m.rows[i].ID == id {
			return &m.rows[i]
		}
	}
	return nil
}

func (m *memLedger) MarkSent(id int64, txid string) error {
	p := m.row(id)
	if p == nil {
		return fmt.Errorf("missing %d", id)
	}
	if p.Status != "reserved" && p.Status != "review" {
		if p.Status == "sent" {
			return nil
		}
		return fmt.Errorf("status %s", p.Status)
	}
	p.Status = "sent"
	p.TxID = txid
	return nil
}

func (m *memLedger) MarkFailed(id int64) error {
	p := m.row(id)
	if p == nil || p.Status != "reserved" {
		return nil
	}
	p.Status = "failed"
	return nil
}

func (m *memLedger) MarkReview(id int64) error {
	p := m.row(id)
	if p == nil || p.Status != "reserved" {
		return nil
	}
	p.Status = "review"
	return nil
}

func (m *memLedger) NotePayment(id int64, txid, txidem string, confs int64) error {
	p := m.row(id)
	if p == nil {
		return fmt.Errorf("missing %d", id)
	}
	if p.Status == "reserved" || p.Status == "review" {
		if txid != "" {
			p.TxID = txid
		}
		if txidem != "" {
			p.TxIdem = txidem
		}
		p.Confirmations = confs
	}
	return nil
}

func (m *memLedger) Reserved() ([]Payout, error) {
	var out []Payout
	for _, p := range m.rows {
		if p.Status == "reserved" || p.Status == "review" {
			out = append(out, p)
		}
	}
	return out, nil
}

func (m *memLedger) Sent() ([]Payout, error) {
	var out []Payout
	for _, p := range m.rows {
		if p.Status == "sent" {
			out = append(out, p)
		}
	}
	return out, nil
}

func (m *memLedger) RevertSent(id int64, status string) error {
	p := m.row(id)
	if p == nil || p.Status != "sent" {
		return fmt.Errorf("payout %d is not sent", id)
	}
	if status != "reserved" && status != "review" {
		return fmt.Errorf("status %s", status)
	}
	p.Status = status
	return nil
}

func (m *memLedger) Drop(id int64) error {
	p := m.row(id)
	if p == nil {
		return fmt.Errorf("missing %d", id)
	}
	if p.Status == "failed" {
		return nil
	}
	if p.Status != "reserved" && p.Status != "review" && p.Status != "sent" {
		return fmt.Errorf("status %s", p.Status)
	}
	p.Status = "failed"
	return nil
}

func (m *memLedger) Payout(id int64) (Payout, error) {
	p := m.row(id)
	if p == nil {
		return Payout{}, fmt.Errorf("missing %d", id)
	}
	return *p, nil
}

func (m *memLedger) ReleaseReview(id int64) error {
	p := m.row(id)
	if p == nil || p.Status != "review" {
		return fmt.Errorf("payout %d is not in review", id)
	}
	p.Status = "failed"
	return nil
}

func (m *memLedger) status(id int64) Payout {
	p := m.row(id)
	if p == nil {
		return Payout{}
	}
	return *p
}

const crashAddr = "nexa:miner"
const crashAmt = int64(1000)

// TestReleaseOfATxCountMissPaysAgain is the crash after sendtoaddress
// when getwalletinfo reports txcount = mapWallet.size()/3 and that count
// used to stop on a page boundary. The comment is still in the wallet.
// The scan reads past txcount, the row is marked sent, and release does
// not return the coins for a second payment.
func TestReleaseOfATxCountMissPaysAgain(t *testing.T) {
	const comment = "nexapool:hidden"
	type item struct {
		rows int
		body map[string]any
	}
	wallet := make([]item, 1001)
	for i := 0; i < 1000; i++ {
		wallet[i] = item{rows: 2, body: map[string]any{
			"txid": fmt.Sprintf("old-%d", i), "txidem": fmt.Sprintf("old-idem-%d", i),
			"comment": "other", "confirmations": 1,
		}}
	}
	wallet[1000] = item{rows: 1, body: map[string]any{
		"txid": "txid-pay", "txidem": "idem-pay", "comment": comment, "confirmations": 1,
	}}
	const txcount = 1000
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		raw, _ := io.ReadAll(r.Body)
		var req struct {
			Method string `json:"method"`
			Params []any  `json:"params"`
		}
		if err := json.Unmarshal(raw, &req); err != nil {
			http.Error(w, "bad", 500)
			return
		}
		if req.Method == "getwalletinfo" {
			fmt.Fprintf(w, `{"result":{"txcount":%d},"error":null,"id":"nexapool"}`, txcount)
			return
		}
		if req.Method != "listtransactionsfrom" {
			http.Error(w, "bad", 500)
			return
		}
		from := int(req.Params[2].(float64))
		count := int(req.Params[1].(float64))
		if from > len(wallet) {
			fmt.Fprintf(w, `{"result":[],"error":null,"id":"nexapool"}`)
			return
		}
		end := from + count
		if end > len(wallet) {
			end = len(wallet)
		}
		var rows []map[string]any
		for _, it := range wallet[from:end] {
			for n := 0; n < it.rows; n++ {
				rows = append(rows, it.body)
			}
		}
		if rows == nil {
			rows = []map[string]any{}
		}
		buf, _ := json.Marshal(map[string]any{"result": rows, "error": nil, "id": "nexapool"})
		w.Header().Set("Content-Type", "application/json")
		w.Write(buf)
	}))
	defer srv.Close()
	client, err := nexa.NewClient(srv.URL, "u", "p", "")
	if err != nil {
		t.Fatal(err)
	}
	book := newMem(crashAddr, crashAmt)
	id, err := book.Reserve(crashAddr, crashAmt, comment)
	if err != nil {
		t.Fatal(err)
	}
	wlt := &lookupWallet{c: client, pay: Payment{TxID: "txid-second", TxIdem: "idem-second", Confirmations: 1}}
	res, err := RunPayouts(book, wlt, 1, 1)
	if err != nil {
		t.Fatal(err)
	}
	if wlt.sends != 0 || res.Sent != 1 {
		t.Fatalf("hidden comment was not settled, or was sent again: %+v sends %d", res, wlt.sends)
	}
	if got := book.status(id); got.Status != "sent" || got.TxID != "txid-pay" {
		t.Fatalf("status %+v, want sent with txid-pay", got)
	}
	for _, confirm := range []string{"", "none", "txid-pay"} {
		if err := ResolveReview(book, wlt, id, "release", 1, confirm); err == nil {
			t.Fatalf("release returned coins for a payment the scan found, confirm %q", confirm)
		}
	}
	if got := book.status(id); got.Status != "sent" || got.TxID != "txid-pay" {
		t.Fatalf("release changed %+v", got)
	}
	res, err = RunPayouts(book, wlt, 1, 1)
	if err != nil {
		t.Fatal(err)
	}
	if wlt.sends != 0 || res.Sent != 0 {
		t.Fatalf("second pass paid again: %+v sends %d", res, wlt.sends)
	}
}

type lookupWallet struct {
	c     *nexa.Client
	sends int
	pay   Payment
}

func (w *lookupWallet) Send(string, int64, string) (Payment, error) {
	w.sends++
	if w.pay.TxID == "" && w.pay.TxIdem == "" {
		return Payment{}, errors.New("send called on a crashed reservation")
	}
	return w.pay, nil
}

func (w *lookupWallet) Find(comment, id string) (Payment, bool, error) {
	pay, found, err := w.c.LookupPayment(comment, id)
	if err != nil || !found {
		return Payment{}, false, err
	}
	return Payment{TxID: pay.TxID, TxIdem: pay.TxIdem, Confirmations: pay.Confirmations}, true, nil
}
