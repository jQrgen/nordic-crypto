package pool

import (
	"encoding/hex"
	"path/filepath"
	"testing"
	"time"

	"github.com/jQrgen/nordic-crypto/pool/internal/nexa"
	"github.com/jQrgen/nordic-crypto/pool/internal/store"
	"github.com/jQrgen/nordic-crypto/pool/internal/stratum"
)

// The echelon full-hashing vector. Its digest meets the regtest compact
// target 0x207fffff and a tiny share target, and it does not meet Bitcoin
// difficulty 1 (compact 0x1d00ffff).
const (
	securityMiner = "nexa:nq2qqqgzqvzq2ps8pqys5zcvp58q7yq3zgfsalz92rn6"
	vectorCommit  = "0a4ac49b2d02e3c8d12c7093255ba7c49624f9c374d9f1c2f8e37c58705e74b0"
	vectorNonce   = "10000000000000001182dc5800000000"
)

func securityService(t *testing.T, node *fakeNode) *Service {
	t.Helper()
	db, err := store.Open(filepath.Join(t.TempDir(), "pool.sqlite"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { db.Close() })
	svc, err := New(Config{
		FeePercent: 1, FeeAddress: feeAddr, CoinbaseAddress: feeAddr, MinPayout: 100_000_000,
		Maturity: 5001, PPLNSBlocks: 2, HashrateWindow: time.Minute,
		PayoutEvery: time.Hour, TxReserve: 100,
	}, db, node, nil)
	if err != nil {
		t.Fatal(err)
	}
	return svc
}

func vectorShare(jobID string, diffMicros, ntime uint64) stratum.Share {
	nonce, _ := hex.DecodeString(vectorNonce)
	return stratum.Share{
		Address: securityMiner, Worker: "rig", JobID: jobID, Nonce: nonce,
		DifficultyMicros: diffMicros, NTime: ntime,
	}
}

func TestCraftedShareCountedOnlyUnderShareTarget(t *testing.T) {
	node := &fakeNode{
		cand: nexa.Candidate{ID: 3, HeaderCommitment: vectorCommit, NBits: "1d00ffff"},
		info: nexa.MiningInfo{Blocks: 10, Difficulty: 1},
	}
	svc := securityService(t, node)
	if err := svc.Poll(); err != nil {
		t.Fatal(err)
	}
	job, ok := svc.CurrentJob()
	if !ok {
		t.Fatal("no job")
	}

	// Tiny server-side difficulty: the published digest is under the share
	// target and over the network target, so it is stored and not submitted.
	okShare := vectorShare(job.ID, 1, job.Time)
	verdict := svc.Submit(okShare)
	if !verdict.Accept {
		t.Fatalf("share under the share target was rejected: %+v", verdict)
	}
	if len(node.submits) != 0 {
		t.Fatalf("share above the network target was submitted: %#v", node.submits)
	}
	view, err := svc.Lookup(securityMiner)
	if err != nil {
		t.Fatal(err)
	}
	if view.ValidShares != 1 {
		t.Fatalf("shares stored %d", view.ValidShares)
	}

	// The same digest at difficulty 1 is above the share target.
	low := svc.Submit(vectorShare(job.ID, nexa.Micros, job.Time))
	if low.Accept || low.Code != 23 {
		t.Fatalf("share above the share target: %+v", low)
	}
	view, err = svc.Lookup(securityMiner)
	if err != nil {
		t.Fatal(err)
	}
	if view.ValidShares != 1 {
		t.Fatalf("rejected share was stored, count %d", view.ValidShares)
	}
	if len(node.submits) != 0 {
		t.Fatal("low-difficulty share was submitted as a block")
	}
}

func TestCraftedBlockUsesCandidateTargetNotClientDifficulty(t *testing.T) {
	node := &fakeNode{
		cand: nexa.Candidate{ID: 9, HeaderCommitment: vectorCommit, NBits: "207fffff"},
		info: nexa.MiningInfo{Blocks: 10, Difficulty: 1},
	}
	svc := securityService(t, node)
	if err := svc.Poll(); err != nil {
		t.Fatal(err)
	}
	job, ok := svc.CurrentJob()
	if !ok {
		t.Fatal("no job")
	}
	// DifficultyMicros is what the session stored, not a field the miner
	// can put in mining.submit. A tiny value still has to meet the job nBits
	// before the node is called, and the RPC sees only the candidate id
	// and the nonce.
	verdict := svc.Submit(vectorShare(job.ID, 1, job.Time))
	if !verdict.Accept {
		t.Fatalf("%+v", verdict)
	}
	if len(node.submits) != 1 || node.submits[0].id != 9 || node.submits[0].nonce != vectorNonce {
		t.Fatalf("submit %#v", node.submits)
	}
	again := svc.Submit(vectorShare(job.ID, 1, job.Time))
	if again.Accept || again.Code != 22 {
		t.Fatalf("replay %+v", again)
	}
	if len(node.submits) != 1 {
		t.Fatalf("replay submitted the block again: %#v", node.submits)
	}
}

func TestReplayAcrossJobsWithTheSameCommitmentIsDuplicate(t *testing.T) {
	node := &fakeNode{info: nexa.MiningInfo{Blocks: 1, Difficulty: 1}}
	svc := securityService(t, node)
	info := nexa.MiningInfo{Blocks: 1, Difficulty: 1}
	if err := svc.publish(nexa.Candidate{ID: 1, HeaderCommitment: vectorCommit, NBits: "207fffff"}, info); err != nil {
		t.Fatal(err)
	}
	if err := svc.publish(nexa.Candidate{ID: 2, HeaderCommitment: vectorCommit, NBits: "207fffff"}, info); err != nil {
		t.Fatal(err)
	}
	// A clean publish drops the previous job id. The same proof on the new
	// job is still a duplicate of the pow hash once it is accepted there.
	stale := svc.Submit(vectorShare("1", 1, 0))
	if stale.Accept || stale.Code != 21 {
		t.Fatalf("replaced job %+v", stale)
	}
	cur, ok := svc.CurrentJob()
	if !ok {
		t.Fatal("no job")
	}
	first := svc.Submit(vectorShare(cur.ID, 1, cur.Time))
	if !first.Accept {
		t.Fatalf("current job %+v", first)
	}
	second := svc.Submit(vectorShare(cur.ID, 1, cur.Time))
	if second.Accept || second.Code != 22 {
		t.Fatalf("same proof on the current job: %+v", second)
	}
	if len(node.submits) != 1 {
		t.Fatalf("duplicate proof submitted twice: %#v", node.submits)
	}
}

func TestUnknownJobIsStaleAndCleanNotifyDropsThePreviousJob(t *testing.T) {
	node := &fakeNode{info: nexa.MiningInfo{Blocks: 1, Difficulty: 1}}
	svc := securityService(t, node)
	info := nexa.MiningInfo{Blocks: 1, Difficulty: 1}
	if err := svc.publish(nexa.Candidate{ID: 1, HeaderCommitment: vectorCommit, NBits: "207fffff"}, info); err != nil {
		t.Fatal(err)
	}
	missing := svc.Submit(vectorShare("no-such-job", 1, 0))
	if missing.Accept || missing.Code != 21 {
		t.Fatalf("unknown job %+v", missing)
	}

	// A clean publish is the only kind publish() emits. The previous job id
	// is rejected, which is what echelon requires.
	other := vectorCommit[:len(vectorCommit)-2] + "11"
	if err := svc.publish(nexa.Candidate{ID: 2, HeaderCommitment: other, NBits: "207fffff"}, info); err != nil {
		t.Fatal(err)
	}
	prev := svc.Submit(vectorShare("1", 1, 0))
	if prev.Accept || prev.Code != 21 {
		t.Fatalf("previous job survived clean notify: %+v", prev)
	}
}

func TestJobOlderThanTheWindowIsStale(t *testing.T) {
	node := &fakeNode{info: nexa.MiningInfo{Blocks: 1, Difficulty: 1}}
	svc := securityService(t, node)
	info := nexa.MiningInfo{Blocks: 1, Difficulty: 1}
	if err := svc.publish(nexa.Candidate{ID: 1, HeaderCommitment: vectorCommit, NBits: "207fffff"}, info); err != nil {
		t.Fatal(err)
	}
	for i := 0; i < 32; i++ {
		// Distinct commitments so each publish is a new job. The nonce will
		// not be valid for these; only the job id is under test.
		tail := hex.EncodeToString([]byte{byte(i + 1)})
		commit := vectorCommit[:len(vectorCommit)-2] + tail
		cand := nexa.Candidate{ID: int64(i + 2), HeaderCommitment: commit, NBits: "207fffff"}
		if err := svc.publish(cand, info); err != nil {
			t.Fatal(err)
		}
	}
	evicted := svc.Submit(vectorShare("1", 1, 0))
	if evicted.Accept || evicted.Code != 21 {
		t.Fatalf("evicted job %+v", evicted)
	}
	// The job just published is the only one kept. A garbage nonce is an
	// invalid proof (20), not a stale job (21).
	var kept string
	svc.mu.Lock()
	kept = svc.order[0]
	svc.mu.Unlock()
	cur, _ := svc.CurrentJob()
	garbage := stratum.Share{
		Address: securityMiner, JobID: kept, Nonce: []byte{0x01},
		DifficultyMicros: nexa.Micros * 1_000_000, NTime: cur.Time,
	}
	still := svc.Submit(garbage)
	// 20 is an unusable proof and 23 is a hash over the share target. Either
	// means the job is still known. 21 would mean it had been dropped.
	if still.Accept || still.Code == 21 {
		t.Fatalf("job %s inside the window: %+v", kept, still)
	}
}

func TestOneMissingBlockReplyDoesNotOrphanImmatureWork(t *testing.T) {
	node := &fakeNode{
		info:  nexa.MiningInfo{Blocks: 20, Difficulty: 1},
		block: nexa.Block{Hash: "other"},
	}
	svc := securityService(t, node)
	if _, err := svc.db.InsertBlock(store.Block{Height: 4, Hash: "aa", Finder: securityMiner}); err != nil {
		t.Fatal(err)
	}
	if err := svc.MatureOnce(); err != nil {
		t.Fatal(err)
	}
	rows, err := svc.db.RecentBlocks(5)
	if err != nil || len(rows) != 1 {
		t.Fatalf("%v %+v", err, rows)
	}
	if rows[0].Status != "immature" {
		t.Fatalf("status %s, want the block kept for retry", rows[0].Status)
	}
	node.block = nexa.Block{Hash: "aa", Height: 4, Confirmations: 5001, Reward: 10_000}
	if err := svc.MatureOnce(); err != nil {
		t.Fatal(err)
	}
	rows, err = svc.db.RecentBlocks(5)
	if err != nil || len(rows) != 1 || rows[0].Status != "mature" {
		t.Fatalf("retry did not mature: %+v %v", rows, err)
	}
}
