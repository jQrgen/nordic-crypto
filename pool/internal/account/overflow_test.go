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

type countingWallet struct{ sends int }

func (w *countingWallet) Send(string, int64, string) (Payment, error) {
	w.sends++
	return Payment{TxID: "tx", Confirmations: 1}, nil
}
func (w *countingWallet) Find(string, string) (Payment, bool, error) {
	return Payment{}, false, nil
}

func TestNegativePayoutIsNotSent(t *testing.T) {
	w := &countingWallet{}
	res, err := RunPayouts(rejectingLedger{}, w, 1, 1)
	if err != nil {
		t.Fatal(err)
	}
	if res.Sent != 0 || w.sends != 0 {
		t.Fatalf("sent %+v sends %d", res, w.sends)
	}
	if _, err := RunPayouts(rejectingLedger{}, w, -1, 1); err == nil {
		t.Fatal("negative minimum was accepted")
	}
}

type rejectingLedger struct{}

func (rejectingLedger) Payable(int64) ([]Balance, error) {
	return []Balance{{Address: "a", Amount: -5}}, nil
}
func (rejectingLedger) Reserve(string, int64, string) (int64, error) {
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
