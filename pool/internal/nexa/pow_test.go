package nexa

import (
	"bytes"
	"encoding/hex"
	"testing"
)

// Vectors from https://spec.nexa.org/mining/echelon-protocol/ (the "Full
// hashing examples" section). They are the values a pool and a miner must
// agree on, including the intermediate Schnorr signature.
func TestPowHashOfficialVectors(t *testing.T) {
	commitment := "0a4ac49b2d02e3c8d12c7093255ba7c49624f9c374d9f1c2f8e37c58705e74b0"
	cases := []struct {
		nonce string
		want  string
	}{
		{
			nonce: "10000000000000001182dc5800000000",
			want:  "00000042cbc240375242e14641488a0e2dca7b54458a2cea23dc1d2c178bb188",
		},
		{
			nonce: "1000000000000000b787915d00000000",
			want:  "0000005f0b59e110863566e77d85e1b4fc713754e5c75f8fc3df44133866a669",
		},
	}
	hc, err := hex.DecodeString(commitment)
	if err != nil {
		t.Fatal(err)
	}
	for _, tc := range cases {
		nonce, err := hex.DecodeString(tc.nonce)
		if err != nil {
			t.Fatal(err)
		}
		got, err := PowHash(hc, nonce, nil)
		if err != nil {
			t.Fatalf("nonce %s: %v", tc.nonce, err)
		}
		if hex.EncodeToString(got) != tc.want {
			t.Fatalf("nonce %s\n got %x\nwant %s", tc.nonce, got, tc.want)
		}
		// An all-zero previous hash is the value nexad sends when Tailstorm
		// is off. It must not change the hash.
		zeros := make([]byte, 32)
		again, err := PowHash(hc, nonce, zeros)
		if err != nil {
			t.Fatal(err)
		}
		if !bytes.Equal(got, again) {
			t.Fatalf("zero prevhash changed the digest")
		}
	}
}

func TestPowHashTailstormBindsParent(t *testing.T) {
	hc, _ := hex.DecodeString("0a4ac49b2d02e3c8d12c7093255ba7c49624f9c374d9f1c2f8e37c58705e74b0")
	nonce, _ := hex.DecodeString("10000000000000001182dc5800000000")
	classic, err := PowHash(hc, nonce, nil)
	if err != nil {
		t.Fatal(err)
	}
	parent := bytes.Repeat([]byte{0x11}, 32)
	bound, err := PowHash(hc, nonce, parent)
	if err != nil {
		t.Fatal(err)
	}
	if bytes.Equal(classic, bound) {
		t.Fatal("tailstorm hash matched the pre-fork hash")
	}
	again, err := PowHash(hc, nonce, parent)
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(bound, again) {
		t.Fatal("tailstorm hash was not stable")
	}
}

func TestPowHashRejectsBadInput(t *testing.T) {
	nonce := []byte{1, 2, 3, 4}
	if _, err := PowHash(make([]byte, 31), nonce, nil); err == nil {
		t.Fatal("short commitment was accepted")
	}
	if _, err := PowHash(make([]byte, 32), nil, nil); err == nil {
		t.Fatal("empty nonce was accepted")
	}
	if _, err := PowHash(make([]byte, 32), make([]byte, 17), nil); err == nil {
		t.Fatal("overlong nonce was accepted")
	}
}
