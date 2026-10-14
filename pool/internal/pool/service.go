// Package pool ties the node, the ledger and the stratum server together.
package pool

import (
	"encoding/hex"
	"errors"
	"fmt"
	"log"
	"math"
	"math/big"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/jQrgen/nordic-crypto/pool/internal/account"
	"github.com/jQrgen/nordic-crypto/pool/internal/nexa"
	"github.com/jQrgen/nordic-crypto/pool/internal/store"
	"github.com/jQrgen/nordic-crypto/pool/internal/stratum"
)

// ErrBadAddress is returned when a lookup is not a Nexa address.
var ErrBadAddress = errors.New("pool: invalid address")

// Config is the accounting and publishing configuration.
type Config struct {
	FeePercent      int
	FeeAddress      string
	CoinbaseAddress string
	MinPayout       int64
	Maturity        int64
	PPLNSBlocks     float64
	HashrateWindow  time.Duration
	PayoutEvery     time.Duration
	TxReserve       int64
	PublicStratum   string
	PayoutConfs     int64
	HotWalletMax    int64
	// Tailstorm is auto, on, or off. auto follows the mining candidate.
	Tailstorm string
	// TailstormAt, when set, is a unix time compared with the node's
	// median time past. It is not compared with the wall clock.
	TailstormAt int64
	// ReleaseNoneMinAge is how old a reservation must be before
	// release -confirm none is accepted. Zero becomes 24 hours.
	ReleaseNoneMinAge time.Duration
	// ReleaseConflictDepth is how many confirmations a competing
	// spend needs before the coins can be paid again. Zero becomes 10.
	// A value below account.MinConflictDepth is rejected.
	ReleaseConflictDepth int64
}

// Chain is the nexad surface the pool uses.
type Chain interface {
	GetMiningCandidate(address string) (nexa.Candidate, error)
	SubmitSolution(id int64, nonceHex string) (int64, string, error)
	GetMiningInfo() (nexa.MiningInfo, error)
	GetBlock(hash string) (nexa.Block, error)
	CreatePayout(address string, sats int64, avoid []string) (nexa.SignedTx, error)
	SendRaw(raw string) error
	LookupTx(txidem string) (nexa.TxView, error)
	// LockOutpoints calls lockunspent. unlock false locks.
	LockOutpoints(outpoints []string, unlock bool) error
	WalletBalance() (int64, error)
	Unlock(passphrase string, timeout int) error
	Lock(passphrase string) error
	MedianTime() (int64, error)
}

// Service is the pool.
type Service struct {
	cfg     Config
	db      *store.Store
	node    Chain
	log     *log.Logger
	pass    string
	stratum *stratum.Server
	now     func() time.Time

	mu      sync.Mutex
	jobs    map[string]*memJob
	order   []string
	next    uint64
	hasTip  bool
	tipID   int64
	tipHash string
	info    nexa.MiningInfo
	online  bool
}

type memJob struct {
	wire        stratum.Job
	commitment  []byte
	prev        []byte
	network     *big.Int
	candidateID int64
}

// New checks the fee address and the payout settings.
func New(cfg Config, db *store.Store, node Chain, logger *log.Logger) (*Service, error) {
	if logger == nil {
		logger = log.Default()
	}
	if cfg.FeePercent < 1 || cfg.FeePercent > 100 {
		return nil, fmt.Errorf("pool: fee percent %d", cfg.FeePercent)
	}
	if !nexa.ValidAddress(cfg.FeeAddress) {
		return nil, fmt.Errorf("pool: fee address is empty or invalid")
	}
	cfg.FeeAddress = strings.ToLower(cfg.FeeAddress)
	if cfg.CoinbaseAddress == "" || !nexa.ValidAddress(cfg.CoinbaseAddress) {
		return nil, fmt.Errorf("pool: coinbase address is empty or invalid")
	}
	cfg.CoinbaseAddress = strings.ToLower(cfg.CoinbaseAddress)
	mode, err := tailstormMode(cfg.Tailstorm)
	if err != nil {
		return nil, err
	}
	cfg.Tailstorm = mode
	if cfg.MinPayout <= 0 {
		return nil, fmt.Errorf("pool: minimum payout")
	}
	if cfg.Maturity == 0 {
		cfg.Maturity = 5001
	}
	if cfg.Maturity < 5001 {
		return nil, fmt.Errorf("pool: maturity %d is below 5001", cfg.Maturity)
	}
	if cfg.PayoutConfs <= 0 {
		cfg.PayoutConfs = 1
	}
	if cfg.ReleaseNoneMinAge <= 0 {
		cfg.ReleaseNoneMinAge = 24 * time.Hour
	}
	if cfg.ReleaseConflictDepth <= 0 {
		cfg.ReleaseConflictDepth = 10
	}
	if cfg.ReleaseConflictDepth < account.MinConflictDepth {
		return nil, fmt.Errorf("pool: release conflict depth %d is below %d", cfg.ReleaseConflictDepth, account.MinConflictDepth)
	}
	if cfg.PPLNSBlocks <= 0 {
		cfg.PPLNSBlocks = 2
	}
	if cfg.HashrateWindow <= 0 {
		cfg.HashrateWindow = 15 * time.Minute
	}
	if cfg.TxReserve < 0 {
		return nil, fmt.Errorf("pool: negative fee reserve")
	}
	if cfg.PublicStratum == "" {
		cfg.PublicStratum = "stratum+tcp://pool.nordiccrypto.no:3333"
	}
	return &Service{
		cfg: cfg, db: db, node: node, log: logger,
		jobs: map[string]*memJob{},
	}, nil
}

// SetPassphrase sets the wallet passphrase. It is never written to the log.
func (s *Service) SetPassphrase(p string) { s.pass = strings.TrimSpace(p) }

// Attach sends new work to miners.
func (s *Service) Attach(server *stratum.Server) { s.stratum = server }

// Authorize accepts a Nexa address. The password is ignored on purpose:
// the address is the account.
func (s *Service) Authorize(address, worker string) error {
	address = strings.ToLower(strings.TrimSpace(address))
	if !nexa.ValidAddress(address) {
		return ErrBadAddress
	}
	if len(worker) > 64 || strings.ContainsAny(worker, " \t\r\n") {
		return errors.New("pool: bad worker name")
	}
	return nil
}

// Poll fetches a mining candidate and, when it changed, notifies miners.
func (s *Service) Poll() error {
	cand, err := s.node.GetMiningCandidate(s.cfg.CoinbaseAddress)
	if err != nil {
		s.mark(false, nexa.MiningInfo{})
		return err
	}
	info, err := s.node.GetMiningInfo()
	if err != nil {
		s.mark(false, nexa.MiningInfo{})
		return err
	}
	s.mu.Lock()
	s.info = info
	s.online = true
	same := s.hasTip && s.tipID == cand.ID && s.tipHash == cand.HeaderCommitment
	s.mu.Unlock()
	if same {
		return nil
	}
	return s.publish(cand, info)
}

func (s *Service) mark(online bool, info nexa.MiningInfo) {
	s.mu.Lock()
	s.online = online
	s.info = info
	s.mu.Unlock()
}

func (s *Service) clock() time.Time {
	if s.now != nil {
		return s.now()
	}
	return time.Now()
}

func (s *Service) publish(cand nexa.Candidate, info nexa.MiningInfo) error {
	commitment, err := nexa.DecodeHex(cand.HeaderCommitment)
	if err != nil || len(commitment) != 32 {
		return fmt.Errorf("pool: bad header commitment")
	}
	target, err := compactTarget(cand.NBits)
	if err != nil {
		return err
	}
	now := s.clock().Unix()
	active, err := s.tailstormActive(cand)
	if err != nil {
		return err
	}
	var prev []byte
	prevHex := ""
	if active {
		prev, err = nexa.DecodeHex(cand.PrevHash)
		if err != nil || len(prev) != 32 || allZero(prev) {
			return fmt.Errorf("pool: tailstorm candidate is missing previousBlockHash")
		}
		prevHex = hex.EncodeToString(prev)
	}
	s.mu.Lock()
	s.next++
	id := strconv.FormatUint(s.next, 16)
	job := &memJob{
		commitment:  commitment,
		prev:        prev,
		network:     target,
		candidateID: cand.ID,
		wire: stratum.Job{
			ID: id, Commitment: hex.EncodeToString(commitment), NBits: strings.ToLower(cand.NBits),
			PrevHash: prevHex, Time: uint64(now),
			Height: info.Blocks + 1, CandidateID: cand.ID, Clean: true,
		},
	}
	// A clean notify invalidates every previous job id. Echelon says the
	// miner must forget them, and the pool must reject them.
	if job.wire.Clean {
		s.jobs = map[string]*memJob{id: job}
		s.order = []string{id}
	} else {
		s.jobs[id] = job
		s.order = append(s.order, id)
		if len(s.order) > 32 {
			delete(s.jobs, s.order[0])
			s.order = s.order[1:]
		}
	}
	s.hasTip = true
	s.tipID = cand.ID
	s.tipHash = cand.HeaderCommitment
	wire := job.wire
	s.mu.Unlock()
	if s.stratum != nil {
		s.stratum.SetJob(wire)
	}
	return nil
}

func tailstormMode(v string) (string, error) {
	switch strings.ToLower(strings.TrimSpace(v)) {
	case "", "auto":
		return "auto", nil
	case "on", "true", "yes":
		return "on", nil
	case "off", "false", "no":
		return "off", nil
	default:
		return "", fmt.Errorf("pool: tailstorm mode %q", v)
	}
}

// tailstormActive follows the mining candidate unless the operator pinned
// a mode or a median-time override. There is no wall-clock switch.
func (s *Service) tailstormActive(cand nexa.Candidate) (bool, error) {
	switch s.cfg.Tailstorm {
	case "on":
		return true, nil
	case "off":
		return false, nil
	default:
		if s.cfg.TailstormAt > 0 {
			mtp, err := s.node.MedianTime()
			if err != nil {
				return false, err
			}
			return mtp >= s.cfg.TailstormAt, nil
		}
		return nexa.TailstormParent(cand.PrevHash), nil
	}
}

func allZero(b []byte) bool {
	for _, c := range b {
		if c != 0 {
			return false
		}
	}
	return true
}

// CurrentJob is the work miners were last given.
func (s *Service) CurrentJob() (stratum.Job, bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if len(s.order) == 0 {
		return stratum.Job{}, false
	}
	return s.jobs[s.order[len(s.order)-1]].wire, true
}

// Submit checks a share, stores it, and submits a block when the share
// meets the network target.
func (s *Service) Submit(sh stratum.Share) stratum.Verdict {
	sh.Address = strings.ToLower(sh.Address)
	s.mu.Lock()
	job := s.jobs[sh.JobID]
	s.mu.Unlock()
	if job == nil {
		return stratum.Verdict{Code: 21, Message: "Stale share"}
	}
	if sh.NTime != job.wire.Time {
		_ = s.db.AddReject(sh.Address, time.Now())
		return stratum.Verdict{Code: 20, Message: "bad time"}
	}
	var parent []byte
	if len(job.prev) == 32 && !allZero(job.prev) {
		parent = job.prev
	}
	pow, err := nexa.PowHash(job.commitment, sh.Nonce, parent)
	if err != nil {
		_ = s.db.AddReject(sh.Address, time.Now())
		return stratum.Verdict{Code: 20, Message: "Invalid proof of work"}
	}
	digest := nexa.HashInt(pow)
	if !nexa.Meets(digest, nexa.ShareTarget(sh.DifficultyMicros)) {
		_ = s.db.AddReject(sh.Address, time.Now())
		return stratum.Verdict{Code: 23, Message: "Low difficulty"}
	}
	err = s.db.AddShare(store.Share{
		Address: sh.Address, Worker: sh.Worker, JobID: sh.JobID,
		Nonce: hex.EncodeToString(sh.Nonce), PowHash: hex.EncodeToString(pow),
		Work: sh.DifficultyMicros,
	})
	if errors.Is(err, store.ErrDuplicate) {
		return stratum.Verdict{Code: 22, Message: "Duplicate share"}
	}
	if err != nil {
		s.log.Printf("share store: %v", err)
		return stratum.Verdict{Code: 20, Message: "Unavailable"}
	}
	if nexa.Meets(digest, job.network) {
		s.submitBlock(job, sh)
	}
	return stratum.Verdict{Accept: true}
}

func (s *Service) submitBlock(job *memJob, sh stratum.Share) {
	height, hash, err := s.node.SubmitSolution(job.candidateID, hex.EncodeToString(sh.Nonce))
	if err != nil {
		s.log.Printf("block submit rejected: %v", err)
		return
	}
	if hash == "" {
		s.log.Printf("block submit returned no hash")
		return
	}
	if _, err := s.db.InsertBlock(store.Block{Height: height, Hash: hash, Finder: sh.Address}); err != nil {
		s.log.Printf("record block %s: %v", hash, err)
		return
	}
	s.log.Printf("block submitted height %d hash %s finder %s", height, hash, sh.Address)
}

// MatureOnce credits blocks that have reached coinbase maturity.
func (s *Service) MatureOnce() error {
	info, err := s.node.GetMiningInfo()
	if err != nil {
		return err
	}
	target, err := WindowWork(s.cfg.PPLNSBlocks, info.Difficulty)
	if err != nil {
		return err
	}
	blocks, err := s.db.ImmatureBlocks()
	if err != nil {
		return err
	}
	// hold keeps the id prune from deleting history an unfilled window
	// still needs. The time prune runs either way: one immature block
	// used to stop it for the whole maturity wait.
	hold := false
	var floor int64 = -1
	for _, b := range blocks {
		blk, err := s.node.GetBlock(b.Hash)
		if err != nil {
			// "Block not found on disk" is nexad's reply when the header is
			// known and the body is not. That is a retry, not an orphan.
			s.log.Printf("block %s not ready, will retry: %v", b.Hash, err)
			hold = true
			continue
		}
		if blk.Confirmations < 0 {
			if err := s.db.OrphanBlock(b.ID); err != nil {
				return err
			}
			s.log.Printf("block %s orphaned", b.Hash)
			continue
		}
		if err := s.db.SetConfirmations(b.ID, blk.Confirmations); err != nil {
			return err
		}
		shares, oldest, filled, err := s.db.ShareWindow(b.FoundAt, target)
		if err != nil {
			return err
		}
		if !filled {
			hold = true
		} else if oldest > 0 && (floor < 0 || oldest < floor) {
			floor = oldest
		}
		if blk.Confirmations < s.cfg.Maturity {
			continue
		}
		if blk.Reward <= 0 {
			s.log.Printf("block %s has no pool coinbase output yet", b.Hash)
			continue
		}
		credits, err := account.Split(blk.Reward, s.cfg.FeePercent, s.cfg.FeeAddress, account.Window(shares, target))
		if err != nil {
			return err
		}
		if err := s.db.MatureBlock(b.ID, blk.Reward, credits); err != nil {
			return err
		}
		s.log.Printf("block %d matured, reward %s", blk.Height, nexa.FormatNEX(blk.Reward))
	}
	keep := int64(0)
	if !hold && floor > 1 {
		if err := s.db.PruneSharesBefore(floor); err != nil {
			return err
		}
		keep = floor
	}
	if err := s.db.PruneSharesBeforeTime(s.clock().Add(-14*24*time.Hour), keep); err != nil {
		return err
	}
	return s.db.PruneRejectsBefore(s.clock().Add(-48 * time.Hour))
}

// PayOnce sends mature balances at or above the minimum. It will not reserve
// more than the wallet can spend, and it leaves TxReserve in the wallet for
// transaction fees.
func (s *Service) PayOnce() (account.Result, error) {
	unlock, err := s.db.LockPayouts()
	if err != nil {
		return account.Result{}, err
	}
	defer unlock()
	if s.cfg.HotWalletMax <= 0 {
		return account.Result{}, fmt.Errorf("pool: hot wallet cap is not set")
	}
	if err := s.node.Unlock(s.pass, 180); err != nil {
		return account.Result{}, err
	}
	defer s.node.Lock(s.pass)
	if err := s.LockReservedCoins(); err != nil {
		return account.Result{}, err
	}
	bal, err := s.node.WalletBalance()
	if err != nil {
		return account.Result{}, err
	}
	if bal > s.cfg.HotWalletMax {
		// Still match in-flight rows to the wallet. Do not start a new send.
		result, recErr := account.Reconcile(s.db, rpcWallet{s.node}, s.cfg.PayoutConfs, s.cfg.ReleaseConflictDepth)
		if recErr != nil {
			return result, recErr
		}
		return result, fmt.Errorf("pool: wallet balance %s is above the hot wallet cap %s", nexa.FormatNEX(bal), nexa.FormatNEX(s.cfg.HotWalletMax))
	}
	reserved, err := s.db.Reserved()
	if err != nil {
		return account.Result{}, err
	}
	var held int64
	for _, p := range reserved {
		held += p.Amount
	}
	left := bal - held - s.cfg.TxReserve
	if left < 0 {
		left = 0
	}
	return account.RunPayouts(&spendCap{Ledger: s.db, left: left}, rpcWallet{s.node}, s.cfg.MinPayout, s.cfg.PayoutConfs, s.cfg.ReleaseConflictDepth)
}

// LockReservedCoins locks every outpoint still reserved, in review, or
// sent. lockunspent does not survive a restart, so this runs at startup
// and at the start of each payout pass.
func (s *Service) LockReservedCoins() error {
	ops, err := s.db.ReservedOutpoints()
	if err != nil {
		return err
	}
	return s.node.LockOutpoints(ops, false)
}

// Reviews lists payouts held for an operator. The coins stay deducted
// until the row is completed or released.
func (s *Service) Reviews() ([]account.Payout, error) {
	all, err := s.db.Reserved()
	if err != nil {
		return nil, err
	}
	var out []account.Payout
	for _, p := range all {
		if p.Status == "review" {
			out = append(out, p)
		}
	}
	return out, nil
}

// ResolveReview completes or releases one reserved or review row.
// action is "complete" or "release". release -confirm names the stored
// txidem and is accepted only when a different txidem has spent an input
// with at least ReleaseConflictDepth confirmations. "none" is accepted
// only when the row was never signed and the reservation is at least
// ReleaseNoneMinAge old.
func (s *Service) ResolveReview(id int64, action, confirm string) error {
	if err := s.node.Unlock(s.pass, 60); err != nil {
		return err
	}
	defer s.node.Lock(s.pass)
	return account.ResolveReview(s.db, rpcWallet{s.node}, id, action, s.cfg.PayoutConfs, confirm, s.cfg.ReleaseNoneMinAge, s.cfg.ReleaseConflictDepth)
}

// WindowWork is the PPLNS window in difficulty micros: blocks times the
// network difficulty. A value that does not fit in a uint64 uses the maximum,
// which keeps every recorded share in the window.
func WindowWork(blocks, difficulty float64) (uint64, error) {
	if blocks <= 0 || difficulty <= 0 || math.IsNaN(difficulty) || math.IsInf(difficulty, 0) {
		return 0, fmt.Errorf("pool: network difficulty is not usable")
	}
	v := blocks * difficulty * float64(nexa.Micros)
	if v < 1 {
		return 1, nil
	}
	if v >= float64(math.MaxUint64) {
		return math.MaxUint64, nil
	}
	return uint64(v), nil
}

// Hashrate converts a sum of share difficulty micros over a window into
// hashes per second, on the same scale as getnetworkhashps.
func Hashrate(workMicros uint64, window time.Duration) float64 {
	if window <= 0 {
		return 0
	}
	hashes := float64(workMicros) * 4294967296 / float64(nexa.Micros)
	return hashes / window.Seconds()
}

func compactTarget(nbits string) (*big.Int, error) {
	nbits = strings.TrimPrefix(strings.TrimPrefix(strings.ToLower(strings.TrimSpace(nbits)), "0x"), "0x")
	if nbits == "" || len(nbits) > 8 {
		return nil, fmt.Errorf("pool: bad nbits")
	}
	v, err := strconv.ParseUint(nbits, 16, 32)
	if err != nil {
		return nil, err
	}
	target := nexa.CompactToTarget(uint32(v))
	if target == nil {
		return nil, fmt.Errorf("pool: bad nbits")
	}
	return target, nil
}

type rpcWallet struct{ n Chain }

func (w rpcWallet) Prepare(address string, sats int64, avoid []string) (account.Signed, error) {
	signed, err := w.n.CreatePayout(address, sats, avoid)
	if err != nil {
		return account.Signed{}, err
	}
	return account.Signed{TxID: signed.TxID, TxIdem: signed.TxIdem, Raw: signed.Raw, Inputs: append([]string(nil), signed.Inputs...)}, nil
}

func (w rpcWallet) Broadcast(raw string) error { return w.n.SendRaw(raw) }

func (w rpcWallet) LookupTx(txidem string) (account.TxState, error) {
	view, err := w.n.LookupTx(txidem)
	if err != nil {
		return account.TxState{}, err
	}
	return account.TxState{
		Payment:     account.Payment{TxID: view.TxID, TxIdem: view.TxIdem, Confirmations: view.Confirmations},
		InWallet:    view.InWallet,
		InMempool:   view.InMempool,
		OnChain:     view.OnChain,
		Conflict:    view.Conflict,
		SpendTxIdem: view.SpendTxIdem,
		SpendConfs:  view.SpendConfs,
	}, nil
}

func (w rpcWallet) Lock(outpoints []string) error {
	return w.n.LockOutpoints(outpoints, false)
}

func (w rpcWallet) Unlock(outpoints []string) error {
	return w.n.LockOutpoints(outpoints, true)
}

// spendCap hides balances the wallet cannot cover. Reserved and sent rows
// still go to the underlying ledger.
type spendCap struct {
	account.Ledger
	left int64
}

func (c *spendCap) Payable(min int64) ([]account.Balance, error) {
	all, err := c.Ledger.Payable(min)
	if err != nil {
		return nil, err
	}
	var out []account.Balance
	for _, b := range all {
		if b.Amount <= c.left {
			out = append(out, b)
			c.left -= b.Amount
		}
	}
	return out, nil
}
