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

	// crashBeforeNote returns before the identifiers are stored.
	crashBeforeNote bool
	// crashAfterNote stores the identifiers, then returns an error so
	// MarkSent never runs.
	crashAfterNote bool
	// crashBeforeMark stores the identifiers and fails MarkSent.
	crashBeforeMark bool

	notes int
	marks int
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
	m.marks++
	if m.crashBeforeMark {
		return errors.New("crash before mark sent")
	}
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
	m.notes++
	if m.crashBeforeNote {
		return errors.New("crash before note")
	}
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
	if m.crashAfterNote {
		return errors.New("crash after note committed")
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

func (m *memLedger) status(id int64) Payout {
	p := m.row(id)
	if p == nil {
		return Payout{}
	}
	return *p
}

// scriptWallet records every send. Find answers from what was actually
// broadcast, keyed by the idempotency comment.
type scriptWallet struct {
	sends    int
	sent     map[string]Payment
	sendPay  Payment
	sendErr  error
	findErr  error
	findMiss bool
}

func (w *scriptWallet) Send(address string, sats int64, comment string) (Payment, error) {
	w.sends++
	if w.sendErr != nil {
		if w.sendPay.TxID != "" || w.sendPay.TxIdem != "" {
			if w.sent == nil {
				w.sent = map[string]Payment{}
			}
			w.sent[comment] = w.sendPay
		}
		return w.sendPay, w.sendErr
	}
	pay := w.sendPay
	if pay.TxID == "" && pay.TxIdem == "" {
		pay = Payment{TxID: "txid-" + comment, TxIdem: "idem-" + comment, Confirmations: 1}
	}
	if w.sent == nil {
		w.sent = map[string]Payment{}
	}
	w.sent[comment] = pay
	return pay, nil
}

func (w *scriptWallet) Find(comment, id string) (Payment, bool, error) {
	if w.findErr != nil {
		return Payment{}, false, w.findErr
	}
	if w.findMiss {
		return Payment{}, false, nil
	}
	if pay, ok := w.sent[comment]; ok {
		if id == "" || id == pay.TxID || id == pay.TxIdem {
			return pay, true, nil
		}
		return pay, true, nil
	}
	return Payment{}, false, nil
}

const crashAddr = "nexa:miner"
const crashAmt = int64(1000)

func TestCrashAfterReserveBeforeSendDoesNotSend(t *testing.T) {
	book := newMem(crashAddr, crashAmt)
	id, err := book.Reserve(crashAddr, crashAmt, "nexapool:reserved-only")
	if err != nil {
		t.Fatal(err)
	}
	w := &scriptWallet{findMiss: true}
	res, err := RunPayouts(book, w, 1, 1)
	if err != nil {
		t.Fatal(err)
	}
	if w.sends != 0 || res.Sent != 0 || res.Deferred != 1 {
		t.Fatalf("sends %d result %+v", w.sends, res)
	}
	if got := book.status(id); got.Status != "review" {
		t.Fatalf("status %s, want review", got.Status)
	}
	res, err = RunPayouts(book, w, 1, 1)
	if err != nil {
		t.Fatal(err)
	}
	if w.sends != 0 || res.Sent != 0 {
		t.Fatalf("second pass sent: %+v sends %d", res, w.sends)
	}
	due, err := book.Payable(1)
	if err != nil || len(due) != 0 {
		t.Fatalf("review released the coins: %+v %v", due, err)
	}
}

func TestCrashAfterSendBeforeNoteDoesNotSendAgain(t *testing.T) {
	book := newMem(crashAddr, crashAmt)
	book.crashBeforeNote = true
	w := &scriptWallet{sendPay: Payment{TxID: "txid-real", TxIdem: "idem-real", Confirmations: 1}}
	res, err := RunPayouts(book, w, 1, 1)
	if err == nil || w.sends != 1 {
		t.Fatalf("err %v sends %d result %+v", err, w.sends, res)
	}
	rows, err := book.Reserved()
	if err != nil || len(rows) != 1 || rows[0].Status != "reserved" || rows[0].TxID != "" {
		t.Fatalf("row after crash %+v %v", rows, err)
	}
	book.crashBeforeNote = false
	res, err = RunPayouts(book, w, 1, 1)
	if err != nil {
		t.Fatal(err)
	}
	if w.sends != 1 || res.Sent != 1 {
		t.Fatalf("reconcile sent again: %+v sends %d", res, w.sends)
	}
	got := book.status(rows[0].ID)
	if got.Status != "sent" || got.TxID != "txid-real" || got.TxIdem != "idem-real" {
		t.Fatalf("settled as %+v", got)
	}
}

func TestCrashAfterNoteBeforeMarkSentDoesNotSendAgain(t *testing.T) {
	book := newMem(crashAddr, crashAmt)
	book.crashAfterNote = true
	w := &scriptWallet{sendPay: Payment{TxID: "txid-real", TxIdem: "idem-real", Confirmations: 1}}
	if _, err := RunPayouts(book, w, 1, 1); err == nil || w.sends != 1 {
		t.Fatalf("expected crash after note, sends %d err %v", w.sends, err)
	}
	rows, _ := book.Reserved()
	if len(rows) != 1 || rows[0].TxID != "txid-real" || rows[0].Status != "reserved" {
		t.Fatalf("note was not durable: %+v", rows)
	}
	book.crashAfterNote = false
	res, err := RunPayouts(book, w, 1, 1)
	if err != nil {
		t.Fatal(err)
	}
	if w.sends != 1 || res.Sent != 1 {
		t.Fatalf("second pass %+v sends %d", res, w.sends)
	}
	if got := book.status(rows[0].ID); got.Status != "sent" || got.TxID != "txid-real" {
		t.Fatalf("marked %+v", got)
	}
}

func TestCrashInsideMarkSentLeavesTheNoteAndDoesNotResend(t *testing.T) {
	book := newMem(crashAddr, crashAmt)
	book.crashBeforeMark = true
	w := &scriptWallet{sendPay: Payment{TxID: "txid-real", TxIdem: "idem-real", Confirmations: 2}}
	if _, err := RunPayouts(book, w, 1, 1); err == nil {
		t.Fatal("mark crash was swallowed")
	}
	book.crashBeforeMark = false
	res, err := RunPayouts(book, w, 1, 1)
	if err != nil {
		t.Fatal(err)
	}
	if w.sends != 1 || res.Sent != 1 {
		t.Fatalf("%+v sends %d", res, w.sends)
	}
}

func TestFindErrorStaysReservedAndDoesNotSend(t *testing.T) {
	book := newMem(crashAddr, crashAmt)
	id, err := book.Reserve(crashAddr, crashAmt, "nexapool:lookup-down")
	if err != nil {
		t.Fatal(err)
	}
	w := &scriptWallet{findErr: errors.New("nexa: timeout talking to nexad")}
	res, err := RunPayouts(book, w, 1, 1)
	if err != nil {
		t.Fatal(err)
	}
	if w.sends != 0 || res.Deferred != 1 || res.Sent != 0 {
		t.Fatalf("%+v sends %d", res, w.sends)
	}
	if got := book.status(id); got.Status != "reserved" {
		t.Fatalf("status %s", got.Status)
	}
}

func TestFindMissMovesToReviewAndDoesNotSend(t *testing.T) {
	book := newMem(crashAddr, crashAmt)
	id, err := book.Reserve(crashAddr, crashAmt, "nexapool:missing")
	if err != nil {
		t.Fatal(err)
	}
	w := &scriptWallet{findMiss: true}
	res, err := RunPayouts(book, w, 1, 1)
	if err != nil {
		t.Fatal(err)
	}
	if w.sends != 0 || res.Sent != 0 {
		t.Fatalf("%+v sends %d", res, w.sends)
	}
	if got := book.status(id); got.Status != "review" {
		t.Fatalf("status %s", got.Status)
	}
	// A later pass still will not send. The coins stay deducted.
	if _, err := RunPayouts(book, w, 1, 1); err != nil {
		t.Fatal(err)
	}
	if w.sends != 0 {
		t.Fatalf("review was sent, sends %d", w.sends)
	}
	due, _ := book.Payable(1)
	if len(due) != 0 {
		t.Fatalf("payable %+v", due)
	}
}

func TestSendHeldRecordsIdemAndDoesNotSendAgain(t *testing.T) {
	book := newMem(crashAddr, crashAmt)
	w := &scriptWallet{
		sendPay: Payment{TxIdem: "idem-only"},
		sendErr: &nexa.SendHeld{TxIdem: "idem-only", Err: errors.New("gettransaction did not return a txid")},
	}
	res, err := RunPayouts(book, w, 1, 1)
	if err != nil {
		t.Fatal(err)
	}
	if w.sends != 1 || res.Sent != 0 || res.Deferred != 1 {
		t.Fatalf("%+v sends %d", res, w.sends)
	}
	rows, _ := book.Reserved()
	if len(rows) != 1 || rows[0].TxIdem != "idem-only" || rows[0].TxID != "" || rows[0].Status != "reserved" {
		t.Fatalf("held row %+v", rows)
	}
	w.sent["ignored"] = Payment{}
	// The idem is now resolvable to the canonical id with a confirmation.
	w.sendErr = nil
	w.sent = map[string]Payment{
		rows[0].Key: {TxID: "txid-real", TxIdem: "idem-only", Confirmations: 1},
	}
	res, err = RunPayouts(book, w, 1, 1)
	if err != nil {
		t.Fatal(err)
	}
	if w.sends != 1 || res.Sent != 1 {
		t.Fatalf("held retry %+v sends %d", res, w.sends)
	}
	got := book.status(rows[0].ID)
	if got.Status != "sent" || got.TxID != "txid-real" {
		t.Fatalf("stored %+v", got)
	}
}

func TestDefiniteSendFailureRetriesOnce(t *testing.T) {
	book := newMem(crashAddr, crashAmt)
	w := &scriptWallet{sendErr: errors.New("nexa: Insufficient funds")}
	res, err := RunPayouts(book, w, 1, 1)
	if err != nil {
		t.Fatal(err)
	}
	if w.sends != 1 || res.Failed != 1 || res.Sent != 0 {
		t.Fatalf("%+v sends %d", res, w.sends)
	}
	due, _ := book.Payable(1)
	if len(due) != 1 || due[0].Amount != crashAmt {
		t.Fatalf("coins not returned: %+v", due)
	}
	w.sendErr = nil
	w.sendPay = Payment{TxID: "txid-retry", TxIdem: "idem-retry", Confirmations: 1}
	res, err = RunPayouts(book, w, 1, 1)
	if err != nil {
		t.Fatal(err)
	}
	if w.sends != 2 || res.Sent != 1 {
		t.Fatalf("retry %+v sends %d", res, w.sends)
	}
	res, err = RunPayouts(book, w, 1, 1)
	if err != nil {
		t.Fatal(err)
	}
	if w.sends != 2 || res.Sent != 0 {
		t.Fatalf("third pass %+v sends %d", res, w.sends)
	}
}

func TestAmbiguousSendWithoutIDStaysReserved(t *testing.T) {
	book := newMem(crashAddr, crashAmt)
	w := &scriptWallet{sendErr: errors.New("nexa: connection reset by peer")}
	res, err := RunPayouts(book, w, 1, 1)
	if err != nil {
		t.Fatal(err)
	}
	if w.sends != 1 || res.Deferred != 1 || res.Failed != 0 {
		t.Fatalf("%+v sends %d", res, w.sends)
	}
	rows, _ := book.Reserved()
	if len(rows) != 1 || rows[0].Status != "reserved" || rows[0].TxID != "" {
		t.Fatalf("row %+v", rows)
	}
	// The send did land. The next pass must match the comment and not send.
	w.sendErr = nil
	w.sent = map[string]Payment{
		rows[0].Key: {TxID: "txid-real", TxIdem: "idem-real", Confirmations: 1},
	}
	res, err = RunPayouts(book, w, 1, 1)
	if err != nil {
		t.Fatal(err)
	}
	if w.sends != 1 || res.Sent != 1 {
		t.Fatalf("ambiguous reconcile %+v sends %d", res, w.sends)
	}
}

func TestZeroConfirmationsAreNotMarkedSent(t *testing.T) {
	book := newMem(crashAddr, crashAmt)
	w := &scriptWallet{sendPay: Payment{TxID: "txid-real", TxIdem: "idem-real", Confirmations: 0}}
	res, err := RunPayouts(book, w, 1, 1)
	if err != nil {
		t.Fatal(err)
	}
	if w.sends != 1 || res.Sent != 0 || res.Deferred != 1 {
		t.Fatalf("%+v sends %d", res, w.sends)
	}
	rows, _ := book.Reserved()
	if len(rows) != 1 || rows[0].Status != "reserved" || rows[0].TxID != "txid-real" {
		t.Fatalf("row %+v", rows)
	}
	res, err = RunPayouts(book, w, 1, 1)
	if err != nil {
		t.Fatal(err)
	}
	if w.sends != 1 || res.Sent != 0 {
		t.Fatalf("unconfirmed retry %+v sends %d", res, w.sends)
	}
	w.sent[rows[0].Key] = Payment{TxID: "txid-real", TxIdem: "idem-real", Confirmations: 1}
	res, err = RunPayouts(book, w, 1, 1)
	if err != nil {
		t.Fatal(err)
	}
	if w.sends != 1 || res.Sent != 1 {
		t.Fatalf("confirmed %+v sends %d", res, w.sends)
	}
	if got := book.status(rows[0].ID); got.TxID != "txid-real" || got.Status != "sent" {
		t.Fatalf("stored %+v", got)
	}
}

// TestCrashedPaymentMissedByPagingIsReviewedNotResent is the crash after
// sendtoaddress and before NotePayment, against a wallet nexad would
// actually return: each send is two JSON rows, and listtransactionsfrom
// counts wallet items. The comment is in the wallet. The scan misses it.
// The row goes to review and is not sent a second time.
func TestCrashedPaymentMissedByPagingIsReviewedNotResent(t *testing.T) {
	const comment = "nexapool:crashed"
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
	wallet[1000] = item{rows: 2, body: map[string]any{
		"txid": "txid-real", "txidem": "idem-real", "comment": comment, "confirmations": 1,
	}}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		raw, _ := io.ReadAll(r.Body)
		var req struct {
			Method string `json:"method"`
			Params []any  `json:"params"`
		}
		if err := json.Unmarshal(raw, &req); err != nil || req.Method != "listtransactionsfrom" {
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
	wlt := &lookupWallet{c: client}
	res, err := RunPayouts(book, wlt, 1, 1)
	if err != nil {
		t.Fatal(err)
	}
	if wlt.sends != 0 || res.Sent != 0 {
		t.Fatalf("missed comment was sent: %+v sends %d", res, wlt.sends)
	}
	if got := book.status(id); got.Status != "review" {
		t.Fatalf("status %s, want review", got.Status)
	}
	res, err = RunPayouts(book, wlt, 1, 1)
	if err != nil {
		t.Fatal(err)
	}
	if wlt.sends != 0 || res.Sent != 0 {
		t.Fatalf("second pass sent: %+v sends %d", res, wlt.sends)
	}
}

type lookupWallet struct {
	c     *nexa.Client
	sends int
}

func (w *lookupWallet) Send(string, int64, string) (Payment, error) {
	w.sends++
	return Payment{}, errors.New("send called on a crashed reservation")
}

func (w *lookupWallet) Find(comment, id string) (Payment, bool, error) {
	pay, found, err := w.c.LookupPayment(comment, id)
	if err != nil || !found {
		return Payment{}, false, err
	}
	return Payment{TxID: pay.TxID, TxIdem: pay.TxIdem, Confirmations: pay.Confirmations}, true, nil
}

func TestSentRowIsNotSentAgain(t *testing.T) {
	book := newMem(crashAddr, crashAmt)
	w := &scriptWallet{sendPay: Payment{TxID: "txid-real", TxIdem: "idem-real", Confirmations: 1}}
	if _, err := RunPayouts(book, w, 1, 1); err != nil {
		t.Fatal(err)
	}
	res, err := RunPayouts(book, w, 1, 1)
	if err != nil {
		t.Fatal(err)
	}
	if w.sends != 1 || res.Sent != 0 {
		t.Fatalf("second pass %+v sends %d", res, w.sends)
	}
}
