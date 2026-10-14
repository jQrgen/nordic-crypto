package main

import (
	"errors"
	"strings"
	"testing"
)

func TestRefuseUnlocked(t *testing.T) {
	if err := refuseUnlocked(nil); err != nil {
		t.Fatal(err)
	}
	err := refuseUnlocked(errors.New("connection refused"))
	if err == nil || !strings.Contains(err.Error(), "lockunspent failed") {
		t.Fatalf("startup lock error %v", err)
	}
}
