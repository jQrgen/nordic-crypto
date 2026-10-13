package store

import (
	"errors"
	"fmt"
	"path/filepath"
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

type fakeWallet struct {
	sent       map[string]string
	failNext   error
	sends      int
	confs      int64
	forceConfs bool
	blind      bool
}

func newWallet() *fakeWallet { return &fakeWallet{sent: map[string]string{}} }

func (w *fakeWallet) conf() int64 {
	if w.forceConfs {
		return w.confs
	}
	if w.confs == 0 {
		return 1
	}
	return w.confs
}

func (w *fakeWallet) Send(address string, sats int64, comment string) (account.Payment, error) {
	if w.failNext != nil {
		err := w.failNext
		w.failNext = nil
		if !errors.Is(err, errTimeout) {
			return account.Payment{}, err
		}
		// The node accepted the transaction and then the connection died.
		w.sends++
		txid := "tx-" + comment
		w.sent[comment] = txid
		return account.Payment{}, err
	}
	w.sends++
	txid := "tx-" + comment
	w.sent[comment] = txid
	return account.Payment{TxID: txid, Confirmations: w.conf()}, nil
}

func (w *fakeWallet) Find(comment, id string) (account.Payment, bool, error) {
	if w.blind {
		return account.Payment{}, false, nil
	}
	if id != "" {
		for c, tx := range w.sent {
			if tx == id || c == id {
				return account.Payment{TxID: tx, Confirmations: w.conf()}, true, nil
			}
		}
	}
	txid, ok := w.sent[comment]
	if !ok {
		return account.Payment{}, false, nil
	}
	return account.Payment{TxID: txid, Confirmations: w.conf()}, true, nil
}

var errTimeout = errors.New("timeout talking to nexad")
var errRejected = errors.New("invalid address")

func TestPayoutOnceAndNotAgain(t *testing.T) {
	s := openTest(t)
	credit(t, s, addrA, minPay, "mature")
	w := newWallet()
	res, err := account.RunPayouts(s, w, minPay, 1)
	if err != nil {
		t.Fatal(err)
	}
	if res.Sent != 1 || w.sends != 1 {
		t.Fatalf("first pass sent %d wallet %d", res.Sent, w.sends)
	}
	res, err = account.RunPayouts(s, w, minPay, 1)
	if err != nil {
		t.Fatal(err)
	}
	if res.Sent != 0 || w.sends != 1 {
		t.Fatalf("second pass sent %d wallet %d", res.Sent, w.sends)
	}
	mature, _, paid, _, err := s.balances(addrA)
	if err != nil {
		t.Fatal(err)
	}
	if mature != minPay || paid != minPay {
		t.Fatalf("mature %d paid %d", mature, paid)
	}
}

func TestPayoutIdempotentAfterTimeout(t *testing.T) {
	s := openTest(t)
	credit(t, s, addrA, minPay+50, "mature")
	w := newWallet()
	w.failNext = errTimeout
	res, err := account.RunPayouts(s, w, minPay, 1)
	if err != nil {
		t.Fatal(err)
	}
	if res.Deferred != 1 || res.Sent != 0 || w.sends != 1 {
		t.Fatalf("crash pass %+v sends %d", res, w.sends)
	}
	res, err = account.RunPayouts(s, w, minPay, 1)
	if err != nil {
		t.Fatal(err)
	}
	if res.Sent != 1 || w.sends != 1 {
		t.Fatalf("reconcile sent %d wallet sends %d (want one send)", res.Sent, w.sends)
	}
	res, err = account.RunPayouts(s, w, minPay, 1)
	if err != nil {
		t.Fatal(err)
	}
	if w.sends != 1 || res.Sent != 0 {
		t.Fatalf("third pass sent more: wallet %d result %+v", w.sends, res)
	}
}

func TestPayoutSkipsImmatureAndBelowMinimum(t *testing.T) {
	s := openTest(t)
	credit(t, s, addrA, minPay-1, "mature")
	credit(t, s, addrB, minPay*2, "immature")
	w := newWallet()
	res, err := account.RunPayouts(s, w, minPay, 1)
	if err != nil {
		t.Fatal(err)
	}
	if res.Sent != 0 || w.sends != 0 {
		t.Fatalf("paid something: %+v sends %d", res, w.sends)
	}
}

func TestFailedSendDoesNotStickAndRetryPaysOnce(t *testing.T) {
	s := openTest(t)
	credit(t, s, addrA, minPay, "mature")
	w := newWallet()
	w.failNext = errRejected
	res, err := account.RunPayouts(s, w, minPay, 1)
	if err != nil {
		t.Fatal(err)
	}
	if res.Failed != 1 || w.sends != 0 {
		t.Fatalf("fail pass %+v sends %d", res, w.sends)
	}
	res, err = account.RunPayouts(s, w, minPay, 1)
	if err != nil {
		t.Fatal(err)
	}
	if res.Sent != 1 || w.sends != 1 {
		t.Fatalf("retry %+v sends %d", res, w.sends)
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

// TestBlindReconcileSendsTheReservedPayoutAgain is the old double-pay
// case: a reserved row whose comment is not visible in the wallet. The
// pass must not transmit it again. The coins stay on hold for review.
func TestBlindReconcileSendsTheReservedPayoutAgain(t *testing.T) {
	s := openTest(t)
	credit(t, s, addrA, minPay, "mature")
	if _, err := s.Reserve(addrA, minPay, "nexapool:blind"); err != nil {
		t.Fatal(err)
	}
	w := newWallet()
	w.blind = true
	res, err := account.RunPayouts(s, w, minPay, 1)
	if err != nil {
		t.Fatal(err)
	}
	if w.sends != 0 || res.Sent != 0 || res.Deferred != 1 {
		t.Fatalf("blind reconcile sent again: wallet %d result %+v", w.sends, res)
	}
	var status string
	if err := s.db.QueryRow(`SELECT status FROM payouts WHERE idempotency_key = ?`, "nexapool:blind").Scan(&status); err != nil {
		t.Fatal(err)
	}
	if status != "review" {
		t.Fatalf("status %s, want review", status)
	}
	res, err = account.RunPayouts(s, w, minPay, 1)
	if err != nil {
		t.Fatal(err)
	}
	if w.sends != 0 || res.Sent != 0 {
		t.Fatalf("second blind pass sent: wallet %d result %+v", w.sends, res)
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
	res, err := account.RunPayouts(s, w, minPay, 1)
	if err != nil {
		t.Fatal(err)
	}
	if res.Sent != 1 || w.sends != 1 {
		t.Fatalf("setup %+v sends %d", res, w.sends)
	}
	var key string
	if err := s.db.QueryRow(`SELECT idempotency_key FROM payouts WHERE status = 'sent'`).Scan(&key); err != nil {
		t.Fatal(err)
	}
	delete(w.sent, key)
	res, err = account.RunPayouts(s, w, minPay, 1)
	if err != nil {
		t.Fatal(err)
	}
	if w.sends != 1 || res.Sent != 0 {
		t.Fatalf("a dropped transaction was sent again: wallet %d result %+v", w.sends, res)
	}
	var status string
	if err := s.db.QueryRow(`SELECT status FROM payouts WHERE idempotency_key = ?`, key).Scan(&status); err != nil {
		t.Fatal(err)
	}
	if status != "review" {
		t.Fatalf("dropped payout status %s, want review", status)
	}
	due, err := s.Payable(minPay)
	if err != nil {
		t.Fatal(err)
	}
	if len(due) != 0 {
		t.Fatalf("dropped payout returned the coins: %+v", due)
	}

	// A conflicted transaction (negative confirmations) is not left paid.
	credit(t, s, addrB, minPay, "mature")
	w2 := newWallet()
	if _, err := account.RunPayouts(s, w2, minPay, 1); err != nil {
		t.Fatal(err)
	}
	w2.forceConfs = true
	w2.confs = -1
	res, err = account.RunPayouts(s, w2, minPay, 1)
	if err != nil {
		t.Fatal(err)
	}
	var sent int
	if err := s.db.QueryRow(`SELECT COUNT(*) FROM payouts WHERE address = ? AND status = 'sent'`, addrB).Scan(&sent); err != nil {
		t.Fatal(err)
	}
	if sent != 0 {
		t.Fatalf("conflicted payout stayed sent (%d rows), result %+v", sent, res)
	}
}

func TestResolveReviewCompletesOrReleases(t *testing.T) {
	s := openTest(t)
	credit(t, s, addrA, minPay, "mature")
	id, err := s.Reserve(addrA, minPay, "nexapool:missing")
	if err != nil {
		t.Fatal(err)
	}
	if err := s.MarkReview(id); err != nil {
		t.Fatal(err)
	}
	w := newWallet()
	if err := account.ResolveReview(s, w, id, "complete", 1); err == nil {
		t.Fatal("completed a review row the wallet does not have")
	}
	if err := account.ResolveReview(s, w, id, "release", 1); err != nil {
		t.Fatal(err)
	}
	due, err := s.Payable(minPay)
	if err != nil || len(due) != 1 || due[0].Amount != minPay {
		t.Fatalf("release did not return the coins: %+v %v", due, err)
	}

	id, err = s.Reserve(addrA, minPay, "nexapool:present")
	if err != nil {
		t.Fatal(err)
	}
	if err := s.MarkReview(id); err != nil {
		t.Fatal(err)
	}
	w.sent["nexapool:present"] = "txid-real"
	if err := account.ResolveReview(s, w, id, "release", 1); err == nil {
		t.Fatal("released a review row the wallet still has")
	}
	if err := account.ResolveReview(s, w, id, "complete", 1); err != nil {
		t.Fatal(err)
	}
	p, err := s.Payout(id)
	if err != nil || p.Status != "sent" || p.TxID != "txid-real" {
		t.Fatalf("complete left %+v %v", p, err)
	}
	if _, err := account.RunPayouts(s, w, minPay, 1); err != nil {
		t.Fatal(err)
	}
	if w.sends != 0 {
		t.Fatalf("completed review was sent again (%d)", w.sends)
	}
}

func TestPayoutWaitsForConfirmations(t *testing.T) {
	s := openTest(t)
	credit(t, s, addrA, minPay, "mature")
	w := newWallet()
	w.forceConfs = true
	w.confs = 0
	res, err := account.RunPayouts(s, w, minPay, 1)
	if err != nil {
		t.Fatal(err)
	}
	if res.Deferred != 1 || res.Sent != 0 || w.sends != 1 {
		t.Fatalf("unconfirmed %+v sends %d", res, w.sends)
	}
	res, err = account.RunPayouts(s, w, minPay, 1)
	if err != nil {
		t.Fatal(err)
	}
	if res.Sent != 0 || w.sends != 1 {
		t.Fatalf("unconfirmed retry sent %+v wallet %d", res, w.sends)
	}
	w.confs = 1
	res, err = account.RunPayouts(s, w, minPay, 1)
	if err != nil {
		t.Fatal(err)
	}
	if res.Sent != 1 || w.sends != 1 {
		t.Fatalf("confirmed %+v wallet %d", res, w.sends)
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
