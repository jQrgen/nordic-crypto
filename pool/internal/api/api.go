// Package api is the public JSON read API. It does not serve mock numbers:
// hashrate fields are null when the node is offline.
package api

import (
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"strconv"
	"time"

	"github.com/jQrgen/nordic-crypto/pool/internal/nexa"
	"github.com/jQrgen/nordic-crypto/pool/internal/pool"
)

const explorerBlock = "https://explorer.nordiccrypto.no/nexa/block/"

// Handler serves /api/v1 and, when webRoot is set, the static site.
func Handler(svc *pool.Service, webRoot string, logger *log.Logger) http.Handler {
	if logger == nil {
		logger = log.Default()
	}
	h := &handler{svc: svc, log: logger}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/v1/stats", h.stats)
	mux.HandleFunc("GET /api/v1/blocks", h.blocks)
	mux.HandleFunc("GET /api/v1/miners", h.miners)
	mux.HandleFunc("GET /api/v1/address/{address}", h.address)
	mux.HandleFunc("GET /api/v1/payouts", h.payouts)
	mux.HandleFunc("GET /api/v1/health", h.health)
	if webRoot != "" {
		mux.Handle("/", http.FileServer(http.Dir(webRoot)))
	}
	return mux
}

type handler struct {
	svc *pool.Service
	log *log.Logger
}

func (h *handler) stats(w http.ResponseWriter, r *http.Request) {
	stats, err := h.svc.Snapshot()
	if err != nil {
		h.fail(w, err)
		return
	}
	writeJSON(w, http.StatusOK, statsJSON(stats))
}

func (h *handler) blocks(w http.ResponseWriter, r *http.Request) {
	rows, err := h.svc.Blocks(limit(r))
	if err != nil {
		h.fail(w, err)
		return
	}
	out := make([]blockBody, len(rows))
	for i, b := range rows {
		out[i] = blockJSON(b)
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *handler) miners(w http.ResponseWriter, r *http.Request) {
	rows, online, err := h.svc.Miners()
	if err != nil {
		h.fail(w, err)
		return
	}
	body := map[string]any{"node_online": online}
	if !online {
		body["miners"] = nil
		writeJSON(w, http.StatusOK, body)
		return
	}
	list := make([]map[string]any, len(rows))
	for i, m := range rows {
		list[i] = map[string]any{"address": m.Address, "workers": m.Workers, "hashrate": m.Hashrate}
	}
	body["miners"] = list
	writeJSON(w, http.StatusOK, body)
}

func (h *handler) address(w http.ResponseWriter, r *http.Request) {
	view, err := h.svc.Lookup(r.PathValue("address"))
	if errors.Is(err, pool.ErrBadAddress) {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid address"})
		return
	}
	if err != nil {
		h.fail(w, err)
		return
	}
	pays := make([]payoutBody, len(view.Payouts))
	for i, p := range view.Payouts {
		pays[i] = payoutJSON(p)
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"address":        view.Address,
		"hashrate":       view.Hashrate,
		"valid_shares":   view.ValidShares,
		"invalid_shares": view.InvalidShares,
		"balance":        nexa.FormatNEX(view.Balance),
		"immature":       nexa.FormatNEX(view.Immature),
		"paid":           nexa.FormatNEX(view.Paid),
		"payouts":        pays,
	})
}

func (h *handler) payouts(w http.ResponseWriter, r *http.Request) {
	rows, err := h.svc.Payouts(limit(r))
	if err != nil {
		h.fail(w, err)
		return
	}
	out := make([]payoutBody, len(rows))
	for i, p := range rows {
		out[i] = payoutJSON(p)
	}
	writeJSON(w, http.StatusOK, out)
}

func (h *handler) health(w http.ResponseWriter, r *http.Request) {
	stats, err := h.svc.Snapshot()
	if err != nil {
		h.fail(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"ok": true, "node_online": stats.NodeOnline})
}

func (h *handler) fail(w http.ResponseWriter, err error) {
	h.log.Printf("api: %v", err)
	writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "unavailable"})
}

func limit(r *http.Request) int {
	n, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	if n <= 0 || n > 100 {
		return 20
	}
	return n
}

type statsBody struct {
	NodeOnline      bool       `json:"node_online"`
	FeePercent      int        `json:"fee_percent"`
	MinPayout       string     `json:"min_payout"`
	Maturity        int64      `json:"maturity_confirmations"`
	PPLNSBlocks     float64    `json:"pplns_blocks"`
	PayoutEvery     int64      `json:"payout_interval_seconds"`
	StratumURL      string     `json:"stratum_url"`
	PoolHashrate    *float64   `json:"pool_hashrate"`
	Miners          *int       `json:"miners"`
	NetworkHashrate *float64   `json:"network_hashrate"`
	PoolShare       *float64   `json:"pool_share"`
	LastBlock       *blockBody `json:"last_block"`
}

type blockBody struct {
	Height        int64     `json:"height"`
	Hash          string    `json:"hash"`
	Finder        string    `json:"finder"`
	Reward        string    `json:"reward"`
	Status        string    `json:"status"`
	Confirmations int64     `json:"confirmations"`
	FoundAt       time.Time `json:"found_at"`
	URL           string    `json:"url"`
}

type payoutBody struct {
	Address string    `json:"address"`
	Amount  string    `json:"amount"`
	TxID    string    `json:"txid"`
	Status  string    `json:"status"`
	At      time.Time `json:"time"`
}

func statsJSON(s pool.Stats) statsBody {
	body := statsBody{
		NodeOnline: s.NodeOnline, FeePercent: s.FeePercent, MinPayout: s.MinPayout,
		Maturity: s.Maturity, PPLNSBlocks: s.PPLNSBlocks, PayoutEvery: s.PayoutEvery,
		StratumURL: s.StratumURL, PoolHashrate: s.PoolHashrate, Miners: s.Miners,
		NetworkHashrate: s.NetworkHashrate, PoolShare: s.PoolShare,
	}
	if s.LastBlock != nil {
		b := blockJSON(*s.LastBlock)
		body.LastBlock = &b
	}
	return body
}

func blockJSON(b pool.BlockView) blockBody {
	return blockBody{
		Height: b.Height, Hash: b.Hash, Finder: b.Finder, Reward: nexa.FormatNEX(b.Reward),
		Status: b.Status, Confirmations: b.Confirmations, FoundAt: b.FoundAt,
		URL: fmt.Sprintf("%s%d", explorerBlock, b.Height),
	}
}

func payoutJSON(p pool.PayoutView) payoutBody {
	return payoutBody{Address: p.Address, Amount: nexa.FormatNEX(p.Amount), TxID: p.TxID, Status: p.Status, At: p.At}
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("X-Content-Type-Options", "nosniff")
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(status)
	enc := json.NewEncoder(w)
	enc.SetEscapeHTML(false)
	_ = enc.Encode(v)
}
