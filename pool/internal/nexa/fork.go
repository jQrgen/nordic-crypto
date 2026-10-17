package nexa

import "strings"

// TailstormParent reports whether previousBlockHash from getminingcandidate
// is a real parent summary. nexad leaves that field as 64 zero bytes until
// fTailstormEnabled is set, which happens when the tip is pending the
// upgrade, one block before the median-time check. The pool follows the
// candidate. It does not switch on a wall-clock instant.
func TailstormParent(prevHex string) bool {
	prevHex = strings.ToLower(strings.TrimSpace(prevHex))
	if len(prevHex) != 64 {
		return false
	}
	for i := 0; i < len(prevHex); i++ {
		if prevHex[i] != '0' {
			return true
		}
	}
	return false
}
