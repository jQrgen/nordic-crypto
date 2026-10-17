package stratum

import (
	"net"
	"testing"
	"time"
)

func TestVarDiffRisesAndFalls(t *testing.T) {
	start := time.Unix(1_700_000_000, 0)
	v := newVarDiff(200_000, 50_000, 4_000_000, start)
	now := start
	for i := 0; i < 4; i++ {
		now = now.Add(time.Second)
		if _, changed := v.Observe(now); changed {
			t.Fatal("retargeted before the wait")
		}
	}
	// The difficulty change is reported by the share that crosses the wait.
	v.retarget = now.Add(-61 * time.Second)
	now = now.Add(time.Second)
	micros, changed := v.Observe(now)
	if !changed || micros != 400_000 {
		t.Fatalf("rise got %d changed %v", micros, changed)
	}
	v.retarget = now.Add(-61 * time.Second)
	var fell bool
	for i := 0; i < 4; i++ {
		now = now.Add(45 * time.Second)
		micros, fell = v.Observe(now)
	}
	if !fell || micros != 200_000 {
		t.Fatalf("fall got %d changed %v", micros, fell)
	}
}

func TestVarDiffRampsDuringGrace(t *testing.T) {
	start := time.Unix(1_700_000_000, 0)
	v := newVarDiff(200_000, 50_000, 4_000_000, start)
	v.grace = 3 * time.Minute
	now := start
	var micros uint64
	var changed bool
	for i := 0; i < 4; i++ {
		now = now.Add(3 * time.Second)
		micros, changed = v.Observe(now)
	}
	if !changed || micros != 400_000 {
		t.Fatalf("grace retarget got %d changed %v after %s", micros, changed, now.Sub(start))
	}
}

func TestRateLimitDoesNotBanDuringGrace(t *testing.T) {
	a, b := net.Pipe()
	defer a.Close()
	defer b.Close()
	srv := &Server{
		SubmitRate: 1, SubmitBurst: 1, BanAfter: 2, SubmitGrace: time.Minute,
		bans: map[string]time.Time{},
	}
	sess := newSession(srv, a, "127.0.0.1", "aa")
	sess.tokens = 0
	sess.tokenAt = sess.started
	if sess.allowSubmit(sess.started) {
		t.Fatal("rate limit did not trip")
	}
	if sess.rateLimitBans(sess.started.Add(time.Second)) {
		t.Fatal("a rate-limit miss during the grace would ban")
	}
	sess.started = time.Now().Add(-2 * time.Minute)
	if !sess.rateLimitBans(time.Now()) {
		t.Fatal("rate-limit bans stayed off after the grace")
	}
	sess.bad = srv.BanAfter
	sess.penalise()
	srv.mu.Lock()
	defer srv.mu.Unlock()
	if _, ok := srv.bans["127.0.0.1"]; !ok {
		t.Fatal("rate-limit ban did not apply after the grace")
	}
}
