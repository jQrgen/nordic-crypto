package pool

import (
	"encoding/hex"
	"math"
	"path/filepath"
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
		block:   nexa.Block{Hash: "aa", Height: 101, Confirmations: 5000, Reward: 10_000},
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
		Maturity: 5000, PPLNSBlocks: 2, HashrateWindow: time.Minute,
		PayoutEvery: time.Hour, TxReserve: 100,
	}, db, node, nil)
	if err != nil {
		t.Fatal(err)
	}
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
	if f.block.Hash == hash {
		return f.block, nil
	}
	return nexa.Block{}, errString("Block not found")
}
func (f *fakeNode) SendToAddress(address string, sats int64, comment string) (string, error) {
	if sats > f.balance {
		return "", errString("insufficient funds")
	}
	f.balance -= sats
	if f.notes == nil {
		f.notes = map[string]string{}
	}
	f.notes[comment] = "tx"
	f.sent = append(f.sent, sent{address, sats, comment})
	return "tx", nil
}
func (f *fakeNode) WalletBalance() (int64, error) { return f.balance, nil }
func (f *fakeNode) FindComment(comment string) (string, bool, error) {
	tx, ok := f.notes[comment]
	return tx, ok, nil
}
func (f *fakeNode) Unlock(string, int) error { return nil }
func (f *fakeNode) Lock(string) error        { return nil }
