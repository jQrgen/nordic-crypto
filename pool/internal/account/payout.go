package account

import (
	"errors"
	"fmt"
	"strings"
)

// ErrBelowMin is returned when a balance is not yet payable.
var ErrBelowMin = errors.New("account: below minimum payout")

// Balance is a mature amount still owed to an address.
type Balance struct {
	Address string
	Amount  int64
}

// Payout is a reserved or completed payment.
type Payout struct {
	ID      int64
	Address string
	Amount  int64
	Key     string
	TxID    string
	Status  string
}

// Ledger is the durable book the payout runner updates.
type Ledger interface {
	Payable(minSats int64) ([]Balance, error)
	Reserve(address string, amount int64, key string) (int64, error)
	MarkSent(id int64, txid string) error
	MarkFailed(id int64) error
	Reserved() ([]Payout, error)
}

// Wallet sends coins from the node wallet and can find a send that already
// happened, matched by the comment stored with the payout.
type Wallet interface {
	Send(address string, sats int64, comment string) (txid string, err error)
	FindComment(comment string) (txid string, found bool, err error)
}

// Result counts what one payout pass did.
type Result struct {
	Sent     int
	Failed   int
	Deferred int
}

// RunPayouts pays every mature balance at or above minSats, once.
//
// A payout is reserved in the ledger before the node is asked to send.
// The reservation already reduces the payable balance, so a second pass
// cannot reserve the same coins. If the process dies after the node has
// accepted the transaction and before the ledger is updated, the next pass
// finds the wallet comment and records the txid instead of sending again.
// A definite wallet error marks the payout failed and returns the coins to
// the balance. A timeout or a dropped connection leaves the reservation in
// place so the next pass can reconcile it.
func RunPayouts(ledger Ledger, wallet Wallet, minSats int64) (Result, error) {
	var result Result
	if minSats < 0 {
		return result, fmt.Errorf("account: negative minimum")
	}
	pending, err := ledger.Reserved()
	if err != nil {
		return result, err
	}
	for _, p := range pending {
		done, err := finish(ledger, wallet, p)
		if err != nil {
			return result, err
		}
		result.Sent += done.Sent
		result.Failed += done.Failed
		result.Deferred += done.Deferred
	}
	due, err := ledger.Payable(minSats)
	if err != nil {
		return result, err
	}
	for _, b := range due {
		if b.Amount < minSats {
			continue
		}
		key, err := newKey()
		if err != nil {
			return result, err
		}
		id, err := ledger.Reserve(b.Address, b.Amount, key)
		if err != nil {
			if errors.Is(err, ErrBelowMin) {
				continue
			}
			return result, err
		}
		done, err := finish(ledger, wallet, Payout{ID: id, Address: b.Address, Amount: b.Amount, Key: key})
		if err != nil {
			return result, err
		}
		result.Sent += done.Sent
		result.Failed += done.Failed
		result.Deferred += done.Deferred
	}
	return result, nil
}

func finish(ledger Ledger, wallet Wallet, p Payout) (Result, error) {
	var result Result
	txid, found, err := wallet.FindComment(p.Key)
	if err != nil {
		return result, err
	}
	if found {
		if err := ledger.MarkSent(p.ID, txid); err != nil {
			return result, err
		}
		result.Sent++
		return result, nil
	}
	txid, err = wallet.Send(p.Address, p.Amount, p.Key)
	if err != nil {
		if ambiguous(err) {
			result.Deferred++
			return result, nil
		}
		if markErr := ledger.MarkFailed(p.ID); markErr != nil {
			return result, markErr
		}
		result.Failed++
		return result, nil
	}
	if txid == "" {
		result.Deferred++
		return result, nil
	}
	if err := ledger.MarkSent(p.ID, txid); err != nil {
		return result, err
	}
	result.Sent++
	return result, nil
}

func ambiguous(err error) bool {
	s := strings.ToLower(err.Error())
	return strings.Contains(s, "timeout") || strings.Contains(s, "eof") || strings.Contains(s, "connection")
}
