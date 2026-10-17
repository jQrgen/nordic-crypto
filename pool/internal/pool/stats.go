package pool

import (
	"strings"
	"time"

	"github.com/jQrgen/nordic-crypto/pool/internal/nexa"
	"github.com/jQrgen/nordic-crypto/pool/internal/store"
)

// BlockView is one pool block for the public API.
type BlockView struct {
	Height        int64
	Hash          string
	Finder        string
	Reward        int64
	Status        string
	Confirmations int64
	FoundAt       time.Time
}

// PayoutView is one payout for the public API.
type PayoutView struct {
	Address string
	Amount  int64
	TxID    string
	Status  string
	At      time.Time
}

// AddressView is one miner's ledger.
type AddressView struct {
	Address       string
	Hashrate      float64
	ValidShares   int64
	InvalidShares int64
	Balance       int64
	Immature      int64
	Paid          int64
	Payouts       []PayoutView
}

// MinerView is one address in the hashrate window.
type MinerView struct {
	Address  string
	Workers  int
	Hashrate float64
}

// Stats is the public pool summary. Nil hashrate fields mean the node is
// offline and the number must not be shown as zero.
type Stats struct {
	NodeOnline      bool
	FeePercent      int
	MinPayout       string
	Maturity        int64
	PPLNSBlocks     float64
	PayoutEvery     int64
	StratumURL      string
	PoolHashrate    *float64
	Miners          *int
	NetworkHashrate *float64
	PoolShare       *float64
	LastBlock       *BlockView
}

// Snapshot reads the ledger and the last node sample.
func (s *Service) Snapshot() (Stats, error) {
	out := s.configStats()
	blocks, err := s.db.RecentBlocks(1)
	if err != nil {
		return Stats{}, err
	}
	if len(blocks) > 0 {
		view := blockView(blocks[0])
		out.LastBlock = &view
	}
	s.mu.Lock()
	online := s.online
	info := s.info
	s.mu.Unlock()
	out.NodeOnline = online
	if !online {
		return out, nil
	}
	miners, err := s.db.WorkSince(time.Now().Add(-s.cfg.HashrateWindow))
	if err != nil {
		return Stats{}, err
	}
	var work uint64
	for _, m := range miners {
		work += m.Work
	}
	rate := Hashrate(work, s.cfg.HashrateWindow)
	n := len(miners)
	net := info.NetworkHashrate
	out.PoolHashrate = &rate
	out.Miners = &n
	out.NetworkHashrate = &net
	if net > 0 {
		share := rate / net
		out.PoolShare = &share
	}
	return out, nil
}

func (s *Service) configStats() Stats {
	return Stats{
		FeePercent:  s.cfg.FeePercent,
		MinPayout:   nexa.FormatNEX(s.cfg.MinPayout),
		Maturity:    s.cfg.Maturity,
		PPLNSBlocks: s.cfg.PPLNSBlocks,
		PayoutEvery: int64(s.cfg.PayoutEvery / time.Second),
		StratumURL:  s.cfg.PublicStratum,
	}
}

// Blocks returns the newest pool blocks.
func (s *Service) Blocks(limit int) ([]BlockView, error) {
	rows, err := s.db.RecentBlocks(limit)
	if err != nil {
		return nil, err
	}
	out := make([]BlockView, len(rows))
	for i, row := range rows {
		out[i] = blockView(row)
	}
	return out, nil
}

// Miners returns addresses with work in the hashrate window.
// The boolean is false when the node is offline.
func (s *Service) Miners() ([]MinerView, bool, error) {
	s.mu.Lock()
	online := s.online
	s.mu.Unlock()
	if !online {
		return nil, false, nil
	}
	rows, err := s.db.WorkSince(time.Now().Add(-s.cfg.HashrateWindow))
	if err != nil {
		return nil, false, err
	}
	out := make([]MinerView, len(rows))
	for i, row := range rows {
		out[i] = MinerView{
			Address: row.Address, Workers: row.Workers,
			Hashrate: Hashrate(row.Work, s.cfg.HashrateWindow),
		}
	}
	return out, true, nil
}

// Lookup returns one address. The address must be a valid Nexa address.
func (s *Service) Lookup(address string) (AddressView, error) {
	address = strings.ToLower(strings.TrimSpace(address))
	if !nexa.ValidAddress(address) {
		return AddressView{}, ErrBadAddress
	}
	st, err := s.db.AddressStats(address, time.Now().Add(-s.cfg.HashrateWindow))
	if err != nil {
		return AddressView{}, err
	}
	pays, err := s.db.ListPayouts(address, 20)
	if err != nil {
		return AddressView{}, err
	}
	balance := st.Mature - st.Paid - st.Reserved
	if balance < 0 {
		balance = 0
	}
	view := AddressView{
		Address: address, Hashrate: Hashrate(st.Work, s.cfg.HashrateWindow),
		ValidShares: st.ValidShares, InvalidShares: st.InvalidShares,
		Balance: balance, Immature: st.Immature, Paid: st.Paid,
		Payouts: make([]PayoutView, len(pays)),
	}
	for i, p := range pays {
		view.Payouts[i] = PayoutView{Address: p.Address, Amount: p.Amount, TxID: p.TxID, Status: p.Status, At: p.At}
	}
	return view, nil
}

// Payouts returns the newest payouts.
func (s *Service) Payouts(limit int) ([]PayoutView, error) {
	rows, err := s.db.ListPayouts("", limit)
	if err != nil {
		return nil, err
	}
	out := make([]PayoutView, len(rows))
	for i, p := range rows {
		out[i] = PayoutView{Address: p.Address, Amount: p.Amount, TxID: p.TxID, Status: p.Status, At: p.At}
	}
	return out, nil
}

func blockView(b store.Block) BlockView {
	return BlockView{
		Height: b.Height, Hash: b.Hash, Finder: b.Finder, Reward: b.Reward,
		Status: b.Status, Confirmations: b.Confirmations, FoundAt: b.FoundAt,
	}
}
