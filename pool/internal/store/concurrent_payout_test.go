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

func (w *safeWallet) Send(address string, sats int64, comment string) (string, error) {
	w.mu.Lock()
	defer w.mu.Unlock()
	w.sends.Add(1)
	if w.sent == nil {
		w.sent = map[string]string{}
	}
	txid := "tx-" + comment
	w.sent[comment] = txid
	return txid, nil
}

func (w *safeWallet) FindComment(comment string) (string, bool, error) {
	w.mu.Lock()
	defer w.mu.Unlock()
	txid, ok := w.sent[comment]
	return txid, ok, nil
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
			if _, err := account.RunPayouts(s, w, minPay); err != nil {
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
	res, err := account.RunPayouts(s, w, minPay)
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

func (w *blindWallet) Send(string, int64, string) (string, error) {
	w.mu.Lock()
	w.sends++
	w.mu.Unlock()
	return "", errors.New("timeout talking to nexad")
}

func (w *blindWallet) FindComment(string) (string, bool, error) {
	return "", false, nil
}

func TestBlindReconcileSendsTheReservedPayoutAgain(t *testing.T) {
	s := openTest(t)
	credit(t, s, addrA, minPay, "mature")
	w := &blindWallet{}
	first, err := account.RunPayouts(s, w, minPay)
	if err != nil {
		t.Fatal(err)
	}
	if first.Deferred != 1 || w.sends != 1 {
		t.Fatalf("first %+v sends %d", first, w.sends)
	}
	second, err := account.RunPayouts(s, w, minPay)
	if err != nil {
		t.Fatal(err)
	}
	if w.sends != 2 || second.Deferred != 1 {
		t.Fatalf("reconcile did not send again: %+v sends %d", second, w.sends)
	}
}
