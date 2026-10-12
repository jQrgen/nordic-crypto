package stratum

import (
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
