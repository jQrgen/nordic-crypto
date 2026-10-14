package store

import (
	"errors"
	"fmt"
	"strings"
	"sync"
	"sync/atomic"
	"testing"

	"github.com/jQrgen/nordic-crypto/pool/internal/account"
)

type safeWallet struct {
	mu         sync.Mutex
	prepares   atomic.Int32
	broadcasts atomic.Int32
	next       atomic.Int32
	txs        []*fakeTx
}

func (w *safeWallet) Prepare(string, int64, []string) (account.Signed, error) {
	n := w.next.Add(1)
	w.prepares.Add(1)
	tx := &fakeTx{txid: fmt.Sprintf("tx-%d", n), idem: fmt.Sprintf("idem-%d", n), raw: fmt.Sprintf("raw-%d", n)}
	w.mu.Lock()
	w.txs = append(w.txs, tx)
	w.mu.Unlock()
	return account.Signed{TxID: tx.txid, TxIdem: tx.idem, Raw: tx.raw, Inputs: []string{tx.raw}}, nil
}

func (w *safeWallet) Lock([]string) error   { return nil }
func (w *safeWallet) Unlock([]string) error { return nil }

func (w *safeWallet) Broadcast(raw string) error {
	w.mu.Lock()
	defer w.mu.Unlock()
	for _, tx := range w.txs {
		if tx.raw == raw {
			tx.visible = true
			w.broadcasts.Add(1)
			return nil
		}
	}
	return errors.New("unknown raw transaction")
}

func (w *safeWallet) LookupTx(idem string) (account.TxState, error) {
	w.mu.Lock()
	defer w.mu.Unlock()
	for _, tx := range w.txs {
		if tx.idem == idem {
			if !tx.visible {
				return account.TxState{}, nil
			}
			return account.TxState{
				Payment:  account.Payment{TxID: tx.txid, TxIdem: tx.idem, Confirmations: 1},
				InWallet: true,
			}, nil
		}
	}
	return account.TxState{}, nil
}

func TestConcurrentPayoutReservesTheBalanceOnce(t *testing.T) {
	s := openTest(t)
	credit(t, s, addrA, minPay, "mature")
	w := &safeWallet{}
	var wg sync.WaitGroup
	start := make(chan struct{})
	var errMu sync.Mutex
	var errs []error
	for i := 0; i < 8; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			<-start
			if _, err := account.RunPayouts(s, w, minPay, 1, 10); err != nil {
				errMu.Lock()
				errs = append(errs, err)
				errMu.Unlock()
			}
		}()
	}
	close(start)
	wg.Wait()
	for _, err := range errs {
		if !strings.Contains(err.Error(), "SQLITE_BUSY") && !strings.Contains(err.Error(), "database is locked") {
			t.Fatalf("unexpected payout error %v", err)
		}
	}
	// Signing happens before Reserve, so overlapping runs can Prepare more
	// than once. Only the run that commits the reservation broadcasts.
	if got := w.broadcasts.Load(); got != 1 {
		t.Fatalf("broadcasts %d, want 1 (prepares %d, busy errors %d)", got, w.prepares.Load(), len(errs))
	}
	prepared := w.prepares.Load()
	res, err := account.RunPayouts(s, w, minPay, 1, 10)
	if err != nil {
		t.Fatal(err)
	}
	if res.Sent != 0 || w.broadcasts.Load() != 1 || w.prepares.Load() != prepared {
		t.Fatalf("later pass signed again: %+v prepares %d broadcasts %d", res, w.prepares.Load(), w.broadcasts.Load())
	}
}

// blindWallet signs a transaction, stores it, then fails the broadcast.
// The next pass must broadcast that same hex and must not sign another.
type blindWallet struct {
	mu         sync.Mutex
	prepares   int
	broadcasts int
	raw        string
}

func (w *blindWallet) Prepare(string, int64, []string) (account.Signed, error) {
	w.mu.Lock()
	defer w.mu.Unlock()
	w.prepares++
	w.raw = "raw-blind"
	return account.Signed{TxID: "txid-blind", TxIdem: "idem-blind", Raw: w.raw, Inputs: []string{"out-blind"}}, nil
}

func (w *blindWallet) Broadcast(raw string) error {
	w.mu.Lock()
	defer w.mu.Unlock()
	w.broadcasts++
	if raw != w.raw {
		return errors.New("broadcast of a different transaction")
	}
	return errors.New("timeout talking to nexad")
}

func (w *blindWallet) LookupTx(string) (account.TxState, error) {
	return account.TxState{}, nil
}
func (w *blindWallet) Lock([]string) error   { return nil }
func (w *blindWallet) Unlock([]string) error { return nil }

func TestBlindReconcileDoesNotSendTheReservedPayoutAgain(t *testing.T) {
	s := openTest(t)
	credit(t, s, addrA, minPay, "mature")
	w := &blindWallet{}
	first, err := account.RunPayouts(s, w, minPay, 1, 10)
	if err != nil {
		t.Fatal(err)
	}
	if first.Deferred != 1 || w.prepares != 1 || w.broadcasts != 1 {
		t.Fatalf("first %+v prepares %d broadcasts %d", first, w.prepares, w.broadcasts)
	}
	second, err := account.RunPayouts(s, w, minPay, 1, 10)
	if err != nil {
		t.Fatal(err)
	}
	if w.prepares != 1 || w.broadcasts != 2 || second.Sent != 0 {
		t.Fatalf("reconcile signed a new transaction: %+v prepares %d broadcasts %d", second, w.prepares, w.broadcasts)
	}
	var status, txid string
	if err := s.db.QueryRow(`SELECT status, txid FROM payouts`).Scan(&status, &txid); err != nil {
		t.Fatal(err)
	}
	if status != "reserved" || txid != "txid-blind" {
		t.Fatalf("status %s txid %s", status, txid)
	}
}
