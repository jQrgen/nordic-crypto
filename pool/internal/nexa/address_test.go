package nexa

import "testing"

func TestValidAddress(t *testing.T) {
	// Generated with the cashaddr polymod in nexad src/cashaddr.cpp.
	// Version 0 is pay-to-public-key-hash. Version 0x98 is a template
	// address, which is what Wally gives a miner.
	good := []string{
		"nexa:qqqqzqsrqszsvpcgpy9qkrqdpc83qygjzv5cxgkyhm",
		"nexa:nq2qqqgzqvzq2ps8pqys5zcvp58q7yq3zgfsalz92rn6",
		"NEXA:QQQQZQSRQSZSVPCGPY9QKRQDPC83QYGJZV5CXGKYHM",
	}
	for _, addr := range good {
		if !ValidAddress(addr) {
			t.Fatalf("rejected %s", addr)
		}
	}
	bad := []string{
		"",
		"nexa:qq9rw090p2eu9drv6ptztwx4ghpftwfa0gyqvlvx2q", // help-text example, bad checksum
		"nexatest:qqqqzqsrqszsvpcgpy9qkrqdpc83qygjzv5cxgkyhm",
		"bitcoincash:qqqqzqsrqszsvpcgpy9qkrqdpc83qygjzv5cxgkyhm",
		"nexa:qqqqzqsrqszsvpcgpy9qkrqdpc83qygjzv5cxgkyhM", // mixed case
		"not an address",
		"nexa:qqqq",
	}
	for _, addr := range bad {
		if ValidAddress(addr) {
			t.Fatalf("accepted %s", addr)
		}
	}
}
