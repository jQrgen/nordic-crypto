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
	// Inputs are the outpoints reserved with this row.
	Inputs []string
	// Created is when the reservation was inserted. Release with confirm
	// "none" requires it to be at least the configured minimum age.
	Created time.Time
}

// Signed is a funded and signed payout transaction. TxIdem is GetIdem and
// does not change if the satisfier scripts change. TxID is GetId and is
// informational. Inputs are the prevout hashes the transaction spends.
// Raw is the hex that will be broadcast unchanged.
type Signed struct {
	TxID   string
	TxIdem string
	Raw    string
	Inputs []string
}

// MinConflictDepth is the smallest confirmation count of a competing
// spend that may release a payout. A shallower spend can still be reorged.
const MinConflictDepth int64 = 6

// TxState is a direct lookup of the stored txidem.
// Conflict means an input is spent by a transaction with a different
// txidem. SpendConfs is that spender's confirmation count.
// OnChain means this txidem is in a block, whatever its txid is.
type TxState struct {
	Payment
	InWallet    bool
	InMempool   bool
	OnChain     bool
	Conflict    bool
	SpendTxIdem string
	SpendConfs  int64
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
	// Reserve inserts the row and, when signed is set, its txidem, raw
	// hex, and input outpoints in the same database transaction. The
	// transaction must not have been broadcast yet.
	Reserve(address string, amount int64, key string, signed Signed) (int64, error)
	// ReservedOutpoints are the inputs of rows that are still reserved,
	// in review, or sent. Coin selection must skip them.
	ReservedOutpoints() ([]string, error)
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
	// return to the payable balance. Used when a different txidem has
	// spent an input at sufficient depth.
	Drop(id int64) error
}

// ErrOutpointTaken means another reservation already stored one of the
// signed transaction's inputs. The caller must not unlock those outpoints.
var ErrOutpointTaken = errors.New("account: outpoint already reserved")

// Wallet builds a payout transaction and can find that same transaction
// again by txidem. It does not search wallet comments.
type Wallet interface {
	// Prepare funds and signs a payout, skipping avoid. It locks the
	// inputs it selects and does not broadcast.
	Prepare(address string, sats int64, avoid []string) (Signed, error)
	// Broadcast submits the exact raw hex from Prepare.
	Broadcast(raw string) error
	// LookupTx reads the wallet, the txpool, and the chain for txidem.
	// An error means the lookup did not finish. A zero state means the
	// txidem was not found. txid is not a lookup key.
	LookupTx(txidem string) (TxState, error)
	// Lock calls lockunspent false. Unlock calls lockunspent true.
	Lock(outpoints []string) error
	Unlock(outpoints []string) error
}

// Result counts what one payout pass did.
type Result struct {
	Sent     int
	Failed   int
	Deferred int
}

// RunPayouts pays every mature balance at or above minSats, once.
//
// The signed transaction, including its input outpoints, is stored in
// the same database transaction as the reservation, and only then
// broadcast. A row that already has a txidem is never given a new
// transaction. Recovery looks that txidem up and, if it is absent,
// broadcasts the stored hex again. minConfs below 1 is treated as 1.
// conflictDepth below MinConflictDepth is raised to that floor.
//
// Coins return only when a different txidem has spent an input and that
// spend has at least conflictDepth confirmations. Until then the stored
// hex is broadcast again. Abandoning a transaction does not release it.
func RunPayouts(ledger Ledger, wallet Wallet, minSats, minConfs, conflictDepth int64) (Result, error) {
	if minSats < 0 {
		return Result{}, fmt.Errorf("account: negative minimum")
	}
	conflictDepth = floorDepth(conflictDepth)
	result, err := Reconcile(ledger, wallet, minConfs, conflictDepth)
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
		avoid, err := ledger.ReservedOutpoints()
		if err != nil {
			return result, err
		}
		signed, err := wallet.Prepare(b.Address, b.Amount, avoid)
		if err != nil {
			return result, err
		}
		if signed.TxIdem == "" || signed.Raw == "" || len(signed.Inputs) == 0 {
			return result, fmt.Errorf("account: signed payout has no txidem or inputs")
		}
		key, err := newKey()
		if err != nil {
			_ = wallet.Unlock(signed.Inputs)
			return result, err
		}
		id, err := ledger.Reserve(b.Address, b.Amount, key, signed)
		if err != nil {
			if errors.Is(err, ErrOutpointTaken) {
				result.Deferred++
				continue
			}
			_ = wallet.Unlock(signed.Inputs)
			if errors.Is(err, ErrBelowMin) {
				continue
			}
			return result, err
		}
		row := Payout{
			ID: id, Address: b.Address, Amount: b.Amount, Key: key,
			TxID: signed.TxID, TxIdem: signed.TxIdem, Raw: signed.Raw,
			Inputs: signed.Inputs, Status: "reserved",
		}
		done, err := publish(ledger, wallet, row, minConfs, conflictDepth)
		if err != nil {
			return result, err
		}
		result.Sent += done.Sent
		result.Failed += done.Failed
		result.Deferred += done.Deferred
	}
	return result, nil
}

func floorDepth(d int64) int64 {
	if d < MinConflictDepth {
		return MinConflictDepth
	}
	return d
}

// Reconcile matches reserved, review, and sent rows to the wallet. It
// does not create a new send. PayOnce calls this even when the hot
// wallet is over its cap, so an in-flight row is not stuck until someone
// sweeps the balance. lockunspent is memory only, so every unresolved
// outpoint is locked again before any lookup.
func Reconcile(ledger Ledger, wallet Wallet, minConfs, conflictDepth int64) (Result, error) {
	var result Result
	if minConfs < 1 {
		minConfs = 1
	}
	conflictDepth = floorDepth(conflictDepth)
	held, err := ledger.ReservedOutpoints()
	if err != nil {
		return result, err
	}
	if err := wallet.Lock(held); err != nil {
		return result, err
	}
	sent, err := ledger.Sent()
	if err != nil {
		return result, err
	}
	for _, p := range sent {
		done, err := recheckSent(ledger, wallet, p, minConfs, conflictDepth)
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
		done, err := finishExisting(ledger, wallet, p, minConfs, conflictDepth)
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
// A row with a txidem is never replaced with a new transaction.
func finishExisting(ledger Ledger, wallet Wallet, p Payout, minConfs, conflictDepth int64) (Result, error) {
	if p.TxIdem == "" {
		return holdUnbroadcast(ledger, p.ID)
	}
	return publish(ledger, wallet, p, minConfs, conflictDepth)
}

// publish broadcasts the stored hex when that txidem is not already a
// confirmed payment, then settles whatever the node reports. It does not sign.
func publish(ledger Ledger, wallet Wallet, p Payout, minConfs, conflictDepth int64) (Result, error) {
	var result Result
	st, err := wallet.LookupTx(p.TxIdem)
	if err != nil {
		result.Deferred++
		return result, nil
	}
	if shouldRelay(st, conflictDepth) {
		if p.Raw == "" {
			return holdUnbroadcast(ledger, p.ID)
		}
		st, err = relay(wallet, p)
		if err != nil {
			result.Deferred++
			return result, nil
		}
	}
	return applyState(ledger, wallet, p, st, minConfs, conflictDepth)
}

func recheckSent(ledger Ledger, wallet Wallet, p Payout, minConfs, conflictDepth int64) (Result, error) {
	var result Result
	if p.TxIdem == "" {
		if err := ledger.RevertSent(p.ID, "review"); err != nil {
			return result, err
		}
		result.Deferred++
		return result, nil
	}
	st, err := wallet.LookupTx(p.TxIdem)
	if err != nil {
		result.Deferred++
		return result, nil
	}
	if lost(st, conflictDepth) {
		return dropSpent(ledger, wallet, p)
	}
	if shouldRelay(st, conflictDepth) {
		if p.Raw == "" {
			if err := ledger.RevertSent(p.ID, "review"); err != nil {
				return result, err
			}
			result.Deferred++
			return result, nil
		}
		st, err = relay(wallet, p)
		if err != nil {
			result.Deferred++
			return result, nil
		}
		if lost(st, conflictDepth) {
			return dropSpent(ledger, wallet, p)
		}
		if !ours(st) || st.Confirmations < minConfs {
			if rev := ledger.RevertSent(p.ID, "reserved"); rev != nil {
				return result, rev
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
	if st.Confirmations >= conflictDepth {
		if err := wallet.Unlock(p.Inputs); err != nil {
			return result, err
		}
	}
	return result, nil
}

// dropSpent unlocks the reserved inputs and fails the row. A failed
// unlock leaves the row in place so the next pass can try again.
func dropSpent(ledger Ledger, wallet Wallet, p Payout) (Result, error) {
	if err := wallet.Unlock(p.Inputs); err != nil {
		return Result{}, err
	}
	if err := ledger.Drop(p.ID); err != nil {
		return Result{}, err
	}
	return Result{Failed: 1}, nil
}

func holdUnbroadcast(ledger Ledger, id int64) (Result, error) {
	var result Result
	if err := ledger.MarkReview(id); err != nil {
		return result, err
	}
	result.Deferred++
	return result, nil
}

// shouldRelay is true when the stored hex has to go out again.
// Confirmations of 0 always relay: abandontransaction removes the tx
// from the local mempool and leaves the wallet entry at depth 0.
// InWallet, InMempool, OnChain, and Conflict do not override that.
func shouldRelay(st TxState, conflictDepth int64) bool {
	if st.Confirmations == 0 {
		return true
	}
	return !ours(st) && !deep(st, conflictDepth)
}

// lost is a competing spend deep enough to release the coins.
// Depth 0 is not that spend, whatever other flags the wallet set.
func lost(st TxState, conflictDepth int64) bool {
	return st.Confirmations != 0 && deep(st, conflictDepth)
}

func relay(wallet Wallet, p Payout) (TxState, error) {
	if err := wallet.Broadcast(p.Raw); err != nil {
		return TxState{}, err
	}
	return wallet.LookupTx(p.TxIdem)
}

// ours is the stored txidem itself: in the wallet, the txpool, or a
// block, with a non-negative depth. A different txid on that txidem is
// still this payment. A conflict is not.
func ours(st TxState) bool {
	return (st.InWallet || st.InMempool || st.OnChain) && st.Confirmations >= 0 && !st.Conflict
}

// deep is a spend by a different txidem that has enough confirmations
// to release the coins. A shallower spend can still be reorged away.
func deep(st TxState, depth int64) bool {
	return st.Conflict && st.SpendConfs >= depth
}

func applyState(ledger Ledger, wallet Wallet, p Payout, st TxState, minConfs, conflictDepth int64) (Result, error) {
	if lost(st, conflictDepth) {
		return dropSpent(ledger, wallet, p)
	}
	pay := st.Payment
	if pay.TxID == "" {
		pay.TxID = p.TxID
	}
	// The stored txidem is the identifier. A lookup must not replace it.
	pay.TxIdem = p.TxIdem
	if !ours(st) {
		if p.Raw == "" || p.TxIdem == "" {
			return holdUnbroadcast(ledger, p.ID)
		}
		return Result{Deferred: 1}, nil
	}
	done, err := settle(ledger, p.ID, pay, minConfs)
	if err != nil {
		return done, err
	}
	if st.Confirmations >= conflictDepth {
		if err := wallet.Unlock(p.Inputs); err != nil {
			return done, err
		}
	}
	return done, nil
}

func settle(ledger Ledger, id int64, pay Payment, minConfs int64) (Result, error) {
	var result Result
	if pay.Confirmations < 0 {
		result.Deferred++
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
// "complete" marks the row sent when the stored txidem is in the wallet
// or in a block, is not a conflicting spend, and has at least minConfs
// confirmations. The txid on that row may change; the txidem does not.
// "release" returns the coins only in one of two cases: the row was never
// signed (no txid and no txidem) and the reservation is at least
// minNoneAge old (confirm "none"); or the operator names the stored
// txidem and a different txidem has spent an input with at least
// conflictDepth confirmations. Abandoning a transaction does not release
// it. A lookup that does not finish is not one of those cases.
func ResolveReview(book ReviewBook, wallet Wallet, id int64, action string, minConfs int64, confirm string, minNoneAge time.Duration, conflictDepth int64) error {
	if minConfs < 1 {
		minConfs = 1
	}
	conflictDepth = floorDepth(conflictDepth)
	p, err := book.Payout(id)
	if err != nil {
		return err
	}
	if p.Status != "review" && p.Status != "reserved" {
		return fmt.Errorf("account: payout %d is %s, not reserved or review", id, p.Status)
	}
	st, err := wallet.LookupTx(p.TxIdem)
	if err != nil {
		return err
	}
	switch action {
	case "complete":
		txid := st.TxID
		if txid == "" {
			txid = p.TxID
		}
		if !ours(st) || (!st.InWallet && !st.OnChain) || txid == "" {
			return fmt.Errorf("account: wallet has no confirmed send for payout %d", id)
		}
		if st.Confirmations < minConfs {
			return fmt.Errorf("account: payout %d has %d confirmations, want %d", id, st.Confirmations, minConfs)
		}
		if err := book.NotePayment(id, txid, p.TxIdem, st.Confirmations); err != nil {
			return err
		}
		if err := book.MarkSent(id, txid); err != nil {
			return err
		}
		if st.Confirmations >= conflictDepth {
			if err := wallet.Unlock(p.Inputs); err != nil {
				return err
			}
		}
		return nil
	case "release":
		confirm = strings.TrimSpace(confirm)
		if confirm == "" {
			return fmt.Errorf("account: release of payout %d requires confirmation of the expected txidem, or none", id)
		}
		if strings.EqualFold(confirm, "none") {
			if p.TxID != "" || p.TxIdem != "" {
				return fmt.Errorf("account: payout %d has txidem %s; confirm that id, not none", id, p.TxIdem)
			}
			if minNoneAge > 0 && (p.Created.IsZero() || time.Since(p.Created) < minNoneAge) {
				return fmt.Errorf("account: release of payout %d with confirm none requires the reservation to be at least %s old", id, minNoneAge)
			}
			return book.ReleaseReview(id)
		}
		if p.TxIdem == "" || !strings.EqualFold(confirm, p.TxIdem) {
			return fmt.Errorf("account: confirmation does not match payout %d", id)
		}
		if !deep(st, conflictDepth) {
			return fmt.Errorf("account: payout %d is not spent by a different txidem at %d confirmations", id, conflictDepth)
		}
		if err := wallet.Unlock(p.Inputs); err != nil {
			return err
		}
		return book.ReleaseReview(id)
	default:
		return fmt.Errorf("account: review action must be complete or release")
	}
}
