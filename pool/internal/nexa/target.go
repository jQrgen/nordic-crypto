package nexa

import "math/big"

// Micros is the fixed-point scale for a stratum difficulty. 0.2 is stored
// as 200_000. Share accounting uses this integer so fee and payout math
// never depends on a binary float.
const Micros = 1_000_000

// diff1 is the Bitcoin difficulty-1 target. Nexa miners (lolMiner, BzMiner,
// Rigel, SRBMiner) treat mining.set_difficulty on this scale: the share
// target is this value divided by the difficulty number.
var diff1 = mustTarget("00000000ffff0000000000000000000000000000000000000000000000000000")

func mustTarget(hex string) *big.Int {
	n, ok := new(big.Int).SetString(hex, 16)
	if !ok {
		panic("bad target hex")
	}
	return n
}

// CompactToTarget expands a Bitcoin-style nBits compact word into a target.
// A negative or zero encoding returns nil so the caller rejects the share.
func CompactToTarget(compact uint32) *big.Int {
	mantissa := compact & 0x007fffff
	if compact&0x00800000 != 0 || mantissa == 0 {
		return nil
	}
	exponent := uint(compact >> 24)
	if exponent == 0 {
		return nil
	}
	n := new(big.Int).SetUint64(uint64(mantissa))
	if exponent <= 3 {
		n.Rsh(n, 8*(3-exponent))
	} else {
		n.Lsh(n, 8*(exponent-3))
	}
	if n.Sign() <= 0 || n.BitLen() > 256 {
		return nil
	}
	return n
}

// ShareTarget is the largest proof-of-work digest that still meets the
// given stratum difficulty. diffMicros is difficulty times Micros.
func ShareTarget(diffMicros uint64) *big.Int {
	if diffMicros == 0 {
		return nil
	}
	num := new(big.Int).Mul(diff1, big.NewInt(Micros))
	return num.Div(num, new(big.Int).SetUint64(diffMicros))
}

// Meets reports whether a display-order proof-of-work digest is less than
// or equal to target.
func Meets(powHash, target *big.Int) bool {
	if powHash == nil || target == nil || target.Sign() <= 0 {
		return false
	}
	return powHash.Cmp(target) <= 0
}

// HashInt interprets a display-order digest as an integer.
func HashInt(powHash []byte) *big.Int {
	return new(big.Int).SetBytes(powHash)
}

// WorkHashes is the expected number of NexaPow attempts a share of the
// given difficulty represents. It is difficulty * 2^32, which is the same
// scale nexad uses for getnetworkhashps.
func WorkHashes(diffMicros uint64) float64 {
	return float64(diffMicros) * 4294967296 / Micros
}
