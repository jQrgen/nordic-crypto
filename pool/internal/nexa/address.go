package nexa

import (
	"strings"
)

// Charset is the cashaddr alphabet used by Nexa.
const Charset = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"

const (
	versionP2PKH    = 0x00
	versionP2SH     = 0x08
	versionTemplate = 0x98
)

// ValidAddress reports whether s is a mainnet Nexa cashaddr we can pay.
// Accepted forms are pay-to-public-key-hash, pay-to-script-hash and a
// template address (the kind Wally creates). The checksum is the cashaddr
// polymod implemented by nexad in src/cashaddr.cpp.
func ValidAddress(s string) bool {
	prefix, version, payload, ok := decodeAddress(s)
	if !ok || prefix != "nexa" {
		return false
	}
	switch version {
	case versionP2PKH, versionP2SH:
		return len(payload) == 20
	case versionTemplate:
		return len(payload) > 0 && int(payload[0]) == len(payload)-1
	default:
		return false
	}
}

func decodeAddress(s string) (prefix string, version byte, payload []byte, ok bool) {
	s = strings.TrimSpace(s)
	lower := strings.ToLower(s)
	upper := strings.ToUpper(s)
	if s != lower && s != upper {
		return "", 0, nil, false
	}
	colon := strings.LastIndexByte(lower, ':')
	if colon < 1 || colon+9 > len(lower) {
		return "", 0, nil, false
	}
	prefix = lower[:colon]
	data := make([]byte, 0, len(lower)-colon-1)
	for i := colon + 1; i < len(lower); i++ {
		idx := strings.IndexByte(Charset, lower[i])
		if idx < 0 {
			return "", 0, nil, false
		}
		data = append(data, byte(idx))
	}
	if cashPolymod(expandPrefix(prefix), data) != 1 {
		return "", 0, nil, false
	}
	body := data[:len(data)-8]
	converted := convertBits(body, 5, 8, false)
	if len(converted) < 2 {
		return "", 0, nil, false
	}
	return prefix, converted[0], converted[1:], true
}

func expandPrefix(prefix string) []byte {
	out := make([]byte, len(prefix)+1)
	for i := 0; i < len(prefix); i++ {
		out[i] = prefix[i] & 0x1f
	}
	return out
}

func cashPolymod(prefix, values []byte) uint64 {
	chk := uint64(1)
	feed := func(v byte) {
		top := chk >> 35
		chk = ((chk & 0x07ffffffff) << 5) ^ uint64(v)
		if top&0x01 != 0 {
			chk ^= 0x98f2bc8e61
		}
		if top&0x02 != 0 {
			chk ^= 0x79b76d99e2
		}
		if top&0x04 != 0 {
			chk ^= 0xf33e5fb3c4
		}
		if top&0x08 != 0 {
			chk ^= 0xae2eabe2a8
		}
		if top&0x10 != 0 {
			chk ^= 0x1e4f43e470
		}
	}
	for _, v := range prefix {
		feed(v)
	}
	for _, v := range values {
		feed(v)
	}
	return chk
}

func convertBits(data []byte, from, to uint, pad bool) []byte {
	acc := 0
	bits := uint(0)
	maxv := (1 << to) - 1
	out := make([]byte, 0, len(data)*int(from)/int(to)+1)
	for _, value := range data {
		acc = (acc << from) | int(value)
		bits += from
		for bits >= to {
			bits -= to
			out = append(out, byte((acc>>bits)&maxv))
		}
	}
	if pad {
		if bits > 0 {
			out = append(out, byte((acc<<(to-bits))&maxv))
		}
		return out
	}
	if bits >= from || ((acc<<(to-bits))&maxv) != 0 {
		return nil
	}
	return out
}
