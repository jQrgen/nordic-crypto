// Package account is the pool's bookkeeping: PPLNS, the fee, and the
// rules that decide when a payout may be sent.
package account

import "fmt"

// Share is one accepted share inside a PPLNS window. Work is the share's
// stratum difficulty in micros (difficulty * 1_000_000).
type Share struct {
	Address string
	Work    uint64
}

// Credit is a satoshi amount owed to an address from one block.
type Credit struct {
	Address string
	Amount  int64
	Kind    string // "miner" or "fee"
}

// Window returns the newest shares whose work adds up to at least target.
// shares must be oldest first. If the history is shorter than the target,
// every share is returned. An empty history returns nil.
func Window(shares []Share, target uint64) []Share {
	if len(shares) == 0 || target == 0 {
		return nil
	}
	var sum uint64
	start := len(shares)
	for i := len(shares) - 1; i >= 0; i-- {
		start = i
		sum += shares[i].Work
		if sum >= target {
			break
		}
	}
	out := make([]Share, len(shares)-start)
	copy(out, shares[start:])
	return out
}

// Split divides a block reward. percent is the pool fee in whole percent
// (1 means one percent). The fee is the floor of reward * percent / 100.
// The rest is split across the window in proportion to work, also floored.
// Leftover satoshis from that flooring are added to the fee, so the credits
// sum to the reward and miners are never paid more than their share.
//
// With no shares, the whole reward is a fee credit: the pool found the
// block without recorded work, and the coins stay with the operator.
func Split(reward int64, percent int, feeAddress string, shares []Share) ([]Credit, error) {
	if reward < 0 {
		return nil, fmt.Errorf("account: negative reward")
	}
	if percent < 0 || percent > 100 {
		return nil, fmt.Errorf("account: fee percent %d", percent)
	}
	if feeAddress == "" {
		return nil, fmt.Errorf("account: fee address is empty")
	}
	if reward == 0 {
		return nil, nil
	}
	fee := reward * int64(percent) / 100
	payable := reward - fee
	var total uint64
	for _, sh := range shares {
		if sh.Address == "" || sh.Work == 0 {
			return nil, fmt.Errorf("account: share missing address or work")
		}
		total += sh.Work
	}
	miner := map[string]int64{}
	var paid int64
	if total > 0 && payable > 0 {
		for _, sh := range shares {
			part := payable * int64(sh.Work) / int64(total)
			miner[sh.Address] += part
			paid += part
		}
	}
	fee += payable - paid
	out := make([]Credit, 0, len(miner)+1)
	if fee > 0 {
		out = append(out, Credit{Address: feeAddress, Amount: fee, Kind: "fee"})
	}
	for addr, amount := range miner {
		if amount == 0 {
			continue
		}
		out = append(out, Credit{Address: addr, Amount: amount, Kind: "miner"})
	}
	var sum int64
	for _, c := range out {
		if c.Amount < 0 {
			return nil, fmt.Errorf("account: negative credit")
		}
		sum += c.Amount
	}
	if sum != reward {
		return nil, fmt.Errorf("account: credits %d != reward %d", sum, reward)
	}
	return out, nil
}
