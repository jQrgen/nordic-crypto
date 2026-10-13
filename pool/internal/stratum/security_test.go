package stratum

import (
	"bufio"
	"encoding/json"
	"io"
	"net"
	"strings"
	"testing"
	"time"

	"github.com/jQrgen/nordic-crypto/pool/internal/nexa"
)

func TestCraftedNonceMustCarryThisConnectionExtranonce(t *testing.T) {
	const other = "00112233445566778899aabbccddeeff"
	mine, err := bindNonce("1000000000000000", other)
	if err == nil {
		t.Fatalf("16-byte nonce from another extranonce was accepted: %x", mine)
	}
	own, err := bindNonce("1000000000000000", "1000000000000000aabbccdd")
	if err != nil {
		t.Fatal(err)
	}
	upper, err := bindNonce("1000000000000000", "1000000000000000AABBCCDD")
	if err != nil || hexEqual(own, upper) == false {
		t.Fatalf("upper %x err %v", upper, err)
	}
	// A short counter is prefixed with this session's extranonce, not taken
	// as someone else's space.
	prefixed, err := bindNonce("1000000000000000", "aabbccdd")
	if err != nil {
		t.Fatal(err)
	}
	if got := encodeHex(prefixed); got != "1000000000000000aabbccdd" {
		t.Fatalf("prefixed %s", got)
	}
}

func TestTwoSessionsDoNotShareAnExtranonce(t *testing.T) {
	srv := &Server{StartDiff: 200_000, MinDiff: 50_000, MaxDiff: 4096 * nexa.Micros}
	if err := srv.Listen("127.0.0.1:0"); err != nil {
		t.Fatal(err)
	}
	defer srv.Close()
	a := subscribeExtra(t, srv)
	b := subscribeExtra(t, srv)
	if a == b {
		t.Fatalf("two connections received the same extranonce %s", a)
	}
	if len(a) != 16 || len(b) != 16 {
		t.Fatalf("extranonce lengths %d %d", len(a), len(b))
	}
}

func TestSubmitUsesSessionDifficultyNotTheMessage(t *testing.T) {
	var got uint64
	srv := &Server{
		StartDiff: 200_000,
		MinDiff:   50_000,
		MaxDiff:   4096 * nexa.Micros,
		Hooks: Hooks{
			Authorize: func(string, string) error { return nil },
			Submit: func(sh Share) Verdict {
				got = sh.DifficultyMicros
				return Verdict{Accept: true}
			},
		},
	}
	if err := srv.Listen("127.0.0.1:0"); err != nil {
		t.Fatal(err)
	}
	defer srv.Close()
	conn, rd, extra := dialSubscribeAuthorize(t, srv)
	defer conn.Close()

	writeLine(t, conn, map[string]any{"id": 3, "method": "mining.submit", "params": []any{
		"nexa:qqqqzqsrqszsvpcgpy9qkrqdpc83qygjzv5cxgkyhm", "job", extra + "aa", "0000000063b1fb60",
	}})
	ack := readMap(t, conn, rd)
	if ack["result"] != true || got != 200_000 {
		t.Fatalf("ack %#v difficulty %d", ack, got)
	}
}

func TestSuggestDifficultyCannotLowerTheSession(t *testing.T) {
	client, server := net.Pipe()
	defer client.Close()
	defer server.Close()
	go func() { _, _ = io.Copy(io.Discard, client) }()

	srv := &Server{StartDiff: 200_000, MinDiff: 50_000, MaxDiff: 4096 * nexa.Micros, VarDiff: true}
	sess := newSession(srv, server, "127.0.0.1", "1000000000000000")
	sess.diff.Store(4096 * nexa.Micros)
	sess.vardiff.micros = 4096 * nexa.Micros
	sess.suggest(request{
		ID:     json.RawMessage("1"),
		Method: "mining.suggest_difficulty",
		Params: json.RawMessage(`[0.05]`),
	})
	if sess.diff.Load() != 4096*nexa.Micros {
		t.Fatalf("unauthorized suggest changed difficulty to %d", sess.diff.Load())
	}
	sess.authorized.Store(true)
	sess.suggest(request{
		ID:     json.RawMessage("2"),
		Method: "mining.suggest_difficulty",
		Params: json.RawMessage(`[0.05]`),
	})
	if sess.diff.Load() != 4096*nexa.Micros || sess.vardiff.micros != 4096*nexa.Micros {
		t.Fatalf("suggest lowered the session to %d", sess.diff.Load())
	}
}

func TestOversizedLineIsDropped(t *testing.T) {
	srv := &Server{StartDiff: 200_000, Hooks: Hooks{Authorize: func(string, string) error { return nil }}}
	if err := srv.Listen("127.0.0.1:0"); err != nil {
		t.Fatal(err)
	}
	defer srv.Close()
	conn, err := net.Dial("tcp", srv.Addr())
	if err != nil {
		t.Fatal(err)
	}
	defer conn.Close()
	payload := []byte(`{"id":1,"method":"mining.subscribe","params":["` + strings.Repeat("A", 70*1024) + `"]}`)
	conn.SetDeadline(time.Now().Add(3 * time.Second))
	if _, err := conn.Write(append(payload, '\n')); err != nil {
		t.Fatal(err)
	}
	buf := make([]byte, 1)
	_, err = conn.Read(buf)
	if err == nil {
		t.Fatal("oversized line was answered")
	}
}

func TestMalformedJSONDoesNotDropTheSession(t *testing.T) {
	srv := &Server{StartDiff: 200_000, Hooks: Hooks{Authorize: func(string, string) error { return nil }}}
	if err := srv.Listen("127.0.0.1:0"); err != nil {
		t.Fatal(err)
	}
	defer srv.Close()
	conn, err := net.Dial("tcp", srv.Addr())
	if err != nil {
		t.Fatal(err)
	}
	defer conn.Close()
	rd := bufio.NewReader(conn)
	writeLine(t, conn, "{")
	bad := readMap(t, conn, rd)
	errArr, _ := bad["error"].([]any)
	if len(errArr) == 0 || errArr[0].(float64) != 20 {
		t.Fatalf("bad json %#v", bad)
	}
	writeLine(t, conn, map[string]any{"id": 1, "method": "mining.subscribe", "params": []any{"rig/1"}})
	ok := readMap(t, conn, rd)
	if ok["error"] != nil {
		t.Fatalf("session died after bad json: %#v", ok)
	}
}

func subscribeExtra(t *testing.T, srv *Server) string {
	t.Helper()
	conn, err := net.Dial("tcp", srv.Addr())
	if err != nil {
		t.Fatal(err)
	}
	defer conn.Close()
	rd := bufio.NewReader(conn)
	writeLine(t, conn, map[string]any{"id": 1, "method": "mining.subscribe", "params": []any{"rig/1"}})
	sub := readMap(t, conn, rd)
	result, _ := sub["result"].([]any)
	if len(result) < 2 {
		t.Fatalf("subscribe %#v", sub)
	}
	extra, _ := result[1].(string)
	return extra
}

func dialSubscribeAuthorize(t *testing.T, srv *Server) (net.Conn, *bufio.Reader, string) {
	t.Helper()
	conn, err := net.Dial("tcp", srv.Addr())
	if err != nil {
		t.Fatal(err)
	}
	rd := bufio.NewReader(conn)
	writeLine(t, conn, map[string]any{"id": 1, "method": "mining.subscribe", "params": []any{"rig/1"}})
	sub := readMap(t, conn, rd)
	result := sub["result"].([]any)
	extra := result[1].(string)
	writeLine(t, conn, map[string]any{"id": 2, "method": "mining.authorize", "params": []any{
		"nexa:qqqqzqsrqszsvpcgpy9qkrqdpc83qygjzv5cxgkyhm.rig", "x",
	}})
	if auth := readMap(t, conn, rd); auth["result"] != true {
		t.Fatalf("auth %#v", auth)
	}
	if diff := readMap(t, conn, rd); diff["method"] != "mining.set_difficulty" {
		t.Fatalf("difficulty %#v", diff)
	}
	return conn, rd, extra
}

func writeLine(t *testing.T, conn net.Conn, v any) {
	t.Helper()
	var raw []byte
	switch s := v.(type) {
	case string:
		raw = []byte(s)
	default:
		var err error
		raw, err = json.Marshal(v)
		if err != nil {
			t.Fatal(err)
		}
	}
	conn.SetDeadline(time.Now().Add(3 * time.Second))
	if _, err := conn.Write(append(raw, '\n')); err != nil {
		t.Fatal(err)
	}
}

func readMap(t *testing.T, conn net.Conn, rd *bufio.Reader) map[string]any {
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

func hexEqual(a, b []byte) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

func encodeHex(b []byte) string {
	const hexdigits = "0123456789abcdef"
	out := make([]byte, len(b)*2)
	for i, c := range b {
		out[i*2] = hexdigits[c>>4]
		out[i*2+1] = hexdigits[c&0x0f]
	}
	return string(out)
}
