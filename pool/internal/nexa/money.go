package nexa

import (
	"fmt"
	"strings"
)

// Coin is the number of subunits in one NEX. nexad's COIN constant is 100,
// so amounts on the wire have two decimal places.
const Coin = 100

// FormatNEX renders subunits as a fixed-point NEX string with two decimals.
// The text is what sendtoaddress parses with ParseFixedPoint(..., 2).
func FormatNEX(sats int64) string {
	sign := ""
	if sats < 0 {
		sign = "-"
		sats = -sats
	}
	return fmt.Sprintf("%s%d.%02d", sign, sats/Coin, sats%Coin)
}

// ParseNEX parses a NEX amount with up to two decimal places into subunits.
// "1000000" and "1000000.00" are both 100_000_000 subunits.
func ParseNEX(s string) (int64, error) {
	s = strings.TrimSpace(s)
	if s == "" {
		return 0, fmt.Errorf("nexa: empty amount")
	}
	sign := int64(1)
	if s[0] == '-' {
		sign = -1
		s = s[1:]
	}
	whole, frac, hasFrac := strings.Cut(s, ".")
	if whole == "" || strings.Contains(frac, ".") {
		return 0, fmt.Errorf("nexa: bad amount %q", s)
	}
	if !hasFrac {
		frac = "00"
	}
	if len(frac) > 2 {
		return 0, fmt.Errorf("nexa: more than two decimal places in %q", s)
	}
	for len(frac) < 2 {
		frac += "0"
	}
	var w, f int64
	if _, err := fmt.Sscan(whole, &w); err != nil {
		return 0, fmt.Errorf("nexa: bad amount %q", s)
	}
	if _, err := fmt.Sscan(frac, &f); err != nil {
		return 0, fmt.Errorf("nexa: bad amount %q", s)
	}
	return sign * (w*Coin + f), nil
}
