package nexa

import (
	"encoding/hex"
	"math/big"
	"testing"
)

func TestOfficialVectorMeetsEasyTargetOnly(t *testing.T) {
	hc, _ := hex.DecodeString("0a4ac49b2d02e3c8d12c7093255ba7c49624f9c374d9f1c2f8e37c58705e74b0")
	nonce, _ := hex.DecodeString("10000000000000001182dc5800000000")
	sum, err := PowHash(hc, nonce, nil)
	if err != nil {
		t.Fatal(err)
	}
	h := HashInt(sum)

	// 0x207fffff is the regtest-style compact target: a real solution of the
	// published vector is a block at that difficulty.
	easy := CompactToTarget(0x207fffff)
	if !Meets(h, easy) {
		t.Fatal("published vector did not meet 0x207fffff")
	}

	// Difficulty 1 is far below this digest (the digest has fewer leading
	// zero bits than the difficulty-1 target).
	if Meets(h, ShareTarget(1*Micros)) {
		t.Fatal("published vector unexpectedly met difficulty 1")
	}

	// A very easy share difficulty must accept it. 0.000001 is the smallest
	// step we store in micros.
	if !Meets(h, ShareTarget(1)) {
		t.Fatal("published vector did not meet a tiny share difficulty")
	}
}

func TestShareTargetMonotonic(t *testing.T) {
	low := ShareTarget(200_000)  // 0.2
	high := ShareTarget(400_000) // 0.4
	if low.Cmp(high) <= 0 {
		t.Fatal("a higher difficulty did not produce a lower target")
	}
	if CompactToTarget(0) != nil || CompactToTarget(0x00800001) != nil {
		t.Fatal("invalid compact targets were accepted")
	}
}

func TestWorkHashes(t *testing.T) {
	// Difficulty 1 is exactly 2^32 hashes.
	got := WorkHashes(Micros)
	if got != 4294967296 {
		t.Fatalf("work = %v", got)
	}
	if WorkHashes(200_000) != 4294967296*0.2 {
		t.Fatal("0.2 difficulty did not scale")
	}
	_ = new(big.Int)
}
