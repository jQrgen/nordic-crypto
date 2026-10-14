package store

import (
	"errors"
	"fmt"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/jQrgen/nordic-crypto/pool/internal/account"
)

const (
	addrA   = "nexa:qqqqzqsrqszsvpcgpy9qkrqdpc83qygjzv5cxgkyhm"
	addrB   = "nexa:nq2qqqgzqvzq2ps8pqys5zcvp58q7yq3zgfsalz92rn6"
	feeAddr = addrB
	minPay  = int64(100_000_000) // 1,000,000 NEX
)

func openTest(t *testing.T) *Store {
	t.Helper()
	s, err := Open(filepath.Join(t.TempDir(), "pool.sqlite"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { s.Close() })
	return s
}

var creditN atomic.Int64

func credit(t *testing.T, s *Store, address string, amount int64, status string) {
	t.Helper()
	n := creditN.Add(1)
	id, err := s.InsertBlock(Block{Height: n, Hash: fmt.Sprintf("blk-%d", n), Finder: address, Status: "immature"})
	if err != nil {
		t.Fatal(err)
	}
	if status == "mature" {
		if err := s.MatureBlock(id, amount, []account.Credit{{Address: address, Amount: amount, Kind: "miner"}}); err != nil {
			t.Fatal(err)
		}
	}
}

type fakeTx struct {
	txid    string
	idem    string
	raw     string
	visible bool
}

type fakeWallet struct {
	next       int
	prepares   int
	broadcasts int
	failNext   error
	confs      int64
	forceConfs bool
	txs        []*fakeTx
	// spendConfs is keyed by the stored txidem. A positive value is a
	// different txidem that has spent an input, at that confirmation depth.
	spendConfs map[string]int64
	// abandon is set by tests. A positive depth ignores it. loudZero
	// reports depth 0 with every wallet flag set, which is the abandoned
	// mempool entry: the hex is broadcast again and not signed again.
	abandon    map[string]bool
	sawAbandon bool
	loudZero   bool
	hidden     map[string]bool
	locked     map[string]bool
	lastAvoid  []string
}

func newWallet() *fakeWallet {
	return &fakeWallet{
		spendConfs: map[string]int64{},
		abandon:    map[string]bool{},
		hidden:     map[string]bool{},
		locked:     map[string]bool{},
	}
}

func (w *fakeWallet) conf() int64 {
	if w.forceConfs {
		return w.confs
	}
	if w.confs == 0 {
		return 1
	}
	return w.confs
}

func (w *fakeWallet) Prepare(_ string, _ int64, avoid []string) (account.Signed, error) {
	w.lastAvoid = append([]string(nil), avoid...)
	w.next++
	w.prepares++
	op := fmt.Sprintf("out-%d", w.next)
	for _, a := range avoid {
		if strings.EqualFold(a, op) {
			w.next++
			op = fmt.Sprintf("out-%d", w.next)
		}
	}
	tx := &fakeTx{
		txid: fmt.Sprintf("txid-%d", w.next),
		idem: fmt.Sprintf("idem-%d", w.next),
		raw:  fmt.Sprintf("raw-%d", w.next),
	}
	w.txs = append(w.txs, tx)
	w.locked[op] = true
	return account.Signed{TxID: tx.txid, TxIdem: tx.idem, Raw: tx.raw, Inputs: []string{op}}, nil
}

func (w *fakeWallet) Lock(outpoints []string) error {
	for _, op := range outpoints {
		w.locked[op] = true
	}
	return nil
}

func (w *fakeWallet) Unlock(outpoints []string) error {
	for _, op := range outpoints {
		delete(w.locked, op)
	}
	return nil
}

func (w *fakeWallet) seed(signed account.Signed, visible bool) {
	w.txs = append(w.txs, &fakeTx{txid: signed.TxID, idem: signed.TxIdem, raw: signed.Raw, visible: visible})
}

func (w *fakeWallet) byID(txid, idem, raw string) *fakeTx {
	for _, tx := range w.txs {
		if txid != "" && tx.txid == txid {
			return tx
		}
	}
	for _, tx := range w.txs {
		if idem != "" && tx.idem == idem {
			return tx
		}
	}
	for _, tx := range w.txs {
		if raw != "" && tx.raw == raw {
			return tx
		}
	}
	return nil
}

func (w *fakeWallet) Broadcast(raw string) error {
	tx := w.byID("", "", raw)
	if tx == nil {
		return errors.New("unknown raw transaction")
	}
	w.broadcasts++
	if w.failNext != nil {
		err := w.failNext
		w.failNext = nil
		if broadcastAmbiguous(err) {
			delete(w.hidden, tx.txid)
			tx.visible = true
		}
		return err
	}
	delete(w.hidden, tx.txid)
	tx.visible = true
	return nil
}

func (w *fakeWallet) LookupTx(idem string) (account.TxState, error) {
	tx := w.byID("", idem, "")
	if tx == nil {
		return account.TxState{}, nil
	}
	if w.abandon[tx.txid] || w.abandon[tx.idem] {
		w.sawAbandon = true
	}
	if w.loudZero && tx.visible {
		return account.TxState{
			Payment:     account.Payment{TxID: tx.txid, TxIdem: tx.idem, Confirmations: 0},
			InWallet:    true,
			InMempool:   true,
			OnChain:     true,
			Conflict:    true,
			SpendTxIdem: "other-" + tx.idem,
			SpendConfs:  100,
		}, nil
	}
	if c := w.spendConfs[tx.idem]; c > 0 {
		return account.TxState{
			Payment:     account.Payment{TxID: tx.txid, TxIdem: tx.idem, Confirmations: -c},
			Conflict:    true,
			SpendTxIdem: "other-" + tx.idem,
			SpendConfs:  c,
		}, nil
	}
	if w.hidden[tx.txid] || w.hidden[tx.idem] || !tx.visible {
		return account.TxState{}, nil
	}
	return account.TxState{
		Payment:  account.Payment{TxID: tx.txid, TxIdem: tx.idem, Confirmations: w.conf()},
		InWallet: true,
	}, nil
}

func broadcastAmbiguous(err error) bool {
	s := strings.ToLower(err.Error())
	return strings.Contains(s, "timeout") || strings.Contains(s, "eof") || strings.Contains(s, "connection")
}

var errTimeout = errors.New("timeout talking to nexad")
var errRejected = errors.New("invalid address")

func TestPayoutOnceAndNotAgain(t *testing.T) {
	s := openTest(t)
	credit(t, s, addrA, minPay, "mature")
	w := newWallet()
	res, err := account.RunPayouts(s, w, minPay, 1, 10)
	if err != nil {
		t.Fatal(err)
	}
	if res.Sent != 1 || w.prepares != 1 || w.broadcasts != 1 {
		t.Fatalf("first pass sent %d prepares %d broadcasts %d", res.Sent, w.prepares, w.broadcasts)
	}
	res, err = account.RunPayouts(s, w, minPay, 1, 10)
	if err != nil {
		t.Fatal(err)
	}
	if res.Sent != 0 || w.prepares != 1 || w.broadcasts != 1 {
		t.Fatalf("second pass sent %d prepares %d broadcasts %d", res.Sent, w.prepares, w.broadcasts)
	}
	mature, _, paid, _, err := s.balances(addrA)
	if err != nil {
		t.Fatal(err)
	}
	if mature != minPay || paid != minPay {
		t.Fatalf("mature %d paid %d", mature, paid)
	}
	var inputs int
	if err := s.db.QueryRow(`SELECT COUNT(*) FROM payout_inputs`).Scan(&inputs); err != nil {
		t.Fatal(err)
	}
	if inputs != 1 {
		t.Fatalf("reserved outpoints %d", inputs)
	}
}

// TestCrashAfterBroadcastDoesNotSignAgain is a crash once sendrawtransaction
// has accepted the hex and the reply was lost. The row already holds that
// txid. The next pass finds it and does not sign or broadcast another one.
func TestCrashAfterBroadcastDoesNotSignAgain(t *testing.T) {
	s := openTest(t)
	credit(t, s, addrA, minPay+50, "mature")
	w := newWallet()
	w.failNext = errTimeout
	res, err := account.RunPayouts(s, w, minPay, 1, 10)
	if err != nil {
		t.Fatal(err)
	}
	if res.Deferred != 1 || res.Sent != 0 || w.prepares != 1 || w.broadcasts != 1 {
		t.Fatalf("crash pass %+v prepares %d broadcasts %d", res, w.prepares, w.broadcasts)
	}
	var txid, raw, status string
	if err := s.db.QueryRow(`SELECT COALESCE(txid,''), COALESCE(raw_tx,''), status FROM payouts`).Scan(&txid, &raw, &status); err != nil {
		t.Fatal(err)
	}
	if status != "reserved" || txid == "" || raw == "" {
		t.Fatalf("stored payout status %s txid %q raw %q", status, txid, raw)
	}
	res, err = account.RunPayouts(s, w, minPay, 1, 10)
	if err != nil {
		t.Fatal(err)
	}
	if res.Sent != 1 || w.prepares != 1 || w.broadcasts != 1 {
		t.Fatalf("reconcile sent %d prepares %d broadcasts %d", res.Sent, w.prepares, w.broadcasts)
	}
	var got string
	if err := s.db.QueryRow(`SELECT txid FROM payouts WHERE status = 'sent'`).Scan(&got); err != nil {
		t.Fatal(err)
	}
	if got != txid {
		t.Fatalf("settled txid %s, stored %s", got, txid)
	}
	res, err = account.RunPayouts(s, w, minPay, 1, 10)
	if err != nil {
		t.Fatal(err)
	}
	if w.prepares != 1 || w.broadcasts != 1 || res.Sent != 0 {
		t.Fatalf("third pass signed again: prepares %d broadcasts %d result %+v", w.prepares, w.broadcasts, res)
	}
}

func TestPayoutSkipsImmatureAndBelowMinimum(t *testing.T) {
	s := openTest(t)
	credit(t, s, addrA, minPay-1, "mature")
	credit(t, s, addrB, minPay*2, "immature")
	w := newWallet()
	res, err := account.RunPayouts(s, w, minPay, 1, 10)
	if err != nil {
		t.Fatal(err)
	}
	if res.Sent != 0 || w.prepares != 0 || w.broadcasts != 0 {
		t.Fatalf("paid something: %+v prepares %d broadcasts %d", res, w.prepares, w.broadcasts)
	}
}

// TestCrashAfterStoreBroadcastsTheStoredTransaction is a crash after the
// signed hex is durable and before sendrawtransaction accepts it. The next
// pass broadcasts that same hex and does not sign a second transaction.
func TestCrashAfterStoreBroadcastsTheStoredTransaction(t *testing.T) {
	s := openTest(t)
	credit(t, s, addrA, minPay, "mature")
	w := newWallet()
	w.failNext = errRejected
	res, err := account.RunPayouts(s, w, minPay, 1, 10)
	if err != nil {
		t.Fatal(err)
	}
	if res.Deferred != 1 || res.Sent != 0 || res.Failed != 0 || w.prepares != 1 || w.broadcasts != 1 {
		t.Fatalf("fail pass %+v prepares %d broadcasts %d", res, w.prepares, w.broadcasts)
	}
	var txid, raw, status string
	if err := s.db.QueryRow(`SELECT COALESCE(txid,''), COALESCE(raw_tx,''), status FROM payouts`).Scan(&txid, &raw, &status); err != nil {
		t.Fatal(err)
	}
	if status != "reserved" || txid == "" || raw == "" {
		t.Fatalf("row was not stored before the failed broadcast: %s %q %q", status, txid, raw)
	}
	res, err = account.RunPayouts(s, w, minPay, 1, 10)
	if err != nil {
		t.Fatal(err)
	}
	if res.Sent != 1 || w.prepares != 1 || w.broadcasts != 2 {
		t.Fatalf("retry %+v prepares %d broadcasts %d", res, w.prepares, w.broadcasts)
	}
	var got, gotRaw string
	if err := s.db.QueryRow(`SELECT txid, raw_tx FROM payouts WHERE status = 'sent'`).Scan(&got, &gotRaw); err != nil {
		t.Fatal(err)
	}
	if got != txid || gotRaw != raw {
		t.Fatalf("retry changed the transaction: %s %s, stored %s %s", got, gotRaw, txid, raw)
	}
}

func TestMatureIsIdempotentAndOrphanRemovesCredit(t *testing.T) {
	s := openTest(t)
	id, err := s.InsertBlock(Block{Height: 10, Hash: "aa", Finder: addrA})
	if err != nil {
		t.Fatal(err)
	}
	credits := []account.Credit{
		{Address: feeAddr, Amount: minPay / 100, Kind: "fee"},
		{Address: addrA, Amount: minPay - minPay/100, Kind: "miner"},
	}
	if err := s.MatureBlock(id, minPay, credits); err != nil {
		t.Fatal(err)
	}
	if err := s.MatureBlock(id, minPay, credits); err != nil {
		t.Fatal(err)
	}
	var rows int
	if err := s.db.QueryRow(`SELECT COUNT(*) FROM credits WHERE block_id = ?`, id).Scan(&rows); err != nil {
		t.Fatal(err)
	}
	if rows != 2 {
		t.Fatalf("credits rows %d, want 2", rows)
	}
	// A mature block is not orphaned by OrphanBlock. Coins that have
	// matured stay credited.
	if err := s.OrphanBlock(id); err != nil {
		t.Fatal(err)
	}
	var status string
	if err := s.db.QueryRow(`SELECT status FROM blocks WHERE id = ?`, id).Scan(&status); err != nil {
		t.Fatal(err)
	}
	if status != "mature" {
		t.Fatalf("status %s", status)
	}

	id2, err := s.InsertBlock(Block{Height: 11, Hash: "bb", Finder: addrA})
	if err != nil {
		t.Fatal(err)
	}
	if err := s.MatureBlock(id2, 50, []account.Credit{{Address: addrA, Amount: 50, Kind: "miner"}}); err != nil {
		t.Fatal(err)
	}
	// Force the status back so the orphan path can be tested on a block
	// that already has credits. The production caller only orphans an
	// immature block; the ledger still has to drop credits if it is asked.
	if _, err := s.db.Exec(`UPDATE blocks SET status = 'immature' WHERE id = ?`, id2); err != nil {
		t.Fatal(err)
	}
	if err := s.OrphanBlock(id2); err != nil {
		t.Fatal(err)
	}
	mature, _, _, _, err := s.balances(addrA)
	if err != nil {
		t.Fatal(err)
	}
	if mature != minPay-minPay/100 {
		t.Fatalf("orphan left immature coins in the balance: %d", mature)
	}
}

func TestDuplicateShare(t *testing.T) {
	s := openTest(t)
	sh := Share{Address: addrA, Worker: "rig", JobID: "1", Nonce: "aa", PowHash: "bb", Work: 200_000}
	if err := s.AddShare(sh); err != nil {
		t.Fatal(err)
	}
	if err := s.AddShare(sh); !errors.Is(err, ErrDuplicate) {
		t.Fatalf("duplicate share err %v", err)
	}
}

// TestBlindReconcileSendsTheReservedPayoutAgain is a reservation that
// never got a signed transaction. The pass must not build one for that
// row. The coins stay on hold for review.
func TestBlindReconcileSendsTheReservedPayoutAgain(t *testing.T) {
	s := openTest(t)
	credit(t, s, addrA, minPay, "mature")
	if _, err := s.Reserve(addrA, minPay, "nexapool:blind", account.Signed{}); err != nil {
		t.Fatal(err)
	}
	w := newWallet()
	res, err := account.RunPayouts(s, w, minPay, 1, 10)
	if err != nil {
		t.Fatal(err)
	}
	if w.prepares != 0 || w.broadcasts != 0 || res.Sent != 0 || res.Deferred != 1 {
		t.Fatalf("unbroadcast row was signed: prepares %d broadcasts %d result %+v", w.prepares, w.broadcasts, res)
	}
	var status string
	if err := s.db.QueryRow(`SELECT status FROM payouts WHERE idempotency_key = ?`, "nexapool:blind").Scan(&status); err != nil {
		t.Fatal(err)
	}
	if status != "review" {
		t.Fatalf("status %s, want review", status)
	}
	res, err = account.RunPayouts(s, w, minPay, 1, 10)
	if err != nil {
		t.Fatal(err)
	}
	if w.prepares != 0 || w.broadcasts != 0 || res.Sent != 0 {
		t.Fatalf("second pass signed the unbroadcast row: prepares %d broadcasts %d result %+v", w.prepares, w.broadcasts, res)
	}
	due, err := s.Payable(minPay)
	if err != nil {
		t.Fatal(err)
	}
	if len(due) != 0 {
		t.Fatalf("review row released the coins: %+v", due)
	}
}

func TestSentPayoutIsReopenedWhenTheTransactionDrops(t *testing.T) {
	s := openTest(t)
	credit(t, s, addrA, minPay, "mature")
	w := newWallet()
	res, err := account.RunPayouts(s, w, minPay, 1, 10)
	if err != nil {
		t.Fatal(err)
	}
	if res.Sent != 1 || w.prepares != 1 || w.broadcasts != 1 {
		t.Fatalf("setup %+v prepares %d broadcasts %d", res, w.prepares, w.broadcasts)
	}
	var txid string
	if err := s.db.QueryRow(`SELECT txid FROM payouts WHERE status = 'sent'`).Scan(&txid); err != nil {
		t.Fatal(err)
	}
	w.hidden[txid] = true
	res, err = account.RunPayouts(s, w, minPay, 1, 10)
	if err != nil {
		t.Fatal(err)
	}
	if w.prepares != 1 || w.broadcasts != 2 || res.Sent != 0 {
		t.Fatalf("a dropped transaction was signed again: prepares %d broadcasts %d result %+v", w.prepares, w.broadcasts, res)
	}
	var status, got string
	if err := s.db.QueryRow(`SELECT status, txid FROM payouts WHERE txid = ?`, txid).Scan(&status, &got); err != nil {
		t.Fatal(err)
	}
	if status != "sent" || got != txid {
		t.Fatalf("rebroadcast changed the payout: status %s txid %s", status, got)
	}
	due, err := s.Payable(minPay)
	if err != nil {
		t.Fatal(err)
	}
	if len(due) != 0 {
		t.Fatalf("rebroadcast returned the coins: %+v", due)
	}
}

// TestConflictingSpendPaysOnceMoreWithANewTransaction keeps the stored
// transaction while a competing spend is shallower than
// release_conflict_depth. At that depth the row is dropped and one new
// payout is signed.
func TestConflictingSpendPaysOnceMoreWithANewTransaction(t *testing.T) {
	s := openTest(t)
	credit(t, s, addrB, minPay, "mature")
	w := newWallet()
	if _, err := account.RunPayouts(s, w, minPay, 1, 10); err != nil {
		t.Fatal(err)
	}
	var oldIdem string
	if err := s.db.QueryRow(`SELECT txidem FROM payouts WHERE address = ? AND status = 'sent'`, addrB).Scan(&oldIdem); err != nil {
		t.Fatal(err)
	}
	w.spendConfs[oldIdem] = 1
	res, err := account.RunPayouts(s, w, minPay, 1, 10)
	if err != nil {
		t.Fatal(err)
	}
	if res.Failed != 0 || res.Sent != 0 || w.prepares != 1 {
		t.Fatalf("shallow conflict signed again: %+v prepares %d", res, w.prepares)
	}
	var status, idem string
	if err := s.db.QueryRow(`SELECT status, txidem FROM payouts WHERE address = ?`, addrB).Scan(&status, &idem); err != nil {
		t.Fatal(err)
	}
	if status == "failed" || idem != oldIdem {
		t.Fatalf("shallow conflict changed the payout: status %s txidem %s", status, idem)
	}
	due, err := s.Payable(minPay)
	if err != nil || len(due) != 0 {
		t.Fatalf("shallow conflict returned the coins: %+v %v", due, err)
	}
	w.spendConfs[oldIdem] = 10
	res, err = account.RunPayouts(s, w, minPay, 1, 10)
	if err != nil {
		t.Fatal(err)
	}
	if res.Failed != 1 || res.Sent != 1 || w.prepares != 2 {
		t.Fatalf("deep conflict %+v prepares %d broadcasts %d", res, w.prepares, w.broadcasts)
	}
	var failed, sent int
	if err := s.db.QueryRow(`SELECT
		SUM(CASE WHEN status = 'failed' AND txidem = ? THEN 1 ELSE 0 END),
		SUM(CASE WHEN status = 'sent' AND txidem != ? THEN 1 ELSE 0 END)
		FROM payouts WHERE address = ?`, oldIdem, oldIdem, addrB).Scan(&failed, &sent); err != nil {
		t.Fatal(err)
	}
	if failed != 1 || sent != 1 {
		t.Fatalf("conflicted txidem %s failed %d sent-other %d", oldIdem, failed, sent)
	}
}

// TestAbandonedSentPayoutIsSignedAgain records that abandontransaction
// does not sign a second payout. The name is the review's scenario.
func TestAbandonedSentPayoutIsSignedAgain(t *testing.T) {
	s := openTest(t)
	credit(t, s, addrA, minPay, "mature")
	w := newWallet()
	if _, err := account.RunPayouts(s, w, minPay, 1, 10); err != nil {
		t.Fatal(err)
	}
	var oldTx, oldIdem string
	if err := s.db.QueryRow(`SELECT txid, txidem FROM payouts WHERE status = 'sent'`).Scan(&oldTx, &oldIdem); err != nil {
		t.Fatal(err)
	}
	w.abandon[oldTx] = true
	res, err := account.RunPayouts(s, w, minPay, 1, 10)
	if err != nil {
		t.Fatal(err)
	}
	if !w.sawAbandon || res.Failed != 0 || res.Sent != 0 || w.prepares != 1 {
		t.Fatalf("abandon signed again: saw %v %+v prepares %d", w.sawAbandon, res, w.prepares)
	}
	var status, idem string
	if err := s.db.QueryRow(`SELECT status, txidem FROM payouts`).Scan(&status, &idem); err != nil {
		t.Fatal(err)
	}
	if status != "sent" || idem != oldIdem {
		t.Fatalf("abandon changed the payout: status %s txidem %s", status, idem)
	}
	due, err := s.Payable(minPay)
	if err != nil || len(due) != 0 {
		t.Fatalf("abandon returned the coins: %+v %v", due, err)
	}
}

// TestAbandonedDepthZeroIsRebroadcast keeps the stored hex when the
// wallet still lists the payout at depth 0, including when every flag
// says the transaction is conflicted or already confirmed.
func TestAbandonedDepthZeroIsRebroadcast(t *testing.T) {
	s := openTest(t)
	credit(t, s, addrA, minPay, "mature")
	w := newWallet()
	if _, err := account.RunPayouts(s, w, minPay, 1, 10); err != nil {
		t.Fatal(err)
	}
	var oldTx, oldIdem, raw string
	if err := s.db.QueryRow(`SELECT txid, txidem, raw_tx FROM payouts WHERE status = 'sent'`).Scan(&oldTx, &oldIdem, &raw); err != nil {
		t.Fatal(err)
	}
	w.abandon[oldTx] = true
	w.loudZero = true
	res, err := account.RunPayouts(s, w, minPay, 1, 10)
	if err != nil {
		t.Fatal(err)
	}
	if !w.sawAbandon || res.Failed != 0 || w.prepares != 1 || w.broadcasts < 2 {
		t.Fatalf("depth 0 did not rebroadcast the stored hex: saw %v %+v prepares %d broadcasts %d", w.sawAbandon, res, w.prepares, w.broadcasts)
	}
	var status, idem, gotRaw string
	if err := s.db.QueryRow(`SELECT status, txidem, raw_tx FROM payouts`).Scan(&status, &idem, &gotRaw); err != nil {
		t.Fatal(err)
	}
	if status == "failed" || idem != oldIdem || gotRaw != raw {
		t.Fatalf("depth 0 changed the payout: status %s txidem %s raw %s", status, idem, gotRaw)
	}
	due, err := s.Payable(minPay)
	if err != nil || len(due) != 0 {
		t.Fatalf("depth 0 returned the coins: %+v %v", due, err)
	}
}

func TestResolveReviewCompletesOrReleases(t *testing.T) {
	s := openTest(t)
	credit(t, s, addrA, minPay, "mature")
	id, err := s.Reserve(addrA, minPay, "nexapool:missing", account.Signed{})
	if err != nil {
		t.Fatal(err)
	}
	if err := s.MarkReview(id); err != nil {
		t.Fatal(err)
	}
	w := newWallet()
	if err := account.ResolveReview(s, w, id, "complete", 1, "", 24*time.Hour, 10); err == nil {
		t.Fatal("completed a review row the wallet does not have")
	}
	if err := account.ResolveReview(s, w, id, "release", 1, "", 24*time.Hour, 10); err == nil {
		t.Fatal("released without confirmation")
	}
	if err := account.ResolveReview(s, w, id, "release", 1, "txid-other", 24*time.Hour, 10); err == nil {
		t.Fatal("released a row that has no txid by naming one")
	}
	if err := account.ResolveReview(s, w, id, "release", 1, "none", 24*time.Hour, 10); err == nil {
		t.Fatal("released a fresh reservation with confirm none")
	}
	if _, err := s.db.Exec(`UPDATE payouts SET created_at = ? WHERE id = ?`, time.Now().Add(-25*time.Hour).Unix(), id); err != nil {
		t.Fatal(err)
	}
	if err := account.ResolveReview(s, w, id, "release", 1, "none", 24*time.Hour, 10); err != nil {
		t.Fatal(err)
	}
	due, err := s.Payable(minPay)
	if err != nil || len(due) != 1 || due[0].Amount != minPay {
		t.Fatalf("release did not return the coins: %+v %v", due, err)
	}

	present := account.Signed{TxID: "txid-real", TxIdem: "idem-real", Raw: "raw-real", Inputs: []string{"out-real"}}
	id, err = s.Reserve(addrA, minPay, "nexapool:present", present)
	if err != nil {
		t.Fatal(err)
	}
	if err := s.MarkReview(id); err != nil {
		t.Fatal(err)
	}
	w.seed(present, true)
	for _, confirm := range []string{"", "none", "txid-real"} {
		if err := account.ResolveReview(s, w, id, "release", 1, confirm, 24*time.Hour, 10); err == nil {
			t.Fatalf("released a review row the wallet still has, confirm %q", confirm)
		}
	}
	if err := account.ResolveReview(s, w, id, "complete", 1, "", 24*time.Hour, 10); err != nil {
		t.Fatal(err)
	}
	p, err := s.Payout(id)
	if err != nil || p.Status != "sent" || p.TxID != "txid-real" {
		t.Fatalf("complete left %+v %v", p, err)
	}
	if _, err := account.RunPayouts(s, w, minPay, 1, 10); err != nil {
		t.Fatal(err)
	}
	if w.prepares != 0 || w.broadcasts != 0 {
		t.Fatalf("completed review was signed again (prepares %d broadcasts %d)", w.prepares, w.broadcasts)
	}

	// Naming the stored txid, or abandoning it, does not release the coins.
	// Release names the stored txidem and requires a different txidem at
	// release_conflict_depth. A plain miss stays held.
	credit(t, s, addrA, minPay, "mature")
	named := account.Signed{TxID: "txid-expected", TxIdem: "idem-expected", Raw: "raw-expected", Inputs: []string{"out-expected"}}
	id, err = s.Reserve(addrA, minPay, "nexapool:named", named)
	if err != nil {
		t.Fatal(err)
	}
	if err := s.MarkReview(id); err != nil {
		t.Fatal(err)
	}
	held := newWallet()
	held.seed(named, true)
	for _, confirm := range []string{"", "none", "txid-other", "TXID-EXPECTED", "IDEM-EXPECTED"} {
		if err := account.ResolveReview(s, held, id, "release", 1, confirm, 24*time.Hour, 10); err == nil {
			t.Fatalf("released a live payout with confirm %q", confirm)
		}
	}
	if got, err := s.Payout(id); err != nil || got.Status != "review" || got.TxID != "txid-expected" || got.TxIdem != "idem-expected" {
		t.Fatalf("refused release changed the row: %+v %v", got, err)
	}
	held.abandon["txid-expected"] = true
	if err := account.ResolveReview(s, held, id, "release", 1, "IDEM-EXPECTED", 24*time.Hour, 10); err == nil {
		t.Fatal("released an abandoned payout")
	}
	if err := account.ResolveReview(s, held, id, "complete", 1, "", 24*time.Hour, 10); err != nil {
		t.Fatal(err)
	}

	credit(t, s, addrA, minPay, "mature")
	spent := account.Signed{TxID: "txid-spent", TxIdem: "idem-spent", Raw: "raw-spent", Inputs: []string{"out-spent"}}
	id, err = s.Reserve(addrA, minPay, "nexapool:spent", spent)
	if err != nil {
		t.Fatal(err)
	}
	if err := s.MarkReview(id); err != nil {
		t.Fatal(err)
	}
	conflicted := newWallet()
	conflicted.seed(spent, false)
	conflicted.spendConfs["idem-spent"] = 4
	if err := account.ResolveReview(s, conflicted, id, "release", 1, "txid-spent", 24*time.Hour, 10); err == nil {
		t.Fatal("released a conflicting spend by naming the txid")
	}
	if err := account.ResolveReview(s, conflicted, id, "release", 1, "idem-spent", 24*time.Hour, 10); err == nil {
		t.Fatal("released a conflicting spend shallower than release_conflict_depth")
	}
	if err := account.ResolveReview(s, conflicted, id, "complete", 1, "", 24*time.Hour, 10); err == nil {
		t.Fatal("completed a conflicting spend")
	}
	conflicted.spendConfs["idem-spent"] = 10
	if err := account.ResolveReview(s, conflicted, id, "release", 1, "idem-spent", time.Hour, 10); err != nil {
		t.Fatal(err)
	}
}

func TestPayoutWaitsForConfirmations(t *testing.T) {
	s := openTest(t)
	credit(t, s, addrA, minPay, "mature")
	w := newWallet()
	w.forceConfs = true
	w.confs = 0
	res, err := account.RunPayouts(s, w, minPay, 1, 10)
	if err != nil {
		t.Fatal(err)
	}
	if res.Deferred != 1 || res.Sent != 0 || w.prepares != 1 || w.broadcasts != 1 {
		t.Fatalf("unconfirmed %+v prepares %d broadcasts %d", res, w.prepares, w.broadcasts)
	}
	res, err = account.RunPayouts(s, w, minPay, 1, 10)
	if err != nil {
		t.Fatal(err)
	}
	if res.Sent != 0 || w.prepares != 1 || w.broadcasts != 2 {
		t.Fatalf("unconfirmed retry %+v prepares %d broadcasts %d", res, w.prepares, w.broadcasts)
	}
	w.confs = 1
	res, err = account.RunPayouts(s, w, minPay, 1, 10)
	if err != nil {
		t.Fatal(err)
	}
	if res.Sent != 1 || w.prepares != 1 || w.broadcasts != 2 {
		t.Fatalf("confirmed %+v prepares %d broadcasts %d", res, w.prepares, w.broadcasts)
	}
}

func TestSecondPayoutSkipsReservedOutpoints(t *testing.T) {
	s := openTest(t)
	credit(t, s, addrA, minPay, "mature")
	credit(t, s, addrB, minPay, "mature")
	w := newWallet()
	res, err := account.RunPayouts(s, w, minPay, 1, 10)
	if err != nil {
		t.Fatal(err)
	}
	if res.Sent != 2 || w.prepares != 2 {
		t.Fatalf("both %+v prepares %d", res, w.prepares)
	}
	if len(w.lastAvoid) != 1 || w.lastAvoid[0] != "out-1" {
		t.Fatalf("second payout did not skip the reserved outpoint: %v", w.lastAvoid)
	}
}

func TestReserveRejectsATakenOutpoint(t *testing.T) {
	s := openTest(t)
	credit(t, s, addrA, minPay*2, "mature")
	signed := account.Signed{TxID: "txid-1", TxIdem: "idem-1", Raw: "raw-1", Inputs: []string{"out-1"}}
	if _, err := s.Reserve(addrA, minPay, "nexapool:one", signed); err != nil {
		t.Fatal(err)
	}
	_, err := s.Reserve(addrA, minPay, "nexapool:two", signed)
	if !errors.Is(err, account.ErrOutpointTaken) {
		t.Fatalf("taken outpoint err %v", err)
	}
	var n int
	if err := s.db.QueryRow(`SELECT COUNT(*) FROM payouts`).Scan(&n); err != nil {
		t.Fatal(err)
	}
	if n != 1 {
		t.Fatalf("payout rows %d", n)
	}
	if _, err := s.Reserve(addrA, minPay, "nexapool:bare", account.Signed{TxIdem: "idem-bare"}); err == nil {
		t.Fatal("signed payout without inputs was stored")
	}
}

func TestPruneOrphanedInputsLeavesActiveRows(t *testing.T) {
	s := openTest(t)
	credit(t, s, addrA, minPay*2, "mature")
	held := account.Signed{TxID: "txid-held", TxIdem: "idem-held", Raw: "raw-held", Inputs: []string{"out-held"}}
	heldID, err := s.Reserve(addrA, minPay, "nexapool:held", held)
	if err != nil {
		t.Fatal(err)
	}
	failed := account.Signed{TxID: "txid-old", TxIdem: "idem-old", Raw: "raw-old", Inputs: []string{"out-old"}}
	failedID, err := s.Reserve(addrA, minPay, "nexapool:old", failed)
	if err != nil {
		t.Fatal(err)
	}
	if err := s.Drop(failedID); err != nil {
		t.Fatal(err)
	}
	if _, err := s.db.Exec(`PRAGMA foreign_keys = OFF`); err != nil {
		t.Fatal(err)
	}
	if _, err := s.db.Exec(`DELETE FROM payouts WHERE id = ?`, failedID); err != nil {
		t.Fatal(err)
	}
	if _, err := s.db.Exec(`PRAGMA foreign_keys = ON`); err != nil {
		t.Fatal(err)
	}
	orphans, err := s.OrphanedInputs()
	if err != nil {
		t.Fatal(err)
	}
	if len(orphans) != 1 || orphans[0].Outpoint != "out-old" || orphans[0].PayoutID != failedID || orphans[0].Status != "" {
		t.Fatalf("orphans %+v", orphans)
	}
	n, err := s.PruneOrphanedInputs()
	if err != nil {
		t.Fatal(err)
	}
	if n != 1 {
		t.Fatalf("pruned %d", n)
	}
	left, err := s.OrphanedInputs()
	if err != nil || len(left) != 0 {
		t.Fatalf("left %+v %v", left, err)
	}
	var kept int
	if err := s.db.QueryRow(`SELECT COUNT(*) FROM payout_inputs WHERE payout_id = ?`, heldID).Scan(&kept); err != nil {
		t.Fatal(err)
	}
	if kept != 1 {
		t.Fatalf("active inputs %d", kept)
	}

	if _, err := s.db.Exec(`UPDATE payouts SET status = 'failed' WHERE id = ?`, heldID); err != nil {
		t.Fatal(err)
	}
	failedRows, err := s.OrphanedInputs()
	if err != nil || len(failedRows) != 1 || failedRows[0].Status != "failed" || failedRows[0].Outpoint != "out-held" {
		t.Fatalf("failed inputs %+v %v", failedRows, err)
	}
	n, err = s.PruneOrphanedInputs()
	if err != nil || n != 1 {
		t.Fatalf("prune failed inputs %d %v", n, err)
	}
}

func TestPayoutLock(t *testing.T) {
	s := openTest(t)
	unlock, err := s.LockPayouts()
	if err != nil {
		t.Fatal(err)
	}
	if _, err := s.LockPayouts(); err == nil {
		t.Fatal("second payout lock was granted")
	}
	unlock()
	unlock, err = s.LockPayouts()
	if err != nil {
		t.Fatal(err)
	}
	unlock()
}

func TestShareWindowStopsAtTheTarget(t *testing.T) {
	s := openTest(t)
	base := time.Unix(1_700_000_000, 0)
	for i := 0; i < 5; i++ {
		sh := Share{
			Address: addrA, Worker: "rig", JobID: "j",
			Nonce: fmt.Sprintf("n%d", i), PowHash: fmt.Sprintf("p%d", i),
			Work: 10, At: base.Add(time.Duration(i) * time.Second),
		}
		if err := s.AddShare(sh); err != nil {
			t.Fatal(err)
		}
	}
	got, oldest, filled, err := s.ShareWindow(base.Add(time.Hour), 25)
	if err != nil {
		t.Fatal(err)
	}
	if !filled || len(got) != 3 || oldest == 0 {
		t.Fatalf("window %d filled %v oldest %d", len(got), filled, oldest)
	}
	if got[0].Work != 10 || got[2].Work != 10 {
		t.Fatalf("%+v", got)
	}
	// Oldest first: the three newest shares, so the first of them is not share 0.
	var firstNonce string
	if err := s.db.QueryRow(`SELECT nonce FROM shares WHERE id = ?`, oldest).Scan(&firstNonce); err != nil {
		t.Fatal(err)
	}
	if firstNonce != "n2" {
		t.Fatalf("oldest kept nonce %s", firstNonce)
	}
	if err := s.PruneSharesBefore(oldest); err != nil {
		t.Fatal(err)
	}
	var n int
	if err := s.db.QueryRow(`SELECT COUNT(*) FROM shares`).Scan(&n); err != nil {
		t.Fatal(err)
	}
	if n != 3 {
		t.Fatalf("shares left %d", n)
	}
}
