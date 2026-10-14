package pool

import (
	"encoding/hex"
	"fmt"
	"math"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/jQrgen/nordic-crypto/pool/internal/account"
	"github.com/jQrgen/nordic-crypto/pool/internal/nexa"
	"github.com/jQrgen/nordic-crypto/pool/internal/store"
	"github.com/jQrgen/nordic-crypto/pool/internal/stratum"
)

const (
	minerAddr = "nexa:nq2qqqgzqvzq2ps8pqys5zcvp58q7yq3zgfsalz92rn6"
	feeAddr   = "nexa:qqqqzqsrqszsvpcgpy9qkrqdpc83qygjzv5cxgkyhm"
	vectorHC  = "0a4ac49b2d02e3c8d12c7093255ba7c49624f9c374d9f1c2f8e37c58705e74b0"
	vectorHex = "10000000000000001182dc5800000000"
)

func TestShareMatchesVectorAndSubmitsBlock(t *testing.T) {
	node := &fakeNode{
		cand: nexa.Candidate{ID: 7, HeaderCommitment: vectorHC, NBits: "207fffff"},
		info: nexa.MiningInfo{Blocks: 100, Difficulty: 1, NetworkHashrate: 1e12},
	}
	svc := newTestService(t, node)
	if err := svc.Poll(); err != nil {
		t.Fatal(err)
	}
	job, ok := svc.CurrentJob()
	if !ok {
		t.Fatal("no job")
	}
	nonce, _ := hex.DecodeString(vectorHex)
	verdict := svc.Submit(stratum.Share{
		Address: minerAddr, Worker: "rig1", JobID: job.ID, Nonce: nonce, DifficultyMicros: 1, NTime: job.Time,
	})
	if !verdict.Accept {
		t.Fatalf("rejected: %+v", verdict)
	}
	if len(node.submits) != 1 || node.submits[0].id != 7 || node.submits[0].nonce != vectorHex {
		t.Fatalf("submit %#v", node.submits)
	}
	again := svc.Submit(stratum.Share{
		Address: minerAddr, JobID: job.ID, Nonce: nonce, DifficultyMicros: 1, NTime: job.Time,
	})
	if again.Code != 22 {
		t.Fatalf("duplicate code %d", again.Code)
	}
	low := svc.Submit(stratum.Share{
		Address: minerAddr, JobID: job.ID, Nonce: nonce, DifficultyMicros: nexa.Micros * 1000, NTime: job.Time,
	})
	if low.Code != 23 {
		t.Fatalf("low difficulty code %d", low.Code)
	}
	stale := svc.Submit(stratum.Share{Address: minerAddr, JobID: "missing", Nonce: nonce, DifficultyMicros: 1})
	if stale.Code != 21 {
		t.Fatalf("stale code %d", stale.Code)
	}
	blocks, err := svc.Blocks(10)
	if err != nil || len(blocks) != 1 || blocks[0].Hash != "aa" || blocks[0].Finder != minerAddr {
		t.Fatalf("%v %+v", err, blocks)
	}
}

func TestMatureSplitsFeeAndPayoutStopsAtWallet(t *testing.T) {
	node := &fakeNode{
		info:    nexa.MiningInfo{Difficulty: 0.000001, NetworkHashrate: 100},
		balance: 10_000,
		block:   nexa.Block{Hash: "aa", Height: 101, Confirmations: 5001, Reward: 10_000},
	}
	svc := newTestService(t, node)
	if _, err := svc.db.InsertBlock(store.Block{Height: 101, Hash: "aa", Finder: minerAddr, FoundAt: time.Now()}); err != nil {
		t.Fatal(err)
	}
	if err := svc.db.AddShare(store.Share{
		Address: minerAddr, Worker: "rig", JobID: "1", Nonce: "01", PowHash: "02",
		Work: 1_000_000, At: time.Now().Add(-time.Second),
	}); err != nil {
		t.Fatal(err)
	}
	if err := svc.MatureOnce(); err != nil {
		t.Fatal(err)
	}
	if err := svc.MatureOnce(); err != nil {
		t.Fatal(err)
	}
	view, err := svc.Lookup(minerAddr)
	if err != nil {
		t.Fatal(err)
	}
	fee, err := svc.Lookup(feeAddr)
	if err != nil {
		t.Fatal(err)
	}
	if view.Balance+fee.Balance != 10_000 || fee.Balance != 100 {
		t.Fatalf("miner %d fee %d", view.Balance, fee.Balance)
	}
	node.balance = view.Balance + fee.Balance
	svc.cfg.MinPayout = 50
	svc.cfg.TxReserve = 100
	first, err := svc.PayOnce()
	if err != nil {
		t.Fatal(err)
	}
	second, err := svc.PayOnce()
	if err != nil {
		t.Fatal(err)
	}
	if first.Sent != 1 || second.Sent != 0 {
		t.Fatalf("sent first %d second %d (wallet must keep the reserve)", first.Sent, second.Sent)
	}
	if len(node.sent) != 1 || node.sent[0].address != minerAddr {
		t.Fatalf("paid %#v", node.sent)
	}
	again, _ := svc.Lookup(minerAddr)
	if again.Balance != 0 || again.Paid != view.Balance {
		t.Fatalf("miner balance after pay %d paid %d", again.Balance, again.Paid)
	}
}

func TestSnapshotHidesLiveFiguresWhenNodeIsDown(t *testing.T) {
	node := &fakeNode{err: errDown}
	svc := newTestService(t, node)
	if err := svc.Poll(); err == nil {
		t.Fatal("expected node error")
	}
	stats, err := svc.Snapshot()
	if err != nil {
		t.Fatal(err)
	}
	if stats.NodeOnline || stats.PoolHashrate != nil || stats.Miners != nil || stats.NetworkHashrate != nil {
		t.Fatalf("live figures leaked: %+v", stats)
	}
	if stats.FeePercent != 1 || stats.MinPayout != "1000000.00" {
		t.Fatalf("config %+v", stats)
	}
}

func TestWindowWorkAndHashrate(t *testing.T) {
	got, err := WindowWork(2, 1.5)
	if err != nil || got != 3_000_000 {
		t.Fatalf("%d %v", got, err)
	}
	if _, err := WindowWork(2, 0); err == nil {
		t.Fatal("zero difficulty accepted")
	}
	huge, err := WindowWork(2, math.MaxFloat64)
	if err != nil || huge != math.MaxUint64 {
		t.Fatalf("overflow %d %v", huge, err)
	}
	rate := Hashrate(nexa.Micros, time.Second)
	if rate != 4294967296 {
		t.Fatalf("hashrate %v", rate)
	}
}

func TestCleanJobDropsThePreviousOne(t *testing.T) {
	node := &fakeNode{
		cand: nexa.Candidate{ID: 1, HeaderCommitment: vectorHC, NBits: "207fffff"},
		info: nexa.MiningInfo{Blocks: 10, Difficulty: 1},
	}
	svc := newTestService(t, node)
	if err := svc.Poll(); err != nil {
		t.Fatal(err)
	}
	first, ok := svc.CurrentJob()
	if !ok {
		t.Fatal("no job")
	}
	node.cand.ID = 2
	node.cand.HeaderCommitment = strings.Repeat("ab", 32)
	if err := svc.Poll(); err != nil {
		t.Fatal(err)
	}
	nonce, _ := hex.DecodeString(vectorHex)
	stale := svc.Submit(stratum.Share{Address: minerAddr, JobID: first.ID, Nonce: nonce, DifficultyMicros: 1})
	if stale.Code != 21 {
		t.Fatalf("clean notify left job %s open, code %d", first.ID, stale.Code)
	}
}

func TestMissingBlockIsRetried(t *testing.T) {
	node := &fakeNode{
		info:   nexa.MiningInfo{Difficulty: 0.000001},
		block:  nexa.Block{Hash: "aa", Height: 101, Confirmations: 5001, Reward: 10_000},
		misses: 1,
	}
	svc := newTestService(t, node)
	if _, err := svc.db.InsertBlock(store.Block{Height: 101, Hash: "aa", Finder: minerAddr, FoundAt: time.Now()}); err != nil {
		t.Fatal(err)
	}
	if err := svc.MatureOnce(); err != nil {
		t.Fatal(err)
	}
	blocks, err := svc.db.ImmatureBlocks()
	if err != nil || len(blocks) != 1 {
		t.Fatalf("missing getblock orphaned the block: %v %+v", err, blocks)
	}
	if err := svc.db.AddShare(store.Share{
		Address: minerAddr, Worker: "rig", JobID: "1", Nonce: "01", PowHash: "02",
		Work: 1_000_000, At: time.Now().Add(-time.Second),
	}); err != nil {
		t.Fatal(err)
	}
	if err := svc.MatureOnce(); err != nil {
		t.Fatal(err)
	}
	blocks, err = svc.db.ImmatureBlocks()
	if err != nil || len(blocks) != 0 {
		t.Fatalf("retry did not mature: %v %+v", err, blocks)
	}
}

func TestMaturityWaitsUntilWalletCanSpend(t *testing.T) {
	node := &fakeNode{
		info:  nexa.MiningInfo{Difficulty: 0.000001},
		block: nexa.Block{Hash: "aa", Height: 101, Confirmations: 5000, Reward: 10_000},
	}
	svc := newTestService(t, node)
	if _, err := svc.db.InsertBlock(store.Block{Height: 101, Hash: "aa", Finder: minerAddr, FoundAt: time.Now()}); err != nil {
		t.Fatal(err)
	}
	if err := svc.db.AddShare(store.Share{
		Address: minerAddr, Worker: "rig", JobID: "1", Nonce: "01", PowHash: "02",
		Work: 1_000_000, At: time.Now().Add(-time.Second),
	}); err != nil {
		t.Fatal(err)
	}
	if err := svc.MatureOnce(); err != nil {
		t.Fatal(err)
	}
	if blocks, err := svc.db.ImmatureBlocks(); err != nil || len(blocks) != 1 {
		t.Fatalf("5000 confirmations matured early: %v %+v", err, blocks)
	}
	node.block.Confirmations = 5001
	if err := svc.MatureOnce(); err != nil {
		t.Fatal(err)
	}
	if blocks, err := svc.db.ImmatureBlocks(); err != nil || len(blocks) != 0 {
		t.Fatalf("5001 did not mature: %v %+v", err, blocks)
	}
}

func TestTailstormFollowsTheCandidateNotTheClock(t *testing.T) {
	parent := strings.Repeat("11", 32)
	// 2030-01-01, years after the old wall-clock constant. A zero parent
	// still publishes the pre-fork job.
	node := &fakeNode{
		cand: nexa.Candidate{ID: 1, HeaderCommitment: vectorHC, NBits: "207fffff", PrevHash: strings.Repeat("0", 64)},
		info: nexa.MiningInfo{Blocks: 10, Difficulty: 1},
	}
	svc := newTestService(t, node)
	svc.now = func() time.Time { return time.Unix(1893456000, 0).UTC() }
	if err := svc.Poll(); err != nil {
		t.Fatal(err)
	}
	before, ok := svc.CurrentJob()
	if !ok || before.PrevHash != "" {
		t.Fatalf("zero parent was treated as tailstorm: %+v", before)
	}
	pre := stratum.NotifyParams(before)
	if len(pre) != 5 {
		t.Fatalf("pre-fork notify %#v", pre)
	}
	nonce, _ := hex.DecodeString(vectorHex)
	if v := svc.Submit(stratum.Share{
		Address: minerAddr, JobID: before.ID, Nonce: nonce, DifficultyMicros: 1, NTime: before.Time,
	}); !v.Accept {
		t.Fatalf("pre-fork vector rejected: %+v", v)
	}

	node.cand.ID = 2
	node.cand.PrevHash = parent
	if err := svc.Poll(); err != nil {
		t.Fatal(err)
	}
	after, ok := svc.CurrentJob()
	if !ok || after.PrevHash != parent {
		t.Fatalf("real parent was ignored: %+v", after)
	}
	post := stratum.NotifyParams(after)
	if len(post) != 6 || post[5] != parent {
		t.Fatalf("post-fork notify %#v", post)
	}
	parentBytes, _ := hex.DecodeString(parent)
	hc, _ := hex.DecodeString(vectorHC)
	bound, err := nexa.PowHash(hc, nonce, parentBytes)
	if err != nil {
		t.Fatal(err)
	}
	classic := "00000042cbc240375242e14641488a0e2dca7b54458a2cea23dc1d2c178bb188"
	if hex.EncodeToString(bound) == classic {
		t.Fatal("tailstorm mix did not change the digest")
	}
	if v := svc.Submit(stratum.Share{
		Address: minerAddr, JobID: after.ID, Nonce: nonce, DifficultyMicros: nexa.Micros, NTime: after.Time,
	}); v.Accept {
		t.Fatal("post-fork accepted the pre-fork vector at difficulty 1")
	}

	// An operator can force the pre-fork hash even when the node sends a parent.
	svc.cfg.Tailstorm = "off"
	node.cand.ID = 3
	if err := svc.Poll(); err != nil {
		t.Fatal(err)
	}
	forced, ok := svc.CurrentJob()
	if !ok || forced.PrevHash != "" || len(stratum.NotifyParams(forced)) != 5 {
		t.Fatalf("off override still mixed the parent: %+v", forced)
	}

	// Forcing it on rejects a zero parent instead of hashing the old way.
	svc.cfg.Tailstorm = "on"
	node.cand.ID = 4
	node.cand.PrevHash = strings.Repeat("0", 64)
	if err := svc.Poll(); err == nil {
		t.Fatal("forced tailstorm published a zero parent")
	}

	// A configured activation time is compared with the node's median
	// time, not the wall clock. The candidate already carries a parent.
	svc.cfg.Tailstorm = "auto"
	svc.cfg.TailstormAt = 4_102_488_000
	node.mtp = 4_102_488_000 - 1
	node.cand.ID = 5
	node.cand.PrevHash = parent
	if err := svc.Poll(); err != nil {
		t.Fatal(err)
	}
	early, ok := svc.CurrentJob()
	if !ok || early.PrevHash != "" {
		t.Fatalf("median time before the override still switched: %+v", early)
	}
	node.mtp = 4_102_488_000
	node.cand.ID = 6
	if err := svc.Poll(); err != nil {
		t.Fatal(err)
	}
	late, ok := svc.CurrentJob()
	if !ok || late.PrevHash != parent {
		t.Fatalf("median time at the override did not switch: %+v", late)
	}
}

func TestSubmitRejectsMismatchedNTime(t *testing.T) {
	node := &fakeNode{
		cand: nexa.Candidate{ID: 7, HeaderCommitment: vectorHC, NBits: "207fffff"},
		info: nexa.MiningInfo{Blocks: 100, Difficulty: 1},
	}
	svc := newTestService(t, node)
	if err := svc.Poll(); err != nil {
		t.Fatal(err)
	}
	job, ok := svc.CurrentJob()
	if !ok {
		t.Fatal("no job")
	}
	nonce, _ := hex.DecodeString(vectorHex)
	bad := svc.Submit(stratum.Share{
		Address: minerAddr, JobID: job.ID, Nonce: nonce, DifficultyMicros: 1, NTime: job.Time + 1,
	})
	if bad.Accept || bad.Message != "bad time" {
		t.Fatalf("wrong ntime accepted: %+v", bad)
	}
	if len(node.submits) != 0 {
		t.Fatal("wrong ntime was submitted to the node")
	}
	okShare := svc.Submit(stratum.Share{
		Address: minerAddr, JobID: job.ID, Nonce: nonce, DifficultyMicros: 1, NTime: job.Time,
	})
	if !okShare.Accept {
		t.Fatalf("matching ntime rejected: %+v", okShare)
	}
}

func TestSharePruneRunsWhileBlockIsImmature(t *testing.T) {
	node := &fakeNode{
		info:  nexa.MiningInfo{Difficulty: 1000},
		block: nexa.Block{Hash: "aa", Height: 101, Confirmations: 10, Reward: 10_000},
	}
	svc := newTestService(t, node)
	found := time.Unix(1_700_000_000, 0).UTC()
	if _, err := svc.db.InsertBlock(store.Block{Height: 101, Hash: "aa", Finder: minerAddr, FoundAt: found}); err != nil {
		t.Fatal(err)
	}
	old := found.Add(-20 * 24 * time.Hour)
	if err := svc.db.AddShare(store.Share{
		Address: minerAddr, Worker: "rig", JobID: "old", Nonce: "01", PowHash: "02",
		Work: 1000, At: old,
	}); err != nil {
		t.Fatal(err)
	}
	if err := svc.db.AddShare(store.Share{
		Address: minerAddr, Worker: "rig", JobID: "new", Nonce: "03", PowHash: "04",
		Work: 1000, At: found.Add(-time.Minute),
	}); err != nil {
		t.Fatal(err)
	}
	if err := svc.MatureOnce(); err != nil {
		t.Fatal(err)
	}
	blocks, err := svc.db.ImmatureBlocks()
	if err != nil || len(blocks) != 1 {
		t.Fatalf("immature block was closed: %v %+v", err, blocks)
	}
	kept, err := svc.db.WorkSince(found.Add(-21 * 24 * time.Hour))
	if err != nil {
		t.Fatal(err)
	}
	var work uint64
	for _, m := range kept {
		work += m.Work
	}
	if work != 1000 {
		t.Fatalf("old share survived an immature block, work %d", work)
	}
}

func TestReconcileWhenWalletIsOverTheCap(t *testing.T) {
	node := &fakeNode{balance: 50_000}
	svc := newTestService(t, node)
	svc.cfg.HotWalletMax = 10_000
	svc.cfg.MinPayout = 100
	if _, err := svc.db.InsertBlock(store.Block{Height: 5, Hash: "bb", Finder: minerAddr}); err != nil {
		t.Fatal(err)
	}
	blocks, err := svc.db.ImmatureBlocks()
	if err != nil || len(blocks) != 1 {
		t.Fatal(err)
	}
	if err := svc.db.MatureBlock(blocks[0].ID, 5_000, []account.Credit{{Address: minerAddr, Amount: 5_000, Kind: "miner"}}); err != nil {
		t.Fatal(err)
	}
	id, err := svc.db.Reserve(minerAddr, 5_000, "nexapool:held", account.Signed{TxID: "tx-held", TxIdem: "idem-held", Raw: "raw-held", Inputs: []string{"out-held"}})
	if err != nil {
		t.Fatal(err)
	}
	node.live = map[string]nexa.TxView{
		"idem-held": {Payment: nexa.Payment{TxID: "tx-held", TxIdem: "idem-held", Confirmations: 1}, InWallet: true},
	}
	result, err := svc.PayOnce()
	if err == nil || !strings.Contains(err.Error(), "hot wallet") {
		t.Fatalf("cap error: %v", err)
	}
	if result.Sent != 1 || len(node.sent) != 0 {
		t.Fatalf("over-cap pass sent a new payment: result %+v wallet %#v", result, node.sent)
	}
	p, err := svc.db.Payout(id)
	if err != nil || p.Status != "sent" || p.TxID != "tx-held" {
		t.Fatalf("in-flight row was not reconciled: %+v %v", p, err)
	}
}

func TestMaturityAndCoinbaseAreRequired(t *testing.T) {
	node := &fakeNode{}
	db, err := store.Open(filepath.Join(t.TempDir(), "pool.sqlite"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { db.Close() })
	base := Config{
		FeePercent: 1, FeeAddress: feeAddr, CoinbaseAddress: feeAddr,
		MinPayout: 1, Maturity: 5000, HotWalletMax: 1,
	}
	if _, err := New(base, db, node, nil); err == nil {
		t.Fatal("maturity 5000 was accepted")
	}
	base.Maturity = 5001
	base.CoinbaseAddress = ""
	if _, err := New(base, db, node, nil); err == nil {
		t.Fatal("empty coinbase address was accepted")
	}
}

func TestOfflineNodeDoesNotOrphan(t *testing.T) {
	node := &fakeNode{err: errDown}
	svc := newTestService(t, node)
	if _, err := svc.db.InsertBlock(store.Block{Height: 5, Hash: "bb", Finder: minerAddr}); err != nil {
		t.Fatal(err)
	}
	if err := svc.MatureOnce(); err == nil {
		t.Fatal("maturity should stop when difficulty is unavailable")
	}
	blocks, err := svc.db.ImmatureBlocks()
	if err != nil || len(blocks) != 1 || blocks[0].Status != "immature" {
		t.Fatalf("%v %+v", err, blocks)
	}
}

func newTestService(t *testing.T, node *fakeNode) *Service {
	t.Helper()
	db, err := store.Open(filepath.Join(t.TempDir(), "pool.sqlite"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { db.Close() })
	svc, err := New(Config{
		FeePercent: 1, FeeAddress: feeAddr, CoinbaseAddress: feeAddr, MinPayout: 100_000_000,
		Maturity: 5001, PPLNSBlocks: 2, HashrateWindow: time.Minute,
		PayoutEvery: time.Hour, TxReserve: 100, PayoutConfs: 1,
		HotWalletMax: 1_000_000_000_000,
	}, db, node, nil)
	if err != nil {
		t.Fatal(err)
	}
	// Pin the notify timestamp. Tailstorm follows the candidate, not this clock.
	svc.now = func() time.Time { return time.Unix(1_700_000_000, 0).UTC() }
	return svc
}

type submitted struct {
	id    int64
	nonce string
}

type sent struct {
	address string
	amount  int64
	comment string
}

type fakeNode struct {
	cand    nexa.Candidate
	info    nexa.MiningInfo
	block   nexa.Block
	balance int64
	mtp     int64
	err     error
	misses  int
	submits []submitted
	sent    []sent
	next    int
	pending map[string]pendingTx
	live    map[string]nexa.TxView
}

type pendingTx struct {
	signed  nexa.SignedTx
	address string
	amount  int64
}

var errDown = errString("connection refused")

type errString string

func (e errString) Error() string { return string(e) }

func (f *fakeNode) GetMiningCandidate(string) (nexa.Candidate, error) {
	if f.err != nil {
		return nexa.Candidate{}, f.err
	}
	return f.cand, nil
}
func (f *fakeNode) SubmitSolution(id int64, nonce string) (int64, string, error) {
	f.submits = append(f.submits, submitted{id, nonce})
	return 101, "aa", nil
}
func (f *fakeNode) GetMiningInfo() (nexa.MiningInfo, error) {
	if f.err != nil && f.info.Difficulty == 0 {
		return nexa.MiningInfo{}, f.err
	}
	return f.info, nil
}
func (f *fakeNode) GetBlock(hash string) (nexa.Block, error) {
	if f.misses > 0 {
		f.misses--
		return nexa.Block{}, errString("Block not found on disk")
	}
	if f.block.Hash == hash {
		return f.block, nil
	}
	return nexa.Block{}, errString("Block not found")
}
func (f *fakeNode) CreatePayout(address string, sats int64, _ []string) (nexa.SignedTx, error) {
	if sats <= 0 {
		return nexa.SignedTx{}, errString("empty payout")
	}
	f.next++
	signed := nexa.SignedTx{
		TxID:   fmt.Sprintf("tx-%d", f.next),
		TxIdem: fmt.Sprintf("idem-%d", f.next),
		Raw:    fmt.Sprintf("raw-%d", f.next),
		Inputs: []string{fmt.Sprintf("out-%d", f.next)},
	}
	if f.pending == nil {
		f.pending = map[string]pendingTx{}
	}
	f.pending[signed.Raw] = pendingTx{signed: signed, address: address, amount: sats}
	return signed, nil
}
func (f *fakeNode) SendRaw(raw string) error {
	p, ok := f.pending[raw]
	if !ok {
		return errString("unknown raw transaction")
	}
	if p.amount > f.balance {
		return errString("insufficient funds")
	}
	f.balance -= p.amount
	if f.live == nil {
		f.live = map[string]nexa.TxView{}
	}
	f.live[p.signed.TxIdem] = nexa.TxView{
		Payment:  nexa.Payment{TxID: p.signed.TxID, TxIdem: p.signed.TxIdem, Confirmations: 1},
		InWallet: true,
	}
	f.sent = append(f.sent, sent{p.address, p.amount, p.signed.TxID})
	return nil
}
func (f *fakeNode) LookupTx(txidem string) (nexa.TxView, error) {
	if view, ok := f.live[txidem]; ok {
		return view, nil
	}
	return nexa.TxView{}, nil
}
func (f *fakeNode) LockOutpoints([]string, bool) error { return nil }
func (f *fakeNode) WalletBalance() (int64, error)      { return f.balance, nil }
func (f *fakeNode) Unlock(string, int) error           { return nil }
func (f *fakeNode) Lock(string) error                  { return nil }
func (f *fakeNode) MedianTime() (int64, error) {
	if f.err != nil && f.mtp == 0 {
		return 0, f.err
	}
	return f.mtp, nil
}
