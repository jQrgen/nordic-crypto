package nexa

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"testing"
	"time"
)

// TestPowHashTailstormMatchesPowCpp rebuilds the post-fork digest the way
// nexad src/pow.cpp does for powAlgorithm 1 when prevhash is not null.
//
// CSHA256Writer::GetHash is one SHA-256, not SHA-256d. `combine << hash <<
// prevhash` writes 32 raw bytes each, in internal (little-endian) order.
// h1 is then sha256 of that 32-byte digest. The parent on the wire is
// uint256::GetHex, so the pool reverses it before the mix, which is what
// nexa-miner does. The Schnorr step is the same function the pre-fork
// echelon vectors already lock.
//
// nexad's own tests do not publish a final post-fork hash. This locks the
// construction against the echelon header commitment and the first official
// nonce, with a non-zero parent.
func TestPowHashTailstormMatchesPowCpp(t *testing.T) {
	hc, err := hex.DecodeString("0a4ac49b2d02e3c8d12c7093255ba7c49624f9c374d9f1c2f8e37c58705e74b0")
	if err != nil {
		t.Fatal(err)
	}
	nonce, err := hex.DecodeString("10000000000000001182dc5800000000")
	if err != nil {
		t.Fatal(err)
	}
	parent := bytes.Repeat([]byte{0x11}, 32)
	parent[0] = 0x01
	parent[31] = 0x02

	var pre bytes.Buffer
	pre.Write(reverse(hc))
	pre.WriteByte(byte(len(nonce)))
	pre.Write(nonce)
	mining := sha256d(pre.Bytes())
	combined := sha256.Sum256(append(append([]byte{}, mining...), reverse(parent)...))
	h1 := sha256.Sum256(combined[:])
	sig, err := signBCH(mining, h1[:])
	if err != nil {
		t.Fatal(err)
	}
	final := sha256.Sum256(sig)
	want := reverse(final[:])

	got, err := PowHash(hc, nonce, parent)
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(got, want) {
		t.Fatalf("PowHash\n got %x\nwant %x", got, want)
	}
	if hex.EncodeToString(got) == "00000042cbc240375242e14641488a0e2dca7b54458a2cea23dc1d2c178bb188" {
		t.Fatal("parent mix matched the pre-fork echelon digest")
	}

	// A display-order parent that is not reversed would be a different mix.
	// PowHash must reverse, so feeding it the already-internal bytes (the
	// reverse of the display parent) must not match.
	flipped := reverse(parent)
	other, err := PowHash(hc, nonce, flipped)
	if err != nil {
		t.Fatal(err)
	}
	if bytes.Equal(other, got) {
		t.Fatal("reversing the parent did not change the digest")
	}
}

func TestTailstormActivationInstant(t *testing.T) {
	got := time.Unix(TailstormActivation, 0).UTC()
	want := time.Date(2026, 11, 1, 1, 11, 11, 0, time.UTC)
	if !got.Equal(want) {
		t.Fatalf("activation %s, want %s", got.Format(time.RFC3339), want.Format(time.RFC3339))
	}
	if TailstormActivation-1 >= TailstormActivation {
		t.Fatal("activation instant is not a single second")
	}
}
