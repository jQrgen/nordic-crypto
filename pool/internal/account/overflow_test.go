package account

import (
	"math"
	"testing"
)

func TestSplitDoesNotPayWrappedWork(t *testing.T) {
	shares := []Share{
		{Address: "a", Work: math.MaxUint64 - 5},
		{Address: "b", Work: 10},
	}
	credits, err := Split(10_000, 1, "fee", shares)
	if err == nil {
		var sum int64
		for _, c := range credits {
			if c.Amount < 0 {
				t.Fatalf("negative credit %+v", c)
			}
			sum += c.Amount
		}
		if sum != 10_000 {
			t.Fatalf("wrapped split paid %d from credits %+v", sum, credits)
		}
		t.Fatal("wrapped uint64 work was split without an error")
	}
}

type countingWallet struct{ prepares int }

func (w *countingWallet) Prepare(string, int64, []string) (Signed, error) {
	w.prepares++
	return Signed{TxID: "tx", TxIdem: "idem", Raw: "raw", Inputs: []string{"out"}}, nil
}
func (w *countingWallet) Broadcast(string) error           { return nil }
func (w *countingWallet) LookupTx(string) (TxState, error) { return TxState{}, nil }
func (w *countingWallet) Lock([]string) error              { return nil }
func (w *countingWallet) Unlock([]string) error            { return nil }

func TestNegativePayoutIsNotSent(t *testing.T) {
	w := &countingWallet{}
	res, err := RunPayouts(rejectingLedger{}, w, 1, 1, 10)
	if err != nil {
		t.Fatal(err)
	}
	if res.Sent != 0 || w.prepares != 0 {
		t.Fatalf("sent %+v prepares %d", res, w.prepares)
	}
	if _, err := RunPayouts(rejectingLedger{}, w, -1, 1, 10); err == nil {
		t.Fatal("negative minimum was accepted")
	}
}

type rejectingLedger struct{}

func (rejectingLedger) Payable(int64) ([]Balance, error) {
	return []Balance{{Address: "a", Amount: -5}}, nil
}
func (rejectingLedger) ReservedOutpoints() ([]string, error) { return nil, nil }
func (rejectingLedger) Reserve(string, int64, string, Signed) (int64, error) {
	return 0, ErrBelowMin
}
func (rejectingLedger) MarkSent(int64, string) error { return nil }
func (rejectingLedger) MarkFailed(int64) error       { return nil }
func (rejectingLedger) MarkReview(int64) error       { return nil }
func (rejectingLedger) NotePayment(int64, string, string, int64) error {
	return nil
}
func (rejectingLedger) Reserved() ([]Payout, error)    { return nil, nil }
func (rejectingLedger) Sent() ([]Payout, error)        { return nil, nil }
func (rejectingLedger) RevertSent(int64, string) error { return nil }
func (rejectingLedger) Drop(int64) error               { return nil }
