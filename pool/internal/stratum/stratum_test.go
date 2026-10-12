package stratum

import (
	"bufio"
	"encoding/hex"
	"encoding/json"
	"math"
	"net"
	"strings"
	"testing"
	"time"

	"github.com/jQrgen/nordic-crypto/pool/internal/nexa"
)

func TestBindNonceKeepsOfficialVector(t *testing.T) {
	const (
		extra = "1000000000000000"
		full  = "10000000000000001182dc5800000000"
		want  = "00000042cbc240375242e14641488a0e2dca7b54458a2cea23dc1d2c178bb188"
	)
	got, err := bindNonce(extra, full)
	if err != nil {
		t.Fatal(err)
	}
	counter, err := bindNonce(extra, "1182dc5800000000")
	if err != nil {
		t.Fatal(err)
	}
	if hex.EncodeToString(got) != full || hex.EncodeToString(counter) != full {
		t.Fatalf("nonce changed: %x %x", got, counter)
	}
	hc, err := hex.DecodeString("0a4ac49b2d02e3c8d12c7093255ba7c49624f9c374d9f1c2f8e37c58705e74b0")
	if err != nil {
		t.Fatal(err)
	}
	pow, err := nexa.PowHash(hc, got, nil)
	if err != nil {
		t.Fatal(err)
	}
	if hex.EncodeToString(pow) != want {
		t.Fatalf("pow %x", pow)
	}
	if _, err := bindNonce(extra, "00112233445566778899aabbccddeeff00"); err == nil {
		t.Fatal("nonce longer than 16 bytes was accepted")
	}
}

func TestStratumDialect(t *testing.T) {
	srv := &Server{
		StartDiff: 200_000,
		VarDiff:   false,
		Hooks: Hooks{
			Authorize: func(address, worker string) error {
				if !nexa.ValidAddress(address) {
					return errBad
				}
				if worker == "nope" {
					return errBad
				}
				return nil
			},
			Submit: func(sh Share) Verdict {
				switch sh.JobID {
				case "dup":
					return Verdict{Code: errDuplicate, Message: "Duplicate share"}
				case "low":
					return Verdict{Code: errLowDiff, Message: "Low difficulty"}
				default:
					return Verdict{Accept: true}
				}
			},
		},
	}
	if err := srv.Listen("127.0.0.1:0"); err != nil {
		t.Fatal(err)
	}
	defer srv.Close()
	srv.SetJob(Job{
		ID: "4f", Commitment: strings.Repeat("ab", 32), NBits: "1b02fab2",
		Time: 0x63b1fb60, Clean: false,
	})

	conn, err := net.Dial("tcp", srv.Addr())
	if err != nil {
		t.Fatal(err)
	}
	defer conn.Close()
	rd := bufio.NewReader(conn)
	send := func(v any) {
		t.Helper()
		raw, _ := json.Marshal(v)
		conn.SetDeadline(time.Now().Add(3 * time.Second))
		if _, err := conn.Write(append(raw, '\n')); err != nil {
			t.Fatal(err)
		}
	}
	read := func() map[string]any {
		t.Helper()
		conn.SetDeadline(time.Now().Add(3 * time.Second))
		line, err := rd.ReadString('\n')
		if err != nil {
			t.Fatal(err)
		}
		var m map[string]any
		if err := json.Unmarshal([]byte(line), &m); err != nil {
			t.Fatal(err)
		}
		return m
	}

	send(map[string]any{"id": 1, "method": "mining.subscribe", "params": []any{"lolMiner/1.86", nil}})
	sub := read()
	if sub["id"].(float64) != 1 || sub["error"] != nil {
		t.Fatalf("subscribe %#v", sub)
	}
	result := sub["result"].([]any)
	subs := result[0].([]any)
	if subs[0].([]any)[0] != "mining.set_difficulty" || subs[1].([]any)[0] != "mining.notify" {
		t.Fatalf("subscriptions %#v", subs)
	}
	extra := result[1].(string)
	if len(extra) != 16 || result[2].(float64) != 8 {
		t.Fatalf("extranonce %#v", result[1:])
	}

	send(map[string]any{"id": 2, "method": "mining.authorize", "params": []any{"nexa:qqqqzqsrqszsvpcgpy9qkrqdpc83qygjzv5cxgkyhm.rig1", "x"}})
	if auth := read(); auth["result"] != true {
		t.Fatalf("authorize %#v", auth)
	}
	diff := read()
	if diff["method"] != "mining.set_difficulty" || math.Abs(diff["params"].([]any)[0].(float64)-0.2) > 1e-9 {
		t.Fatalf("difficulty %#v", diff)
	}
	note := read()
	if note["method"] != "mining.notify" {
		t.Fatalf("notify %#v", note)
	}
	np := note["params"].([]any)
	if np[0] != "4f" || np[1] != strings.Repeat("ab", 32) || np[2] != "1b02fab2" || np[3] != "0000000063b1fb60" || np[4] != false {
		t.Fatalf("notify params %#v", np)
	}

	nonce := extra + "1182dc58"
	send(map[string]any{"id": 3, "method": "mining.submit", "params": []any{
		"nexa:qqqqzqsrqszsvpcgpy9qkrqdpc83qygjzv5cxgkyhm.rig1", "4f", nonce, "0000000063b1fb60",
	}})
	if acc := read(); acc["result"] != true || acc["error"] != nil {
		t.Fatalf("submit %#v", acc)
	}

	send(map[string]any{"id": 4, "method": "mining.submit", "params": []any{
		"nexa:qqqqzqsrqszsvpcgpy9qkrqdpc83qygjzv5cxgkyhm", "dup", extra, "0000000063b1fb60", "aa",
	}})
	dup := read()
	errArr := dup["error"].([]any)
	if dup["result"] != false || errArr[0].(float64) != 22 {
		t.Fatalf("duplicate %#v", dup)
	}

	send(map[string]any{"id": 5, "method": "mining.submit", "params": []any{
		"nexa:qqqqzqsrqszsvpcgpy9qkrqdpc83qygjzv5cxgkyhm", "low", nonce, "0000000063b1fb60",
	}})
	low := read()
	if low["error"].([]any)[0].(float64) != 23 {
		t.Fatalf("low %#v", low)
	}

	send(map[string]any{"id": 6, "method": "mining.authorize", "params": []any{"not-an-address", "x"}})
	bad := read()
	if bad["error"].([]any)[0].(float64) != 24 {
		t.Fatalf("bad address %#v", bad)
	}
}

type badAddr struct{}

func (badAddr) Error() string { return "bad" }

var errBad = badAddr{}
