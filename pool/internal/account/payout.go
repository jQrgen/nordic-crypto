package account

import (
	"errors"
	"fmt"
	"strings"
	"time"
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
	// Raw is the signed transaction hex stored before broadcast.
	Raw string
	// Created is when the reservation was inserted. Release with confirm
	// "none" requires it to be at least the configured minimum age.
	Created time.Time
}

// Signed is a funded and signed payout transaction. TxID is GetId and
// TxIdem is GetIdem. Raw is the hex that will be broadcast unchanged.
type Signed struct {
	TxID   string
	TxIdem string
	Raw    string
}

// TxState is a direct lookup of a stored payout transaction.
// Conflict means an input is spent by a different confirmed transaction,
// or the wallet records this transaction at a negative depth.
// OnChain means the transaction is in a block.
type TxState struct {
	Payment
	InWallet  bool
	InMempool bool
	OnChain   bool
	Abandoned bool
	Conflict  bool
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
	// Reserve inserts the row and, when signed is set, its txid and raw
	// hex in the same database transaction. The transaction must not
	// have been broadcast yet.
	Reserve(address string, amount int64, key string, signed Signed) (int64, error)
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

// Wallet builds a payout transaction and can find that same transaction
// again. It does not search wallet comments.
type Wallet interface {
	// Prepare funds and signs a payout. It does not broadcast.
	Prepare(address string, sats int64) (Signed, error)
	// Broadcast submits the exact raw hex from Prepare.
	Broadcast(raw string) error
	// LookupTx reads the wallet and the txpool for a stored id.
	// An error means the lookup did not finish. A zero state means
	// the transaction was not found.
	LookupTx(txid, txidem, raw string) (TxState, error)
}

// Result counts what one payout pass did.
type Result struct {
	Sent     int
	Failed   int
	Deferred int
}

// RunPayouts pays every mature balance at or above minSats, once.
//
// The signed transaction is stored in the same database transaction as
// the reservation, and only then broadcast. A row that already has a
// txid is never given a new transaction. Recovery looks that txid up in
// the wallet and the txpool and, if it is absent, broadcasts the stored
// hex again. minConfs below 1 is treated as 1.
//
// A conflicting confirmed spend, or an abandoned transaction, returns
// the coins. A row with no txid was never broadcast and stays on hold.
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
		signed, err := wallet.Prepare(b.Address, b.Amount)
		if err != nil {
			return result, err
		}
		if signed.TxID == "" || signed.Raw == "" {
			return result, fmt.Errorf("account: signed payout has no txid")
		}
		key, err := newKey()
		if err != nil {
			return result, err
		}
		id, err := ledger.Reserve(b.Address, b.Amount, key, signed)
		if err != nil {
			if errors.Is(err, ErrBelowMin) {
				continue
			}
			return result, err
		}
		row := Payout{
			ID: id, Address: b.Address, Amount: b.Amount, Key: key,
			TxID: signed.TxID, TxIdem: signed.TxIdem, Raw: signed.Raw, Status: "reserved",
		}
		done, err := publish(ledger, wallet, row, minConfs)
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

// finishExisting reconciles a row that survived a restart.
// A row with a txid is never replaced with a new transaction.
func finishExisting(ledger Ledger, wallet Wallet, p Payout, minConfs int64) (Result, error) {
	if p.TxID == "" {
		return holdUnbroadcast(ledger, p.ID)
	}
	return publish(ledger, wallet, p, minConfs)
}

// publish broadcasts the stored hex when the transaction is not already
// in the wallet or the txpool, then settles whatever the node reports.
func publish(ledger Ledger, wallet Wallet, p Payout, minConfs int64) (Result, error) {
	var result Result
	st, err := wallet.LookupTx(p.TxID, p.TxIdem, p.Raw)
	if err != nil {
		result.Deferred++
		return result, nil
	}
	if !seen(st) {
		if p.Raw == "" {
			return holdUnbroadcast(ledger, p.ID)
		}
		if err := wallet.Broadcast(p.Raw); err != nil {
			result.Deferred++
			return result, nil
		}
		st, err = wallet.LookupTx(p.TxID, p.TxIdem, p.Raw)
		if err != nil {
			result.Deferred++
			return result, nil
		}
	}
	return applyState(ledger, p, st, minConfs)
}

func recheckSent(ledger Ledger, wallet Wallet, p Payout, minConfs int64) (Result, error) {
	var result Result
	if p.TxID == "" {
		if err := ledger.RevertSent(p.ID, "review"); err != nil {
			return result, err
		}
		result.Deferred++
		return result, nil
	}
	st, err := wallet.LookupTx(p.TxID, p.TxIdem, p.Raw)
	if err != nil {
		result.Deferred++
		return result, nil
	}
	if st.Conflict || st.Abandoned {
		if err := ledger.Drop(p.ID); err != nil {
			return result, err
		}
		result.Failed++
		return result, nil
	}
	if !seen(st) {
		if p.Raw == "" {
			if err := ledger.RevertSent(p.ID, "review"); err != nil {
				return result, err
			}
			result.Deferred++
			return result, nil
		}
		if err := wallet.Broadcast(p.Raw); err != nil {
			result.Deferred++
			return result, nil
		}
		st, err = wallet.LookupTx(p.TxID, p.TxIdem, p.Raw)
		if err != nil || !seen(st) || st.Confirmations < minConfs {
			if err == nil {
				if rev := ledger.RevertSent(p.ID, "reserved"); rev != nil {
					return result, rev
				}
			}
			result.Deferred++
			return result, nil
		}
	}
	if st.Confirmations < minConfs {
		if err := ledger.RevertSent(p.ID, "reserved"); err != nil {
			return result, err
		}
		result.Deferred++
		return result, nil
	}
	return result, nil
}

func holdUnbroadcast(ledger Ledger, id int64) (Result, error) {
	var result Result
	if err := ledger.MarkReview(id); err != nil {
		return result, err
	}
	result.Deferred++
	return result, nil
}

func seen(st TxState) bool {
	return st.InWallet || st.InMempool || st.OnChain || st.Conflict || st.Abandoned
}

func applyState(ledger Ledger, p Payout, st TxState, minConfs int64) (Result, error) {
	if st.Conflict || st.Abandoned {
		if err := ledger.Drop(p.ID); err != nil {
			return Result{}, err
		}
		return Result{Failed: 1}, nil
	}
	pay := st.Payment
	if pay.TxID == "" {
		pay.TxID = p.TxID
	}
	if pay.TxIdem == "" {
		pay.TxIdem = p.TxIdem
	}
	if !st.InWallet && !st.InMempool && !st.OnChain {
		return holdUnbroadcast(ledger, p.ID)
	}
	return settle(ledger, p.ID, pay, minConfs)
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

// ReviewBook is the slice of the ledger an operator uses to finish a
// reserved or review row. It is not the payout runner.
type ReviewBook interface {
	Payout(id int64) (Payout, error)
	NotePayment(id int64, txid, txidem string, confs int64) error
	MarkSent(id int64, txid string) error
	ReleaseReview(id int64) error
}

// ResolveReview applies an operator decision to one reserved or review row.
//
// "complete" marks the row sent when that stored transaction is in the
// wallet or in a block, is not abandoned or conflicted, and has at least
// minConfs confirmations. "release" returns the coins only in one of
// three cases: the row has no txid and the reservation is at least
// minNoneAge old (confirm "none"); the operator names the stored txid and
// that transaction is abandoned; or the operator names the stored txid and
// an input is spent by a different confirmed transaction. A lookup that
// does not finish is not one of those cases.
func ResolveReview(book ReviewBook, wallet Wallet, id int64, action string, minConfs int64, confirm string, minNoneAge time.Duration) error {
	if minConfs < 1 {
		minConfs = 1
	}
	p, err := book.Payout(id)
	if err != nil {
		return err
	}
	if p.Status != "review" && p.Status != "reserved" {
		return fmt.Errorf("account: payout %d is %s, not reserved or review", id, p.Status)
	}
	st, err := wallet.LookupTx(p.TxID, p.TxIdem, p.Raw)
	if err != nil {
		return err
	}
	switch action {
	case "complete":
		if st.Conflict || st.Abandoned || (!st.InWallet && !st.OnChain) || st.TxID == "" {
			return fmt.Errorf("account: wallet has no confirmed send for payout %d", id)
		}
		if st.Confirmations < minConfs {
			return fmt.Errorf("account: payout %d has %d confirmations, want %d", id, st.Confirmations, minConfs)
		}
		txid, idem := st.TxID, st.TxIdem
		if idem == "" {
			idem = p.TxIdem
		}
		if err := book.NotePayment(id, txid, idem, st.Confirmations); err != nil {
			return err
		}
		return book.MarkSent(id, txid)
	case "release":
		confirm = strings.TrimSpace(confirm)
		if confirm == "" {
			return fmt.Errorf("account: release of payout %d requires confirmation of the expected txid, or none", id)
		}
		if strings.EqualFold(confirm, "none") {
			if p.TxID != "" {
				return fmt.Errorf("account: payout %d has txid %s; confirm that id, not none", id, p.TxID)
			}
			if minNoneAge > 0 && (p.Created.IsZero() || time.Since(p.Created) < minNoneAge) {
				return fmt.Errorf("account: release of payout %d with confirm none requires the reservation to be at least %s old", id, minNoneAge)
			}
			return book.ReleaseReview(id)
		}
		if p.TxID == "" || !strings.EqualFold(confirm, p.TxID) {
			return fmt.Errorf("account: confirmation does not match payout %d", id)
		}
		if !st.Abandoned && !st.Conflict {
			return fmt.Errorf("account: payout %d (%s) is not abandoned and no input is spent by a different confirmed transaction", id, p.TxID)
		}
		return book.ReleaseReview(id)
	default:
		return fmt.Errorf("account: review action must be complete or release")
	}
}
