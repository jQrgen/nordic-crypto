package store

import (
	"errors"
	"strings"
	"sync"
	"sync/atomic"
	"testing"

	"github.com/jQrgen/nordic-crypto/pool/internal/account"
)

type safeWallet struct {
	mu    sync.Mutex
	sends atomic.Int32
	sent  map[string]string
}

func (w *safeWallet) Send(address string, sats int64, comment string) (account.Payment, error) {
	w.mu.Lock()
	defer w.mu.Unlock()
	w.sends.Add(1)
	if w.sent == nil {
		w.sent = map[string]string{}
	}
	txid := "tx-" + comment
	w.sent[comment] = txid
	return account.Payment{TxID: txid, TxIdem: "idem-" + comment, Confirmations: 1}, nil
}

func (w *safeWallet) Find(comment, id string) (account.Payment, bool, error) {
	w.mu.Lock()
	defer w.mu.Unlock()
	txid, ok := w.sent[comment]
	if !ok {
		return account.Payment{}, false, nil
	}
	return account.Payment{TxID: txid, TxIdem: "idem-" + comment, Confirmations: 1}, true, nil
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
			if _, err := account.RunPayouts(s, w, minPay, 1); err != nil {
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
	// Overlapping runs fail closed: one send, and the others return
	// SQLITE_BUSY instead of reserving the same balance. busy_timeout does
	// not absorb the contention; the error comes back immediately.
	if got := w.sends.Load(); got != 1 {
		t.Fatalf("wallet sends %d, want 1 (busy errors %d)", got, len(errs))
	}
	res, err := account.RunPayouts(s, w, minPay, 1)
	if err != nil {
		t.Fatal(err)
	}
	if res.Sent != 0 || w.sends.Load() != 1 {
		t.Fatalf("later pass sent again: %+v sends %d", res, w.sends.Load())
	}
}

// blindWallet accepts the send and then cannot find it, which is what
// listtransactions does once the comment scrolls out of the 200-row window.
type blindWallet struct {
	mu    sync.Mutex
	sends int
}

func (w *blindWallet) Send(string, int64, string) (account.Payment, error) {
	w.mu.Lock()
	w.sends++
	w.mu.Unlock()
	return account.Payment{}, errors.New("timeout talking to nexad")
}

func (w *blindWallet) Find(string, string) (account.Payment, bool, error) {
	return account.Payment{}, false, nil
}

// The timeout is ambiguous, so the first pass keeps the reservation. A
// completed search that still cannot see the comment moves the row to
// review. It must not transmit the payout again.
func TestBlindReconcileDoesNotSendTheReservedPayoutAgain(t *testing.T) {
	s := openTest(t)
	credit(t, s, addrA, minPay, "mature")
	w := &blindWallet{}
	first, err := account.RunPayouts(s, w, minPay, 1)
	if err != nil {
		t.Fatal(err)
	}
	if first.Deferred != 1 || w.sends != 1 {
		t.Fatalf("first %+v sends %d", first, w.sends)
	}
	second, err := account.RunPayouts(s, w, minPay, 1)
	if err != nil {
		t.Fatal(err)
	}
	if w.sends != 1 || second.Sent != 0 {
		t.Fatalf("reconcile sent again: %+v sends %d", second, w.sends)
	}
	var status string
	if err := s.db.QueryRow(`SELECT status FROM payouts`).Scan(&status); err != nil {
		t.Fatal(err)
	}
	if status != "review" {
		t.Fatalf("status %s, want review", status)
	}
}
