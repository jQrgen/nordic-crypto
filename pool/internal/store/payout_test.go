package store

import (
	"errors"
	"fmt"
	"path/filepath"
	"sync/atomic"
	"testing"

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
	sent     map[string]string
	failNext error
	sends    int
}

func newWallet() *fakeWallet { return &fakeWallet{sent: map[string]string{}} }

func (w *fakeWallet) Send(address string, sats int64, comment string) (string, error) {
	if w.failNext != nil {
		err := w.failNext
		w.failNext = nil
		if !errors.Is(err, errTimeout) {
			return "", err
		}
		// The node accepted the transaction and then the connection died.
		w.sends++
		txid := "tx-" + comment
		w.sent[comment] = txid
		return "", err
	}
	w.sends++
	txid := "tx-" + comment
	w.sent[comment] = txid
	return txid, nil
}

func (w *fakeWallet) FindComment(comment string) (string, bool, error) {
	txid, ok := w.sent[comment]
	return txid, ok, nil
}

var errTimeout = errors.New("timeout talking to nexad")
var errRejected = errors.New("invalid address")

func TestPayoutOnceAndNotAgain(t *testing.T) {
	s := openTest(t)
	credit(t, s, addrA, minPay, "mature")
	w := newWallet()
	res, err := account.RunPayouts(s, w, minPay)
	if err != nil {
		t.Fatal(err)
	}
	if res.Sent != 1 || w.sends != 1 {
		t.Fatalf("first pass sent %d wallet %d", res.Sent, w.sends)
	}
	res, err = account.RunPayouts(s, w, minPay)
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
	res, err := account.RunPayouts(s, w, minPay)
	if err != nil {
		t.Fatal(err)
	}
	if res.Deferred != 1 || res.Sent != 0 || w.sends != 1 {
		t.Fatalf("crash pass %+v sends %d", res, w.sends)
	}
	res, err = account.RunPayouts(s, w, minPay)
	if err != nil {
		t.Fatal(err)
	}
	if res.Sent != 1 || w.sends != 1 {
		t.Fatalf("reconcile sent %d wallet sends %d (want one send)", res.Sent, w.sends)
	}
	res, err = account.RunPayouts(s, w, minPay)
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
	res, err := account.RunPayouts(s, w, minPay)
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
	res, err := account.RunPayouts(s, w, minPay)
	if err != nil {
		t.Fatal(err)
	}
	if res.Failed != 1 || w.sends != 0 {
		t.Fatalf("fail pass %+v sends %d", res, w.sends)
	}
	res, err = account.RunPayouts(s, w, minPay)
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
	credits := []account.Credit{{Address: addrA, Amount: minPay, Kind: "miner"}, {Address: feeAddr, Amount: 0, Kind: "fee"}}
	// Drop the zero fee credit; Split never emits one, and a zero amount
	// would still be a credit row. Use a real fee.
	credits = []account.Credit{
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
