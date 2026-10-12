// Package store is the pool ledger. SQLite is the default because the pool
// runs on one machine next to nexad. Every balance is derived from credits
// minus payouts that are reserved or already sent.
package store

import (
	"database/sql"
	"errors"
	"fmt"
	"time"

	"github.com/jQrgen/nordic-crypto/pool/internal/account"
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
	db, err := sql.Open("sqlite", path+"?_pragma=busy_timeout(5000)&_pragma=foreign_keys(1)&_pragma=journal_mode(WAL)")
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(4)
	db.SetMaxIdleConns(2)
	s := &Store{db: db}
	if err := s.migrate(); err != nil {
		db.Close()
		return nil, err
	}
	return s, nil
}

// Store is one open ledger.
type Store struct{ db *sql.DB }

// Close closes the database.
func (s *Store) Close() error { return s.db.Close() }

func (s *Store) migrate() error {
	_, err := s.db.Exec(schema)
	return err
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
    created_at INTEGER NOT NULL,
    sent_at INTEGER
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

// SharesBefore returns accepted shares at or before t, oldest first.
func (s *Store) SharesBefore(t time.Time) ([]account.Share, error) {
	rows, err := s.db.Query(`SELECT address, work FROM shares WHERE created_at <= ? ORDER BY id`, t.Unix())
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []account.Share
	for rows.Next() {
		var sh account.Share
		if err := rows.Scan(&sh.Address, &sh.Work); err != nil {
			return nil, err
		}
		out = append(out, sh)
	}
	return out, rows.Err()
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
		COALESCE((SELECT SUM(amount) FROM payouts WHERE address = ? AND status = 'reserved'), 0)`,
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
			WHERE status IN ('reserved', 'sent') GROUP BY address
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

// Reserve implements account.Ledger. The insert and the balance check are
// one transaction, so two callers cannot reserve the same coins.
func (s *Store) Reserve(address string, amount int64, key string) (int64, error) {
	if amount <= 0 {
		return 0, account.ErrBelowMin
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
		- COALESCE((SELECT SUM(amount) FROM payouts WHERE address = ? AND status IN ('reserved','sent')), 0)`,
		address, address).Scan(&available); err != nil {
		return 0, err
	}
	if available < amount {
		return 0, account.ErrBelowMin
	}
	res, err := tx.Exec(`INSERT INTO payouts(address, amount, status, idempotency_key, created_at)
		VALUES(?,?,'reserved',?,?)`, address, amount, key, time.Now().Unix())
	if err != nil {
		return 0, err
	}
	id, err := res.LastInsertId()
	if err != nil {
		return 0, err
	}
	if err := tx.Commit(); err != nil {
		return 0, err
	}
	return id, nil
}

// MarkSent implements account.Ledger.
func (s *Store) MarkSent(id int64, txid string) error {
	res, err := s.db.Exec(`UPDATE payouts SET status = 'sent', txid = ?, sent_at = ?
		WHERE id = ? AND status = 'reserved'`, txid, time.Now().Unix(), id)
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
// the balance.
func (s *Store) MarkFailed(id int64) error {
	_, err := s.db.Exec(`UPDATE payouts SET status = 'failed' WHERE id = ? AND status = 'reserved'`, id)
	return err
}

// Reserved implements account.Ledger.
func (s *Store) Reserved() ([]account.Payout, error) {
	rows, err := s.db.Query(`SELECT id, address, amount, idempotency_key, COALESCE(txid,''), status
		FROM payouts WHERE status = 'reserved' ORDER BY id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []account.Payout
	for rows.Next() {
		var p account.Payout
		if err := rows.Scan(&p.ID, &p.Address, &p.Amount, &p.Key, &p.TxID, &p.Status); err != nil {
			return nil, err
		}
		out = append(out, p)
	}
	return out, rows.Err()
}

// PayoutsFor returns the newest payouts for an address.
func (s *Store) PayoutsFor(address string, limit int) ([]account.Payout, error) {
	if limit <= 0 {
		limit = 20
	}
	rows, err := s.db.Query(`SELECT id, address, amount, idempotency_key, COALESCE(txid,''), status
		FROM payouts WHERE address = ? ORDER BY id DESC LIMIT ?`, address, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []account.Payout
	for rows.Next() {
		var p account.Payout
		if err := rows.Scan(&p.ID, &p.Address, &p.Amount, &p.Key, &p.TxID, &p.Status); err != nil {
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
	rows, err := s.db.Query(`SELECT id, address, amount, idempotency_key, COALESCE(txid,''), status
		FROM payouts ORDER BY id DESC LIMIT ?`, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []account.Payout
	for rows.Next() {
		var p account.Payout
		if err := rows.Scan(&p.ID, &p.Address, &p.Amount, &p.Key, &p.TxID, &p.Status); err != nil {
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
