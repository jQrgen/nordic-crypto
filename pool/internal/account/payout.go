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

// Payout is a reserved, held, or completed payment.
type Payout struct {
	ID            int64
	Address       string
	Amount        int64
	Key           string
	TxID          string
	TxIdem        string
	Confirmations int64
	Status        string
}

// Payment is a wallet send. TxID is the canonical transaction id.
type Payment struct {
	TxID          string
	TxIdem        string
	Confirmations int64
}

// Ledger is the durable book the payout runner updates.
type Ledger interface {
	Payable(minSats int64) ([]Balance, error)
	Reserve(address string, amount int64, key string) (int64, error)
	MarkSent(id int64, txid string) error
	MarkFailed(id int64) error
	MarkReview(id int64) error
	NotePayment(id int64, txid, txidem string, confs int64) error
	Reserved() ([]Payout, error)
	// Sent returns payouts already marked sent, so a later pass can
	// notice a transaction that dropped after its first confirmation.
	Sent() ([]Payout, error)
	// RevertSent moves a sent row back to reserved or review.
	RevertSent(id int64, status string) error
	// Drop marks a reserved, review, or sent row failed. The coins
	// return to the payable balance. Used when the wallet transaction
	// is conflicted.
	Drop(id int64) error
}

// Wallet sends coins and can find a send that already happened.
// Find reports found only after a complete search. An error means the
// search did not finish.
type Wallet interface {
	Send(address string, sats int64, comment string) (Payment, error)
	Find(comment, id string) (Payment, bool, error)
}

// Result counts what one payout pass did.
type Result struct {
	Sent     int
	Failed   int
	Deferred int
}

// RunPayouts pays every mature balance at or above minSats, once.
//
// The reservation row is written before the node is asked to send. That
// row is the idempotency record: reserved and review rows both reduce the
// payable balance. A row that already existed at the start of the pass is
// only reconciled. It is never sent again. A lookup that does not finish
// leaves the row reserved for the next pass. A completed search that does
// not find the send moves the row to review.
//
// A row created in this pass is sent at most once. A definite wallet
// rejection marks it failed and returns the coins. A timeout, a dropped
// connection, an empty id, or fewer than minConfs confirmations leaves
// the reservation in place. minConfs below 1 is treated as 1.
//
// Sent rows are rechecked. A transaction that later disappears moves
// back to review and is not sent again. Negative confirmations mark
// the row failed so the coins can be paid once more.
func RunPayouts(ledger Ledger, wallet Wallet, minSats, minConfs int64) (Result, error) {
	if minSats < 0 {
		return Result{}, fmt.Errorf("account: negative minimum")
	}
	result, err := Reconcile(ledger, wallet, minConfs)
	if err != nil {
		return result, err
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
		done, err := finishNew(ledger, wallet, Payout{ID: id, Address: b.Address, Amount: b.Amount, Key: key}, minConfs)
		if err != nil {
			return result, err
		}
		result.Sent += done.Sent
		result.Failed += done.Failed
		result.Deferred += done.Deferred
	}
	return result, nil
}

// Reconcile matches reserved, review, and sent rows to the wallet. It
// does not create a new send. PayOnce calls this even when the hot
// wallet is over its cap, so an in-flight row is not stuck until someone
// sweeps the balance.
func Reconcile(ledger Ledger, wallet Wallet, minConfs int64) (Result, error) {
	var result Result
	if minConfs < 1 {
		minConfs = 1
	}
	sent, err := ledger.Sent()
	if err != nil {
		return result, err
	}
	for _, p := range sent {
		done, err := recheckSent(ledger, wallet, p, minConfs)
		if err != nil {
			return result, err
		}
		result.Failed += done.Failed
		result.Deferred += done.Deferred
	}
	pending, err := ledger.Reserved()
	if err != nil {
		return result, err
	}
	for _, p := range pending {
		done, err := finishExisting(ledger, wallet, p, minConfs)
		if err != nil {
			return result, err
		}
		result.Sent += done.Sent
		result.Failed += done.Failed
		result.Deferred += done.Deferred
	}
	return result, nil
}

// finishExisting reconciles a row that survived a restart. It does not send.
func finishExisting(ledger Ledger, wallet Wallet, p Payout, minConfs int64) (Result, error) {
	var result Result
	pay, found, err := wallet.Find(p.Key, firstID(p))
	if err != nil {
		result.Deferred++
		return result, nil
	}
	if !found {
		if markErr := ledger.MarkReview(p.ID); markErr != nil {
			return result, markErr
		}
		result.Deferred++
		return result, nil
	}
	return settle(ledger, p.ID, pay, minConfs)
}

// finishNew sends a reservation that was created earlier in this call.
func finishNew(ledger Ledger, wallet Wallet, p Payout, minConfs int64) (Result, error) {
	var result Result
	pay, err := wallet.Send(p.Address, p.Amount, p.Key)
	if err != nil {
		txid, idem, held := heldPayment(err)
		if held || ambiguous(err) {
			if txid == "" {
				txid = pay.TxID
			}
			if idem == "" {
				idem = pay.TxIdem
			}
			if txid != "" || idem != "" {
				if noteErr := ledger.NotePayment(p.ID, txid, idem, pay.Confirmations); noteErr != nil {
					return result, noteErr
				}
			}
			result.Deferred++
			return result, nil
		}
		if markErr := ledger.MarkFailed(p.ID); markErr != nil {
			return result, markErr
		}
		result.Failed++
		return result, nil
	}
	return settle(ledger, p.ID, pay, minConfs)
}

func recheckSent(ledger Ledger, wallet Wallet, p Payout, minConfs int64) (Result, error) {
	var result Result
	pay, found, err := wallet.Find(p.Key, firstID(p))
	if err != nil {
		result.Deferred++
		return result, nil
	}
	if !found {
		if markErr := ledger.RevertSent(p.ID, "review"); markErr != nil {
			return result, markErr
		}
		result.Deferred++
		return result, nil
	}
	if pay.Confirmations < 0 {
		if markErr := ledger.Drop(p.ID); markErr != nil {
			return result, markErr
		}
		result.Failed++
		return result, nil
	}
	if pay.TxID == "" || pay.Confirmations < minConfs {
		if markErr := ledger.RevertSent(p.ID, "reserved"); markErr != nil {
			return result, markErr
		}
		if noteErr := ledger.NotePayment(p.ID, pay.TxID, pay.TxIdem, pay.Confirmations); noteErr != nil {
			return result, noteErr
		}
		result.Deferred++
		return result, nil
	}
	return result, nil
}

func settle(ledger Ledger, id int64, pay Payment, minConfs int64) (Result, error) {
	var result Result
	if pay.Confirmations < 0 {
		if err := ledger.Drop(id); err != nil {
			return result, err
		}
		result.Failed++
		return result, nil
	}
	if err := ledger.NotePayment(id, pay.TxID, pay.TxIdem, pay.Confirmations); err != nil {
		return result, err
	}
	if pay.TxID == "" || pay.Confirmations < minConfs {
		result.Deferred++
		return result, nil
	}
	if err := ledger.MarkSent(id, pay.TxID); err != nil {
		return result, err
	}
	result.Sent++
	return result, nil
}

func firstID(p Payout) string {
	if p.TxID != "" {
		return p.TxID
	}
	return p.TxIdem
}

type held interface {
	HeldPayment() (txid, txidem string)
}

func heldPayment(err error) (string, string, bool) {
	var h held
	if errors.As(err, &h) {
		txid, idem := h.HeldPayment()
		return txid, idem, true
	}
	return "", "", false
}

// ReviewBook is the slice of the ledger an operator uses to finish a
// review row. It is not the payout runner.
type ReviewBook interface {
	Payout(id int64) (Payout, error)
	NotePayment(id int64, txid, txidem string, confs int64) error
	MarkSent(id int64, txid string) error
	ReleaseReview(id int64) error
}

// ResolveReview applies an operator decision to one review row.
//
// "complete" marks the row sent when the wallet has the payment and at
// least minConfs confirmations. "release" marks it failed only when a
// finished search does not find the send, which returns the coins to the
// payable balance. Releasing a send the wallet still has would pay twice,
// so that is refused. confirm is required for release: it is the txid
// stored on the row, or the word "none" when that row has no txid. A
// search that does not finish is not a miss, and an empty confirm is not
// an acknowledgement.
func ResolveReview(book ReviewBook, wallet Wallet, id int64, action string, minConfs int64, confirm string) error {
	if minConfs < 1 {
		minConfs = 1
	}
	p, err := book.Payout(id)
	if err != nil {
		return err
	}
	if p.Status != "review" {
		return fmt.Errorf("account: payout %d is %s, not review", id, p.Status)
	}
	pay, found, err := wallet.Find(p.Key, firstID(p))
	if err != nil {
		return err
	}
	switch action {
	case "complete":
		if !found || pay.TxID == "" {
			return fmt.Errorf("account: wallet has no send for payout %d", id)
		}
		if pay.Confirmations < minConfs {
			return fmt.Errorf("account: payout %d has %d confirmations, want %d", id, pay.Confirmations, minConfs)
		}
		if err := book.NotePayment(id, pay.TxID, pay.TxIdem, pay.Confirmations); err != nil {
			return err
		}
		return book.MarkSent(id, pay.TxID)
	case "release":
		if found {
			return fmt.Errorf("account: wallet still has payout %d (%s); refusing to release", id, pay.TxID)
		}
		confirm = strings.TrimSpace(confirm)
		if confirm == "" {
			return fmt.Errorf("account: release of payout %d requires confirmation of the expected txid, or none", id)
		}
		if strings.EqualFold(confirm, "none") {
			if p.TxID != "" {
				return fmt.Errorf("account: payout %d has txid %s; confirm that id, not none", id, p.TxID)
			}
		} else if p.TxID == "" || !strings.EqualFold(confirm, p.TxID) {
			return fmt.Errorf("account: confirmation does not match payout %d", id)
		}
		return book.ReleaseReview(id)
	default:
		return fmt.Errorf("account: review action must be complete or release")
	}
}

func ambiguous(err error) bool {
	s := strings.ToLower(err.Error())
	return strings.Contains(s, "timeout") || strings.Contains(s, "eof") || strings.Contains(s, "connection") || strings.Contains(s, "send outcome unknown")
}
