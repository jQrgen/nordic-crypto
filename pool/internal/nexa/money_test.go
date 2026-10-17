package nexa

import "testing"

func TestMoneyRoundTrip(t *testing.T) {
	cases := []struct {
		sats int64
		text string
	}{
		{0, "0.00"},
		{1, "0.01"},
		{100, "1.00"},
		{100_000_000, "1000000.00"},
		{100_000_001, "1000000.01"},
	}
	for _, tc := range cases {
		if got := FormatNEX(tc.sats); got != tc.text {
			t.Fatalf("format %d = %s, want %s", tc.sats, got, tc.text)
		}
		back, err := ParseNEX(tc.text)
		if err != nil || back != tc.sats {
			t.Fatalf("parse %s = %d, %v", tc.text, back, err)
		}
	}
	if _, err := ParseNEX("1.001"); err == nil {
		t.Fatal("three decimal places were accepted")
	}
	got, err := ParseNEX("1000000")
	if err != nil || got != 100_000_000 {
		t.Fatalf("whole nex = %d, %v", got, err)
	}
}
