package pool

import (
	"encoding/hex"
	"math"
	"path/filepath"
	"strings"
	"testing"
	"time"

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
		Address: minerAddr, Worker: "rig1", JobID: job.ID, Nonce: nonce, DifficultyMicros: 1,
	})
	if !verdict.Accept {
		t.Fatalf("rejected: %+v", verdict)
	}
	if len(node.submits) != 1 || node.submits[0].id != 7 || node.submits[0].nonce != vectorHex {
		t.Fatalf("submit %#v", node.submits)
	}
	again := svc.Submit(stratum.Share{
		Address: minerAddr, JobID: job.ID, Nonce: nonce, DifficultyMicros: 1,
	})
	if again.Code != 22 {
		t.Fatalf("duplicate code %d", again.Code)
	}
	low := svc.Submit(stratum.Share{
		Address: minerAddr, JobID: job.ID, Nonce: nonce, DifficultyMicros: nexa.Micros * 1000,
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

func TestNotifySwitchesAtTailstormActivation(t *testing.T) {
	parent := strings.Repeat("11", 32)
	node := &fakeNode{
		cand: nexa.Candidate{ID: 1, HeaderCommitment: vectorHC, NBits: "207fffff", PrevHash: parent},
		info: nexa.MiningInfo{Blocks: 10, Difficulty: 1},
	}
	svc := newTestService(t, node)
	svc.now = func() time.Time { return time.Unix(nexa.TailstormActivation-1, 0).UTC() }
	if err := svc.Poll(); err != nil {
		t.Fatal(err)
	}
	before, ok := svc.CurrentJob()
	if !ok || before.PrevHash != "" || int64(before.Time) != nexa.TailstormActivation-1 {
		t.Fatalf("pre-fork job %+v", before)
	}
	pre := stratum.NotifyParams(before)
	if len(pre) != 5 {
		t.Fatalf("pre-fork notify %#v", pre)
	}
	nonce, _ := hex.DecodeString(vectorHex)
	if v := svc.Submit(stratum.Share{Address: minerAddr, JobID: before.ID, Nonce: nonce, DifficultyMicros: 1}); !v.Accept {
		t.Fatalf("pre-fork vector rejected: %+v", v)
	}

	svc.now = func() time.Time { return time.Unix(nexa.TailstormActivation, 0).UTC() }
	node.cand.ID = 2
	if err := svc.Poll(); err != nil {
		t.Fatal(err)
	}
	after, ok := svc.CurrentJob()
	if !ok || after.PrevHash != parent {
		t.Fatalf("post-fork job %+v", after)
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
	// Difficulty 1 is far above this vector. A share hashed the old way
	// fails. A share hashed with the parent is a different digest and is
	// not the pre-fork proof the miner would have sent.
	if v := svc.Submit(stratum.Share{
		Address: minerAddr, JobID: after.ID, Nonce: nonce, DifficultyMicros: nexa.Micros,
	}); v.Accept {
		t.Fatal("post-fork accepted the pre-fork vector at difficulty 1")
	}
	// One second before activation the parent must stay off the wire even
	// when the candidate already carries one. That case is `before` above.
	node.cand.ID = 3
	node.cand.PrevHash = strings.Repeat("0", 64)
	if err := svc.Poll(); err == nil {
		t.Fatal("post-fork zero parent was published")
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
		FeePercent: 1, FeeAddress: feeAddr, MinPayout: 100_000_000,
		Maturity: 5001, PPLNSBlocks: 2, HashrateWindow: time.Minute,
		PayoutEvery: time.Hour, TxReserve: 100, PayoutConfs: 1,
		HotWalletMax: 1_000_000_000_000,
	}, db, node, nil)
	if err != nil {
		t.Fatal(err)
	}
	// Pin the clock before Hard Fork 2 so share vectors stay pre-Tailstorm.
	// The activation tests set their own clock.
	svc.now = func() time.Time { return time.Unix(nexa.TailstormActivation-86400, 0).UTC() }
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
	err     error
	misses  int
	submits []submitted
	sent    []sent
	notes   map[string]string
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
func (f *fakeNode) SendToAddress(address string, sats int64, comment string) (nexa.Payment, error) {
	if sats > f.balance {
		return nexa.Payment{}, errString("insufficient funds")
	}
	f.balance -= sats
	if f.notes == nil {
		f.notes = map[string]string{}
	}
	txid := "tx-" + comment
	f.notes[comment] = txid
	f.sent = append(f.sent, sent{address, sats, comment})
	return nexa.Payment{TxID: txid, Confirmations: 1}, nil
}
func (f *fakeNode) WalletBalance() (int64, error) { return f.balance, nil }
func (f *fakeNode) LookupPayment(comment, id string) (nexa.Payment, bool, error) {
	if id != "" {
		for c, tx := range f.notes {
			if tx == id || c == id {
				return nexa.Payment{TxID: tx, Confirmations: 1}, true, nil
			}
		}
	}
	tx, ok := f.notes[comment]
	if !ok {
		return nexa.Payment{}, false, nil
	}
	return nexa.Payment{TxID: tx, Confirmations: 1}, true, nil
}
func (f *fakeNode) Unlock(string, int) error { return nil }
func (f *fakeNode) Lock(string) error        { return nil }
