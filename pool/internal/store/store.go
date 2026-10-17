// Package store is the pool ledger. SQLite is the default because the pool
// runs on one machine next to nexad. Every balance is derived from credits
// minus payouts that are reserved or already sent.
package store

import (
	"database/sql"
	"errors"
	"fmt"
	"math"
	"os"
	"strings"
	"time"

	"github.com/jQrgen/nordic-crypto/pool/internal/account"
	"golang.org/x/sys/unix"
	_ "modernc.org/sqlite"
)

// ErrDuplicate is returned when a share was already recorded.
var ErrDuplicate = errors.New("store: duplicate share")

// Share is one accepted proof of work.
type Share struct {
	Address string
	Worker  string
	JobID   string
	Nonce   string
	PowHash string
	Work    uint64
	At      time.Time
}

// Block is a block the pool submitted.
type Block struct {
	ID            int64
	Height        int64
	Hash          string
	Finder        string
	Reward        int64
	Status        string
	Confirmations int64
	FoundAt       time.Time
}

// Miner is an address with recent work, used by the public stats API.
type Miner struct {
	Address string
	Workers int
	Work    uint64
}

// AddressStats is the per-address view.
type AddressStats struct {
	ValidShares   int64
	InvalidShares int64
	Work          uint64
	Mature        int64
	Immature      int64
	Paid          int64
	Reserved      int64
}

// Open opens (and creates) a SQLite database at path.
func Open(path string) (*Store, error) {
	db, err := sql.Open("sqlite", path+"?_pragma=busy_timeout(5000)&_pragma=foreign_keys(1)&_pragma=journal_mode(WAL)&_txlock=immediate")
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(4)
	db.SetMaxIdleConns(2)
	s := &Store{db: db, path: path}
	if err := s.migrate(); err != nil {
		db.Close()
		return nil, err
	}
	return s, nil
}

// Store is one open ledger.
type Store struct {
	db   *sql.DB
	path string
}

// Close closes the database.
func (s *Store) Close() error { return s.db.Close() }

func (s *Store) migrate() error {
	if _, err := s.db.Exec(schema); err != nil {
		return err
	}
	if err := s.ensureColumn("payouts", "txidem", "TEXT NOT NULL DEFAULT ''"); err != nil {
		return err
	}
	if err := s.ensureColumn("payouts", "confirmations", "INTEGER NOT NULL DEFAULT 0"); err != nil {
		return err
	}
	return s.ensureColumn("payouts", "raw_tx", "TEXT NOT NULL DEFAULT ''")
}

func (s *Store) ensureColumn(table, column, decl string) error {
	rows, err := s.db.Query(`PRAGMA table_info(` + table + `)`)
	if err != nil {
		return err
	}
	defer rows.Close()
	for rows.Next() {
		var cid int
		var name, ctype string
		var notnull, pk int
		var dflt any
		if err := rows.Scan(&cid, &name, &ctype, &notnull, &dflt, &pk); err != nil {
			return err
		}
		if name == column {
			return rows.Err()
		}
	}
	if err := rows.Err(); err != nil {
		return err
	}
	_, err = s.db.Exec(`ALTER TABLE ` + table + ` ADD COLUMN ` + column + ` ` + decl)
	return err
}

// LockPayouts takes an exclusive non-blocking lock so a second nexapool
// process cannot pay from the same ledger at the same time. The caller
// must call the returned function when the payout pass finishes.
func (s *Store) LockPayouts() (func(), error) {
	f, err := os.OpenFile(s.path+".payout.lock", os.O_CREATE|os.O_RDWR, 0o600)
	if err != nil {
		return nil, err
	}
	if err := unix.Flock(int(f.Fd()), unix.LOCK_EX|unix.LOCK_NB); err != nil {
		f.Close()
		return nil, fmt.Errorf("store: payout already running: %w", err)
	}
	return func() {
		_ = unix.Flock(int(f.Fd()), unix.LOCK_UN)
		f.Close()
	}, nil
}

const schema = `
CREATE TABLE IF NOT EXISTS shares (
    id INTEGER PRIMARY KEY,
    address TEXT NOT NULL,
    worker TEXT NOT NULL,
    job_id TEXT NOT NULL,
    nonce TEXT NOT NULL,
    pow_hash TEXT NOT NULL,
    work INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    UNIQUE(job_id, nonce),
    UNIQUE(pow_hash)
);
CREATE INDEX IF NOT EXISTS shares_time ON shares(created_at);
CREATE INDEX IF NOT EXISTS shares_address_time ON shares(address, created_at);

CREATE TABLE IF NOT EXISTS rejects (
    id INTEGER PRIMARY KEY,
    address TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS blocks (
    id INTEGER PRIMARY KEY,
    height INTEGER NOT NULL,
    hash TEXT NOT NULL UNIQUE,
    finder TEXT NOT NULL,
    reward INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    confirmations INTEGER NOT NULL DEFAULT 0,
    found_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS credits (
    id INTEGER PRIMARY KEY,
    block_id INTEGER NOT NULL REFERENCES blocks(id),
    address TEXT NOT NULL,
    amount INTEGER NOT NULL,
    kind TEXT NOT NULL,
    UNIQUE(block_id, address, kind)
);

CREATE TABLE IF NOT EXISTS payouts (
    id INTEGER PRIMARY KEY,
    address TEXT NOT NULL,
    amount INTEGER NOT NULL,
    status TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    txid TEXT,
    txidem TEXT NOT NULL DEFAULT '',
    confirmations INTEGER NOT NULL DEFAULT 0,
    raw_tx TEXT NOT NULL DEFAULT '',
    created_at INTEGER NOT NULL,
    sent_at INTEGER
);
CREATE TABLE IF NOT EXISTS payout_inputs (
    payout_id INTEGER NOT NULL REFERENCES payouts(id),
    outpoint TEXT NOT NULL,
    PRIMARY KEY(outpoint)
);
`

// AddShare records an accepted share. A repeated job and nonce, or a
// repeated proof-of-work hash, returns ErrDuplicate.
func (s *Store) AddShare(sh Share) error {
	if sh.At.IsZero() {
		sh.At = time.Now()
	}
	_, err := s.db.Exec(`INSERT INTO shares(address, worker, job_id, nonce, pow_hash, work, created_at)
		VALUES(?,?,?,?,?,?,?)`, sh.Address, sh.Worker, sh.JobID, sh.Nonce, sh.PowHash, sh.Work, sh.At.Unix())
	if err != nil && isUnique(err) {
		return ErrDuplicate
	}
	return err
}

// AddReject counts a rejected share for the address stats. Rejects do not
// enter the PPLNS window.
func (s *Store) AddReject(address string, at time.Time) error {
	if at.IsZero() {
		at = time.Now()
	}
	_, err := s.db.Exec(`INSERT INTO rejects(address, created_at) VALUES(?,?)`, address, at.Unix())
	return err
}

// ShareWindow returns the newest shares at or before t whose work sums to
// at least target, oldest first. It reads the table backwards in pages and
// stops when the window is full, so maturity does not load every share
// ever stored. filled is false when the history is shorter than target.
// oldestID is the smallest share id included, or 0 when the window is empty.
func (s *Store) ShareWindow(t time.Time, target uint64) (shares []account.Share, oldestID int64, filled bool, err error) {
	if target == 0 {
		return nil, 0, false, nil
	}
	const page = 1024
	var newestFirst []account.Share
	var sum uint64
	var cursor int64 = math.MaxInt64
	for {
		rows, err := s.db.Query(`SELECT id, address, work FROM shares
			WHERE created_at <= ? AND id < ? ORDER BY id DESC LIMIT ?`, t.Unix(), cursor, page)
		if err != nil {
			return nil, 0, false, err
		}
		n := 0
		done := false
		for rows.Next() {
			n++
			var id int64
			var sh account.Share
			if err := rows.Scan(&id, &sh.Address, &sh.Work); err != nil {
				rows.Close()
				return nil, 0, false, err
			}
			newestFirst = append(newestFirst, sh)
			oldestID = id
			if sum > math.MaxUint64-sh.Work {
				sum = math.MaxUint64
			} else {
				sum += sh.Work
			}
			cursor = id
			if sum >= target {
				filled = true
				done = true
				break
			}
		}
		err = rows.Err()
		rows.Close()
		if err != nil {
			return nil, 0, false, err
		}
		if done || n < page {
			break
		}
	}
	for i, j := 0, len(newestFirst)-1; i < j; i, j = i+1, j-1 {
		newestFirst[i], newestFirst[j] = newestFirst[j], newestFirst[i]
	}
	return newestFirst, oldestID, filled, nil
}

// PruneSharesBefore deletes shares older than the oldest share a filled
// PPLNS window still needs.
func (s *Store) PruneSharesBefore(id int64) error {
	if id <= 1 {
		return nil
	}
	_, err := s.db.Exec(`DELETE FROM shares WHERE id < ?`, id)
	return err
}

// PruneSharesBeforeTime deletes shares recorded before t. keepID, when
// positive, leaves that share and every newer id in place so a filled
// PPLNS window is not cut short by the clock.
func (s *Store) PruneSharesBeforeTime(t time.Time, keepID int64) error {
	if keepID > 0 {
		_, err := s.db.Exec(`DELETE FROM shares WHERE created_at < ? AND id < ?`, t.Unix(), keepID)
		return err
	}
	_, err := s.db.Exec(`DELETE FROM shares WHERE created_at < ?`, t.Unix())
	return err
}

// PruneRejectsBefore drops reject rows that can no longer affect the
// hashrate window.
func (s *Store) PruneRejectsBefore(t time.Time) error {
	_, err := s.db.Exec(`DELETE FROM rejects WHERE created_at < ?`, t.Unix())
	return err
}

// WorkSince sums difficulty micros per address since t.
func (s *Store) WorkSince(t time.Time) ([]Miner, error) {
	rows, err := s.db.Query(`SELECT address, COUNT(DISTINCT worker), COALESCE(SUM(work),0)
		FROM shares WHERE created_at >= ? GROUP BY address ORDER BY address`, t.Unix())
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []Miner
	for rows.Next() {
		var m Miner
		if err := rows.Scan(&m.Address, &m.Workers, &m.Work); err != nil {
			return nil, err
		}
		out = append(out, m)
	}
	return out, rows.Err()
}

// InsertBlock records a newly submitted block as immature.
func (s *Store) InsertBlock(b Block) (int64, error) {
	if b.FoundAt.IsZero() {
		b.FoundAt = time.Now()
	}
	if b.Status == "" {
		b.Status = "immature"
	}
	res, err := s.db.Exec(`INSERT INTO blocks(height, hash, finder, reward, status, confirmations, found_at)
		VALUES(?,?,?,?,?,?,?)`, b.Height, b.Hash, b.Finder, b.Reward, b.Status, b.Confirmations, b.FoundAt.Unix())
	if err != nil {
		return 0, err
	}
	return res.LastInsertId()
}

// ImmatureBlocks returns blocks that are not yet mature or orphaned.
func (s *Store) ImmatureBlocks() ([]Block, error) {
	return s.blocks(`SELECT id, height, hash, finder, reward, status, confirmations, found_at
		FROM blocks WHERE status = 'immature' ORDER BY height`)
}

// RecentBlocks returns the newest blocks.
func (s *Store) RecentBlocks(limit int) ([]Block, error) {
	if limit <= 0 {
		limit = 20
	}
	return s.blocks(`SELECT id, height, hash, finder, reward, status, confirmations, found_at
		FROM blocks ORDER BY height DESC LIMIT ?`, limit)
}

func (s *Store) blocks(q string, args ...any) ([]Block, error) {
	rows, err := s.db.Query(q, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []Block
	for rows.Next() {
		var b Block
		var found int64
		if err := rows.Scan(&b.ID, &b.Height, &b.Hash, &b.Finder, &b.Reward, &b.Status, &b.Confirmations, &found); err != nil {
			return nil, err
		}
		b.FoundAt = time.Unix(found, 0).UTC()
		out = append(out, b)
	}
	return out, rows.Err()
}

// SetConfirmations updates the confirmation count of an immature block.
func (s *Store) SetConfirmations(id, confs int64) error {
	_, err := s.db.Exec(`UPDATE blocks SET confirmations = ? WHERE id = ? AND status = 'immature'`, confs, id)
	return err
}

// MatureBlock credits a block exactly once. A second call is a no-op so a
// restarted maturity pass cannot pay the same coinbase twice.
func (s *Store) MatureBlock(id, reward int64, credits []account.Credit) error {
	tx, err := s.db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()
	res, err := tx.Exec(`UPDATE blocks SET status = 'mature', reward = ?, confirmations = CASE WHEN confirmations < 0 THEN confirmations ELSE confirmations END
		WHERE id = ? AND status = 'immature'`, reward, id)
	if err != nil {
		return err
	}
	n, err := res.RowsAffected()
	if err != nil {
		return err
	}
	if n == 0 {
		return nil
	}
	for _, c := range credits {
		if _, err := tx.Exec(`INSERT INTO credits(block_id, address, amount, kind) VALUES(?,?,?,?)`,
			id, c.Address, c.Amount, c.Kind); err != nil {
			return err
		}
	}
	return tx.Commit()
}

// OrphanBlock marks an immature block orphaned and drops its credits.
// A block that has already matured is left alone: those coins have passed
// the coinbase maturity the network itself requires before they can move.
func (s *Store) OrphanBlock(id int64) error {
	tx, err := s.db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()
	res, err := tx.Exec(`UPDATE blocks SET status = 'orphan' WHERE id = ? AND status != 'mature'`, id)
	if err != nil {
		return err
	}
	n, err := res.RowsAffected()
	if err != nil {
		return err
	}
	if n == 1 {
		if _, err := tx.Exec(`DELETE FROM credits WHERE block_id = ?`, id); err != nil {
			return err
		}
	}
	return tx.Commit()
}

// AddressStats summarises one miner.
func (s *Store) AddressStats(address string, since time.Time) (AddressStats, error) {
	var st AddressStats
	err := s.db.QueryRow(`SELECT COUNT(*), COALESCE(SUM(work),0) FROM shares WHERE address = ? AND created_at >= ?`,
		address, since.Unix()).Scan(&st.ValidShares, &st.Work)
	if err != nil {
		return st, err
	}
	if err := s.db.QueryRow(`SELECT COUNT(*) FROM rejects WHERE address = ? AND created_at >= ?`,
		address, since.Unix()).Scan(&st.InvalidShares); err != nil {
		return st, err
	}
	st.Mature, st.Immature, st.Paid, st.Reserved, err = s.balances(address)
	return st, err
}

func (s *Store) balances(address string) (mature, immature, paid, reserved int64, err error) {
	err = s.db.QueryRow(`SELECT
		COALESCE((SELECT SUM(c.amount) FROM credits c JOIN blocks b ON b.id = c.block_id
			WHERE c.address = ? AND b.status = 'mature'), 0),
		COALESCE((SELECT SUM(c.amount) FROM credits c JOIN blocks b ON b.id = c.block_id
			WHERE c.address = ? AND b.status = 'immature'), 0),
		COALESCE((SELECT SUM(amount) FROM payouts WHERE address = ? AND status = 'sent'), 0),
		COALESCE((SELECT SUM(amount) FROM payouts WHERE address = ? AND status IN ('reserved', 'review')), 0)`,
		address, address, address, address).Scan(&mature, &immature, &paid, &reserved)
	return mature, immature, paid, reserved, err
}

// ListedPayout is a payout the public API may show. The idempotency key
// stays in the database.
type ListedPayout struct {
	Address string
	Amount  int64
	TxID    string
	Status  string
	At      time.Time
}

// ListPayouts returns newest payouts. An empty address returns every address.
func (s *Store) ListPayouts(address string, limit int) ([]ListedPayout, error) {
	if limit <= 0 {
		limit = 20
	}
	q := `SELECT address, amount, COALESCE(txid,''), status, created_at FROM payouts`
	args := []any{}
	if address != "" {
		q += ` WHERE address = ?`
		args = append(args, address)
	}
	q += ` ORDER BY id DESC LIMIT ?`
	args = append(args, limit)
	rows, err := s.db.Query(q, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []ListedPayout
	for rows.Next() {
		var p ListedPayout
		var at int64
		if err := rows.Scan(&p.Address, &p.Amount, &p.TxID, &p.Status, &at); err != nil {
			return nil, err
		}
		p.At = time.Unix(at, 0).UTC()
		out = append(out, p)
	}
	return out, rows.Err()
}

// Payable implements account.Ledger. The amount is the mature credit minus
// every reserved or sent payout.
func (s *Store) Payable(minSats int64) ([]account.Balance, error) {
	rows, err := s.db.Query(`
		SELECT address, mature - COALESCE(held, 0) AS amount FROM (
			SELECT c.address AS address, SUM(c.amount) AS mature
			FROM credits c JOIN blocks b ON b.id = c.block_id
			WHERE b.status = 'mature' GROUP BY c.address
		) m
		LEFT JOIN (
			SELECT address, SUM(amount) AS held FROM payouts
			WHERE status IN ('reserved', 'sent', 'review') GROUP BY address
		) p USING (address)
		WHERE mature - COALESCE(held, 0) >= ?
		ORDER BY address`, minSats)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []account.Balance
	for rows.Next() {
		var b account.Balance
		if err := rows.Scan(&b.Address, &b.Amount); err != nil {
			return nil, err
		}
		out = append(out, b)
	}
	return out, rows.Err()
}

// Reserve implements account.Ledger. The balance check, the signed
// txidem and raw hex, and each input outpoint are one transaction, so
// the row exists before any broadcast and two callers cannot reserve
// the same coins or the same outpoint.
func (s *Store) Reserve(address string, amount int64, key string, signed account.Signed) (int64, error) {
	if amount <= 0 {
		return 0, account.ErrBelowMin
	}
	inputs := uniqueOutpoints(signed.Inputs)
	if signed.TxIdem != "" && len(inputs) == 0 {
		return 0, fmt.Errorf("store: signed payout has no inputs")
	}
	tx, err := s.db.Begin()
	if err != nil {
		return 0, err
	}
	defer tx.Rollback()
	var available int64
	if err := tx.QueryRow(`
		SELECT COALESCE((SELECT SUM(c.amount) FROM credits c JOIN blocks b ON b.id = c.block_id
			WHERE c.address = ? AND b.status = 'mature'), 0)
		- COALESCE((SELECT SUM(amount) FROM payouts WHERE address = ? AND status IN ('reserved','sent','review')), 0)`,
		address, address).Scan(&available); err != nil {
		return 0, err
	}
	if available < amount {
		return 0, account.ErrBelowMin
	}
	res, err := tx.Exec(`INSERT INTO payouts(address, amount, status, idempotency_key, txid, txidem, raw_tx, created_at)
		VALUES(?,?,'reserved',?,?,?,?,?)`, address, amount, key, signed.TxID, signed.TxIdem, signed.Raw, time.Now().Unix())
	if err != nil {
		return 0, err
	}
	id, err := res.LastInsertId()
	if err != nil {
		return 0, err
	}
	for _, op := range inputs {
		if _, err := tx.Exec(`INSERT INTO payout_inputs(payout_id, outpoint) VALUES(?,?)`, id, op); err != nil {
			if isUnique(err) && contains(strings.ToLower(err.Error()), "payout_inputs") {
				return 0, account.ErrOutpointTaken
			}
			return 0, err
		}
	}
	if err := tx.Commit(); err != nil {
		return 0, err
	}
	return id, nil
}

func uniqueOutpoints(in []string) []string {
	var out []string
	seen := map[string]bool{}
	for _, op := range in {
		op = strings.TrimSpace(op)
		if op == "" || seen[op] {
			continue
		}
		seen[op] = true
		out = append(out, op)
	}
	return out
}

// ReservedOutpoints implements account.Ledger. Failed rows are omitted
// so a released spend can be paid from other coins.
func (s *Store) ReservedOutpoints() ([]string, error) {
	rows, err := s.db.Query(`SELECT i.outpoint FROM payout_inputs i
		JOIN payouts p ON p.id = i.payout_id
		WHERE p.status IN ('reserved', 'review', 'sent')
		ORDER BY i.outpoint`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []string
	for rows.Next() {
		var op string
		if err := rows.Scan(&op); err != nil {
			return nil, err
		}
		out = append(out, op)
	}
	return out, rows.Err()
}

// OrphanInput is a payout_inputs row whose payout is gone or no longer
// reserved, in review, or sent. The outpoint is not held.
type OrphanInput struct {
	PayoutID int64
	Outpoint string
	Status   string
}

// OrphanedInputs lists payout_inputs rows that do not belong to an
// active payout. Failed rows and rows whose payout was removed are both
// included. Reserved, review, and sent inputs are not.
func (s *Store) OrphanedInputs() ([]OrphanInput, error) {
	rows, err := s.db.Query(`SELECT i.payout_id, i.outpoint, COALESCE(p.status, '')
		FROM payout_inputs i
		LEFT JOIN payouts p ON p.id = i.payout_id
		WHERE p.id IS NULL OR p.status NOT IN ('reserved', 'review', 'sent')
		ORDER BY i.payout_id, i.outpoint`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []OrphanInput
	for rows.Next() {
		var row OrphanInput
		if err := rows.Scan(&row.PayoutID, &row.Outpoint, &row.Status); err != nil {
			return nil, err
		}
		out = append(out, row)
	}
	return out, rows.Err()
}

// PruneOrphanedInputs deletes payout_inputs rows that are not held by a
// reserved, review, or sent payout. It returns how many rows were removed.
func (s *Store) PruneOrphanedInputs() (int64, error) {
	res, err := s.db.Exec(`DELETE FROM payout_inputs
		WHERE payout_id NOT IN (
			SELECT id FROM payouts WHERE status IN ('reserved', 'review', 'sent')
		)`)
	if err != nil {
		return 0, err
	}
	return res.RowsAffected()
}

// MarkSent implements account.Ledger. A review row can still be marked
// sent once the wallet shows the canonical txid and enough confirmations.
func (s *Store) MarkSent(id int64, txid string) error {
	res, err := s.db.Exec(`UPDATE payouts SET status = 'sent', txid = ?, sent_at = ?
		WHERE id = ? AND status IN ('reserved', 'review')`, txid, time.Now().Unix(), id)
	if err != nil {
		return err
	}
	n, err := res.RowsAffected()
	if err != nil {
		return err
	}
	if n == 0 {
		var status string
		err := s.db.QueryRow(`SELECT status FROM payouts WHERE id = ?`, id).Scan(&status)
		if err != nil {
			return err
		}
		if status == "sent" {
			return nil
		}
		return fmt.Errorf("store: payout %d is %s", id, status)
	}
	return nil
}

// MarkFailed implements account.Ledger. A failed payout no longer reduces
// the balance. A review row is not failed this way: those coins stay held
// until an operator has checked the wallet.
func (s *Store) MarkFailed(id int64) error {
	_, err := s.db.Exec(`UPDATE payouts SET status = 'failed' WHERE id = ? AND status = 'reserved'`, id)
	return err
}

// MarkReview implements account.Ledger. The coins stay deducted from the
// payable balance and the row is not sent again.
func (s *Store) MarkReview(id int64) error {
	_, err := s.db.Exec(`UPDATE payouts SET status = 'review' WHERE id = ? AND status = 'reserved'`, id)
	return err
}

// Payout loads one payout by id for the operator review command.
func (s *Store) Payout(id int64) (account.Payout, error) {
	var p account.Payout
	var created int64
	err := s.db.QueryRow(`SELECT id, address, amount, idempotency_key, COALESCE(txid,''), COALESCE(txidem,''), COALESCE(raw_tx,''), confirmations, status, created_at
		FROM payouts WHERE id = ?`, id).Scan(&p.ID, &p.Address, &p.Amount, &p.Key, &p.TxID, &p.TxIdem, &p.Raw, &p.Confirmations, &p.Status, &created)
	if err != nil {
		return account.Payout{}, err
	}
	p.Created = time.Unix(created, 0)
	inputs, err := s.inputsFor(p.ID)
	if err != nil {
		return account.Payout{}, err
	}
	p.Inputs = inputs
	return p, nil
}

// ReleaseReview implements account.ReviewBook. The row must be reserved
// or in review. The coins return to the payable balance. The caller has
// checked that this transaction was never signed, or that a different
// txidem spent an input at the configured depth.
func (s *Store) ReleaseReview(id int64) error {
	res, err := s.db.Exec(`UPDATE payouts SET status = 'failed' WHERE id = ? AND status IN ('review', 'reserved')`, id)
	if err != nil {
		return err
	}
	n, err := res.RowsAffected()
	if err != nil {
		return err
	}
	if n == 0 {
		return fmt.Errorf("store: payout %d is not reserved or in review", id)
	}
	return nil
}

// Sent implements account.Ledger.
func (s *Store) Sent() ([]account.Payout, error) {
	return s.payoutsByStatus("sent")
}

// RevertSent implements account.Ledger. status is reserved or review.
func (s *Store) RevertSent(id int64, status string) error {
	if status != "reserved" && status != "review" {
		return fmt.Errorf("store: cannot revert a sent payout to %s", status)
	}
	res, err := s.db.Exec(`UPDATE payouts SET status = ?, sent_at = NULL WHERE id = ? AND status = 'sent'`, status, id)
	if err != nil {
		return err
	}
	n, err := res.RowsAffected()
	if err != nil {
		return err
	}
	if n == 0 {
		return fmt.Errorf("store: payout %d is not sent", id)
	}
	return nil
}

// Drop implements account.Ledger. A deep spend by a different txidem
// is not left as paid.
func (s *Store) Drop(id int64) error {
	res, err := s.db.Exec(`UPDATE payouts SET status = 'failed', sent_at = NULL
		WHERE id = ? AND status IN ('reserved', 'review', 'sent')`, id)
	if err != nil {
		return err
	}
	n, err := res.RowsAffected()
	if err != nil {
		return err
	}
	if n == 0 {
		p, err := s.Payout(id)
		if err != nil {
			return err
		}
		if p.Status == "failed" {
			return nil
		}
		return fmt.Errorf("store: payout %d is %s", id, p.Status)
	}
	return nil
}

func (s *Store) payoutsByStatus(status string) ([]account.Payout, error) {
	rows, err := s.db.Query(`SELECT id, address, amount, idempotency_key, COALESCE(txid,''), COALESCE(txidem,''), COALESCE(raw_tx,''), confirmations, status
		FROM payouts WHERE status = ? ORDER BY id`, status)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []account.Payout
	for rows.Next() {
		var p account.Payout
		if err := rows.Scan(&p.ID, &p.Address, &p.Amount, &p.Key, &p.TxID, &p.TxIdem, &p.Raw, &p.Confirmations, &p.Status); err != nil {
			return nil, err
		}
		inputs, err := s.inputsFor(p.ID)
		if err != nil {
			return nil, err
		}
		p.Inputs = inputs
		out = append(out, p)
	}
	return out, rows.Err()
}

// NotePayment records a txid on a row that is not yet sent. The txid is
// informational. A different txidem does not replace the one stored with
// the reservation. Empty strings leave the stored identifier alone.
func (s *Store) NotePayment(id int64, txid, txidem string, confs int64) error {
	_, err := s.db.Exec(`UPDATE payouts SET
		txid = CASE WHEN ? != '' THEN ? ELSE txid END,
		txidem = CASE WHEN ? != '' AND (txidem = '' OR lower(txidem) = lower(?)) THEN ? ELSE txidem END,
		confirmations = ?
		WHERE id = ? AND status IN ('reserved', 'review')`,
		txid, txid, txidem, txidem, txidem, confs, id)
	return err
}

// Reserved implements account.Ledger. Review rows are included so a later
// pass can still match them to the wallet, and still will not send them.
func (s *Store) Reserved() ([]account.Payout, error) {
	rows, err := s.db.Query(`SELECT id, address, amount, idempotency_key, COALESCE(txid,''), COALESCE(txidem,''), COALESCE(raw_tx,''), confirmations, status
		FROM payouts WHERE status IN ('reserved', 'review') ORDER BY id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []account.Payout
	for rows.Next() {
		var p account.Payout
		if err := rows.Scan(&p.ID, &p.Address, &p.Amount, &p.Key, &p.TxID, &p.TxIdem, &p.Raw, &p.Confirmations, &p.Status); err != nil {
			return nil, err
		}
		inputs, err := s.inputsFor(p.ID)
		if err != nil {
			return nil, err
		}
		p.Inputs = inputs
		out = append(out, p)
	}
	return out, rows.Err()
}

func (s *Store) inputsFor(id int64) ([]string, error) {
	rows, err := s.db.Query(`SELECT outpoint FROM payout_inputs WHERE payout_id = ? ORDER BY outpoint`, id)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []string
	for rows.Next() {
		var op string
		if err := rows.Scan(&op); err != nil {
			return nil, err
		}
		out = append(out, op)
	}
	return out, rows.Err()
}

// PayoutsFor returns the newest payouts for an address.
func (s *Store) PayoutsFor(address string, limit int) ([]account.Payout, error) {
	if limit <= 0 {
		limit = 20
	}
	rows, err := s.db.Query(`SELECT id, address, amount, idempotency_key, COALESCE(txid,''), COALESCE(txidem,''), confirmations, status
		FROM payouts WHERE address = ? ORDER BY id DESC LIMIT ?`, address, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []account.Payout
	for rows.Next() {
		var p account.Payout
		if err := rows.Scan(&p.ID, &p.Address, &p.Amount, &p.Key, &p.TxID, &p.TxIdem, &p.Confirmations, &p.Status); err != nil {
			return nil, err
		}
		out = append(out, p)
	}
	return out, rows.Err()
}

// RecentPayouts returns the newest payouts across the pool.
func (s *Store) RecentPayouts(limit int) ([]account.Payout, error) {
	if limit <= 0 {
		limit = 20
	}
	rows, err := s.db.Query(`SELECT id, address, amount, idempotency_key, COALESCE(txid,''), COALESCE(txidem,''), confirmations, status
		FROM payouts ORDER BY id DESC LIMIT ?`, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []account.Payout
	for rows.Next() {
		var p account.Payout
		if err := rows.Scan(&p.ID, &p.Address, &p.Amount, &p.Key, &p.TxID, &p.TxIdem, &p.Confirmations, &p.Status); err != nil {
			return nil, err
		}
		out = append(out, p)
	}
	return out, rows.Err()
}

func isUnique(err error) bool {
	return err != nil && (contains(err.Error(), "UNIQUE") || contains(err.Error(), "unique"))
}

func contains(s, part string) bool {
	return len(s) >= len(part) && (s == part || len(part) == 0 ||
		(func() bool {
			for i := 0; i+len(part) <= len(s); i++ {
				if s[i:i+len(part)] == part {
					return true
				}
			}
			return false
		})())
}
