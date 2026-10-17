package stratum

import "time"

// VarDiff adjusts a miner's share difficulty so shares arrive about every
// target interval. The difficulty is a power-of-two multiple of the start
// value, clamped to a range, and it does not move more often than every
// retarget interval.
type VarDiff struct {
	micros   uint64
	min      uint64
	max      uint64
	last     time.Time
	retarget time.Time
	started  time.Time
	grace    time.Duration
	samples  []time.Duration
}

func newVarDiff(start, min, max uint64, now time.Time) *VarDiff {
	if start < min {
		start = min
	}
	if start > max {
		start = max
	}
	return &VarDiff{micros: start, min: min, max: max, last: now, retarget: now, started: now}
}

// Observe records a share and returns the difficulty to use from now on.
// changed is true when the miner must be told.
func (v *VarDiff) Observe(now time.Time) (micros uint64, changed bool) {
	gap := now.Sub(v.last)
	if gap < 0 {
		gap = 0
	}
	v.last = now
	v.samples = append(v.samples, gap)
	if len(v.samples) > 8 {
		v.samples = v.samples[1:]
	}
	wait := 60 * time.Second
	if v.grace > 0 && now.Sub(v.started) < v.grace {
		// Climb quickly while the session is still at the start
		// difficulty. A fast miner would otherwise sit under the
		// submit cap for a full minute between each doubling.
		wait = 10 * time.Second
	}
	if now.Sub(v.retarget) < wait || len(v.samples) < 4 {
		return v.micros, false
	}
	var sum time.Duration
	for _, s := range v.samples {
		sum += s
	}
	avg := sum / time.Duration(len(v.samples))
	next := v.micros
	switch {
	case avg < 8*time.Second && v.micros < v.max:
		next = v.micros * 2
		if next > v.max {
			next = v.max
		}
	case avg > 30*time.Second && v.micros > v.min:
		next = v.micros / 2
		if next < v.min {
			next = v.min
		}
	}
	v.retarget = now
	v.samples = nil
	if next == v.micros {
		return v.micros, false
	}
	v.micros = next
	return next, true
}
