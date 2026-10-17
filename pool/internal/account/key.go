package account

import (
	"crypto/rand"
	"encoding/hex"
)

func newKey() (string, error) {
	var buf [16]byte
	if _, err := rand.Read(buf[:]); err != nil {
		return "", err
	}
	return "nexapool:" + hex.EncodeToString(buf[:]), nil
}
