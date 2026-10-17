// Package nexa implements the Nexa mining hash (NexaPow) and the
// helpers a pool needs to check shares against it.
//
// NexaPow is the algorithm in https://spec.nexa.org/mining/echelon-protocol/
// and src/pow.cpp of nexad: double SHA-256 of the header commitment and
// nonce, then a Bitcoin Cash Schnorr signature used as a proof of work.
package nexa

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"hash"
	"math/big"

	"github.com/decred/dcrd/dcrec/secp256k1/v4"
)

// ErrInvalidKey is returned when the mining hash is not a valid secp256k1
// private key. Nexa treats that candidate as failed proof of work.
var ErrInvalidKey = errors.New("nexa: mining hash is not a valid private key")

// PowHash runs NexaPow. headerCommitment and nonce are the bytes miners
// exchange on the wire (header commitment is big-endian hex decoded as-is,
// nonce is the hex-decoded solution nonce). prevHash is the previous summary
// block hash in the same display order. A nil or all-zero prevHash selects
// the pre-Tailstorm hash, which is what nexad 2.2 returns until Hard Fork 2.
//
// The returned digest is display order (big endian), the same order as
// uint256::GetHex in nexad, so it can be compared with a compact target.
func PowHash(headerCommitment, nonce, prevHash []byte) ([]byte, error) {
	if len(headerCommitment) != 32 {
		return nil, errors.New("nexa: header commitment must be 32 bytes")
	}
	if len(nonce) == 0 || len(nonce) > 16 {
		return nil, errors.New("nexa: nonce must be 1 to 16 bytes")
	}
	var buf bytes.Buffer
	buf.Write(reverse(headerCommitment))
	buf.WriteByte(byte(len(nonce)))
	buf.Write(nonce)
	mining := sha256d(buf.Bytes())

	var key secp256k1.ModNScalar
	if key.SetByteSlice(mining) || key.IsZero() {
		return nil, ErrInvalidKey
	}
	h1 := sha256.Sum256(mining)
	if len(prevHash) == 32 && !allZero(prevHash) {
		// Tailstorm binds the solution to the parent summary. nexad writes the
		// internal (little-endian) mining hash and previous hash into a single
		// SHA-256, then hashes that once more. See src/pow.cpp.
		combined := sha256.Sum256(append(append([]byte{}, mining...), reverse(prevHash)...))
		h1 = sha256.Sum256(combined[:])
	}
	sig, err := signBCH(mining, h1[:])
	if err != nil {
		return nil, err
	}
	final := sha256.Sum256(sig)
	return reverse(final[:]), nil
}

func sha256d(b []byte) []byte {
	first := sha256.Sum256(b)
	second := sha256.Sum256(first[:])
	return second[:]
}

func reverse(b []byte) []byte {
	out := make([]byte, len(b))
	for i := range b {
		out[i] = b[len(b)-1-i]
	}
	return out
}

func allZero(b []byte) bool {
	for _, c := range b {
		if c != 0 {
			return false
		}
	}
	return true
}

// signBCH is Bitcoin Cash Schnorr as implemented by nexad's
// secp256k1_schnorr_sign: RFC6979 nonce tagged "Schnorr+SHA256  ", negate
// the nonce unless R.y is a quadratic residue, e = SHA256(R.x || compressed
// pubkey || msg), s = k + e*x. The signature is R.x || s.
func signBCH(privBytes, msg []byte) ([]byte, error) {
	priv := secp256k1.PrivKeyFromBytes(privBytes)
	extra := []byte("Schnorr+SHA256  ")
	k := nonceRFC6979(priv.Serialize(), msg, extra)
	var R secp256k1.JacobianPoint
	secp256k1.ScalarBaseMultNonConst(k, &R)
	R.ToAffine()
	ry := new(big.Int).SetBytes(R.Y.Bytes()[:])
	if big.Jacobi(ry, secp256k1.Params().P) != 1 {
		k.Negate()
	}
	rx := R.X.Bytes()
	pub := priv.PubKey().SerializeCompressed()
	buf := make([]byte, 0, 32+33+32)
	buf = append(buf, rx[:]...)
	buf = append(buf, pub...)
	buf = append(buf, msg...)
	commitment := sha256.Sum256(buf)
	var e secp256k1.ModNScalar
	e.SetBytes(&commitment)
	s := new(secp256k1.ModNScalar).Mul2(&e, &priv.Key).Add(k)
	sig := make([]byte, 64)
	sb := s.Bytes()
	copy(sig[0:32], rx[:])
	copy(sig[32:64], sb[:])
	return sig, nil
}

var (
	hmacZero = []byte{0x00}
	hmacOne  = []byte{0x01}
	kZero    = bytes.Repeat([]byte{0x00}, sha256.BlockSize)
	vOne     = bytes.Repeat([]byte{0x01}, sha256.Size)
)

// hmacSHA256 is a small resettable HMAC used only for the RFC6979 nonce.
// It matches libsecp256k1's hasher, which is what nexad calls.
type hmacSHA256 struct {
	inner, outer hash.Hash
	ipad, opad   [sha256.BlockSize]byte
}

func newHMAC(key []byte) *hmacSHA256 {
	h := &hmacSHA256{inner: sha256.New(), outer: sha256.New()}
	h.initKey(key)
	return h
}

func (h *hmacSHA256) initKey(key []byte) {
	if len(key) > sha256.BlockSize {
		h.outer.Write(key)
		key = h.outer.Sum(nil)
	}
	copy(h.ipad[:], key)
	copy(h.opad[:], key)
	for i := range h.ipad {
		h.ipad[i] ^= 0x36
		h.opad[i] ^= 0x5c
	}
	h.inner.Write(h.ipad[:])
}

func (h *hmacSHA256) ResetKey(key []byte) {
	h.inner.Reset()
	h.outer.Reset()
	copy(h.ipad[:], kZero)
	copy(h.opad[:], kZero)
	h.initKey(key)
}

func (h *hmacSHA256) Reset() {
	h.inner.Reset()
	h.inner.Write(h.ipad[:])
}

func (h *hmacSHA256) Write(p []byte) { h.inner.Write(p) }

func (h *hmacSHA256) Sum() []byte {
	h.outer.Reset()
	h.outer.Write(h.opad[:])
	h.outer.Write(h.inner.Sum(nil))
	return h.outer.Sum(nil)
}

// nonceRFC6979 is libsecp256k1's RFC6979, including the 16-byte algorithm tag
// that Schnorr signing passes in. The extra tag is concatenated after the
// private key and message, which is how secp256k1_nonce_function_rfc6979
// builds its HMAC key material.
func nonceRFC6979(privKey, msg, extra []byte) *secp256k1.ModNScalar {
	var keyBuf [80]byte
	if len(privKey) > 32 {
		privKey = privKey[len(privKey)-32:]
	}
	if len(msg) > 32 {
		msg = msg[len(msg)-32:]
	}
	copy(keyBuf[32-len(privKey):32], privKey)
	copy(keyBuf[64-len(msg):64], msg)
	key := keyBuf[:64]

	v := append([]byte(nil), vOne...)
	k := append([]byte(nil), kZero[:32]...)
	mac := newHMAC(k)
	mac.Write(v)
	mac.Write(hmacZero)
	mac.Write(key)
	mac.Write(extra)
	k = mac.Sum()
	mac.ResetKey(k)
	mac.Write(v)
	v = mac.Sum()
	mac.Reset()
	mac.Write(v)
	mac.Write(hmacOne)
	mac.Write(key)
	mac.Write(extra)
	k = mac.Sum()
	mac.ResetKey(k)
	mac.Write(v)
	v = mac.Sum()
	for {
		mac.Reset()
		mac.Write(v)
		v = mac.Sum()
		var secret secp256k1.ModNScalar
		overflow := secret.SetByteSlice(v)
		if !overflow && !secret.IsZero() {
			return &secret
		}
		mac.Reset()
		mac.Write(v)
		mac.Write(hmacZero)
		k = mac.Sum()
		mac.ResetKey(k)
		mac.Write(v)
		v = mac.Sum()
	}
}

// DecodeHex decodes a hex string, ignoring an optional 0x prefix.
func DecodeHex(s string) ([]byte, error) {
	s = trimHex(s)
	if len(s)%2 == 1 {
		s = "0" + s
	}
	return hex.DecodeString(s)
}

func trimHex(s string) string {
	if len(s) >= 2 && (s[0:2] == "0x" || s[0:2] == "0X") {
		return s[2:]
	}
	return s
}
