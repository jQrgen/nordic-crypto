package account

import (
	"errors"
	"testing"
)

// dyingBook fails Reserve after Prepare has returned a signed transaction.
// That is the crash between signing and the database commit.
type dyingBook struct{}

func (dyingBook) Payable(int64) ([]Balance, error) {
	return []Balance{{Address: "nexa:qqqqzqsrqszsvpcgpy9qkrqdpc83qygjzv5cxgkyhm", Amount: 100}}, nil
}

func (dyingBook) Reserve(string, int64, string, Signed) (int64, error) {
	return 0, errors.New("database commit lost")
}

func (dyingBook) MarkSent(int64, string) error                   { return nil }
func (dyingBook) MarkFailed(int64) error                         { return nil }
func (dyingBook) MarkReview(int64) error                         { return nil }
func (dyingBook) NotePayment(int64, string, string, int64) error { return nil }
func (dyingBook) Reserved() ([]Payout, error)                    { return nil, nil }
func (dyingBook) Sent() ([]Payout, error)                        { return nil, nil }
func (dyingBook) RevertSent(int64, string) error                 { return nil }
func (dyingBook) Drop(int64) error                               { return nil }

type crashWallet struct {
	prepares   int
	broadcasts int
}

func (w *crashWallet) Prepare(string, int64) (Signed, error) {
	w.prepares++
	return Signed{TxID: "txid-1", TxIdem: "idem-1", Raw: "deadbeef"}, nil
}

func (w *crashWallet) Broadcast(string) error {
	w.broadcasts++
	return nil
}

func (w *crashWallet) LookupTx(string, string, string) (TxState, error) {
	return TxState{}, nil
}

func TestCrashBeforeReserveDoesNotBroadcast(t *testing.T) {
	w := &crashWallet{}
	_, err := RunPayouts(dyingBook{}, w, 1, 1)
	if err == nil {
		t.Fatal("reserve failure was ignored")
	}
	if w.prepares != 1 || w.broadcasts != 0 {
		t.Fatalf("prepares %d broadcasts %d", w.prepares, w.broadcasts)
	}
}
