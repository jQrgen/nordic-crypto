// Package config loads the pool's TOML file. Secrets are not read from the
// file: the RPC password comes from the environment or from nexad's cookie,
// and a wallet passphrase is a separate file outside the repository.
package config

import (
	"fmt"
	"net"
	"os"
	"strings"
	"time"

	"github.com/BurntSushi/toml"
	"github.com/jQrgen/nordic-crypto/pool/internal/nexa"
)

// Config is the running configuration.
type Config struct {
	FeePercent      int
	FeeAddress      string
	CoinbaseAddress string
	MinPayout       int64
	Maturity        int64
	PPLNSBlocks     float64
	PayoutEvery     time.Duration
	HashrateWindow  time.Duration
	TxReserve       int64
	PublicStratum   string
	PayoutConfs     int64
	HotWalletMax    int64

	StratumListen string
	VarDiff       bool
	StartDiff     uint64
	MinDiff       uint64
	MaxDiff       uint64
	MaxPerIP      int

	APIListen string
	WebRoot   string

	NodeURL        string
	CookieFile     string
	RPCUser        string
	RPCPassword    string
	PassphraseFile string

	Database string
}

type file struct {
	Pool struct {
		FeePercent          int     `toml:"fee_percent"`
		FeeAddress          string  `toml:"fee_address"`
		CoinbaseAddress     string  `toml:"coinbase_address"`
		MinPayout           string  `toml:"min_payout"`
		Maturity            int64   `toml:"maturity"`
		PPLNSBlocks         float64 `toml:"pplns_blocks"`
		PayoutInterval      string  `toml:"payout_interval"`
		HashrateWindow      string  `toml:"hashrate_window"`
		TxReserve           string  `toml:"tx_reserve"`
		PublicStratum       string  `toml:"public_stratum"`
		PayoutConfirmations int64   `toml:"payout_confirmations"`
		HotWalletMax        string  `toml:"hot_wallet_max"`
	} `toml:"pool"`
	Stratum struct {
		Listen          string  `toml:"listen"`
		VarDiff         bool    `toml:"vardiff"`
		StartDifficulty float64 `toml:"start_difficulty"`
		MinDifficulty   float64 `toml:"min_difficulty"`
		MaxDifficulty   float64 `toml:"max_difficulty"`
		MaxPerIP        int     `toml:"max_per_ip"`
	} `toml:"stratum"`
	API struct {
		Listen  string `toml:"listen"`
		WebRoot string `toml:"web_root"`
	} `toml:"api"`
	Node struct {
		URL            string `toml:"url"`
		CookieFile     string `toml:"cookie_file"`
		PassphraseFile string `toml:"passphrase_file"`
	} `toml:"node"`
	DB struct {
		Path string `toml:"path"`
	} `toml:"db"`
}

// Load reads path and applies NEXAPOOL_RPC_USER and NEXAPOOL_RPC_PASSWORD
// when they are set. An empty fee address is an error.
func Load(path string) (Config, error) {
	var f file
	if _, err := toml.DecodeFile(path, &f); err != nil {
		return Config{}, fmt.Errorf("config: %w", err)
	}
	cfg := Config{
		FeePercent:      f.Pool.FeePercent,
		FeeAddress:      strings.TrimSpace(f.Pool.FeeAddress),
		CoinbaseAddress: strings.TrimSpace(f.Pool.CoinbaseAddress),
		Maturity:        f.Pool.Maturity,
		PPLNSBlocks:     f.Pool.PPLNSBlocks,
		PublicStratum:   strings.TrimSpace(f.Pool.PublicStratum),
		PayoutConfs:     f.Pool.PayoutConfirmations,
		StratumListen:   f.Stratum.Listen,
		VarDiff:         f.Stratum.VarDiff,
		MaxPerIP:        f.Stratum.MaxPerIP,
		APIListen:       f.API.Listen,
		WebRoot:         f.API.WebRoot,
		NodeURL:         f.Node.URL,
		CookieFile:      f.Node.CookieFile,
		PassphraseFile:  f.Node.PassphraseFile,
		Database:        f.DB.Path,
		RPCUser:         os.Getenv("NEXAPOOL_RPC_USER"),
		RPCPassword:     os.Getenv("NEXAPOOL_RPC_PASSWORD"),
	}
	if cfg.FeePercent == 0 {
		cfg.FeePercent = 1
	}
	if cfg.FeePercent < 1 || cfg.FeePercent > 100 {
		return Config{}, fmt.Errorf("config: fee_percent must be from 1 to 100")
	}
	if cfg.FeeAddress == "" || !nexa.ValidAddress(cfg.FeeAddress) {
		return Config{}, fmt.Errorf("config: fee_address must be a Nexa address")
	}
	if cfg.CoinbaseAddress != "" && !nexa.ValidAddress(cfg.CoinbaseAddress) {
		return Config{}, fmt.Errorf("config: coinbase_address must be a Nexa address")
	}
	minText := f.Pool.MinPayout
	if minText == "" {
		minText = "1000000.00"
	}
	minSats, err := nexa.ParseNEX(minText)
	if err != nil || minSats <= 0 {
		return Config{}, fmt.Errorf("config: min_payout")
	}
	cfg.MinPayout = minSats
	if cfg.Maturity <= 0 {
		cfg.Maturity = 5001
	}
	if cfg.PayoutConfs <= 0 {
		cfg.PayoutConfs = 1
	}
	if cfg.PPLNSBlocks <= 0 {
		cfg.PPLNSBlocks = 2
	}
	cfg.PayoutEvery, err = parseDuration(f.Pool.PayoutInterval, time.Hour)
	if err != nil {
		return Config{}, err
	}
	cfg.HashrateWindow, err = parseDuration(f.Pool.HashrateWindow, 15*time.Minute)
	if err != nil {
		return Config{}, err
	}
	reserve := f.Pool.TxReserve
	if reserve == "" {
		reserve = "1.00"
	}
	cfg.TxReserve, err = nexa.ParseNEX(reserve)
	if err != nil || cfg.TxReserve < 0 {
		return Config{}, fmt.Errorf("config: tx_reserve")
	}
	hot := f.Pool.HotWalletMax
	if hot == "" {
		hot = "5000000.00"
	}
	cfg.HotWalletMax, err = nexa.ParseNEX(hot)
	if err != nil || cfg.HotWalletMax <= 0 {
		return Config{}, fmt.Errorf("config: hot_wallet_max")
	}
	if cfg.PublicStratum == "" {
		cfg.PublicStratum = "stratum+tcp://pool.nordiccrypto.no:3333"
	}
	if cfg.StratumListen == "" {
		cfg.StratumListen = "0.0.0.0:3333"
	}
	if cfg.APIListen == "" {
		cfg.APIListen = "127.0.0.1:8080"
	}
	if err := requireLoopbackListen(cfg.APIListen); err != nil {
		return Config{}, err
	}
	if cfg.NodeURL == "" {
		cfg.NodeURL = "http://127.0.0.1:7227/"
	}
	if err := nexa.RequireLoopbackURL(cfg.NodeURL); err != nil {
		return Config{}, fmt.Errorf("config: %w", err)
	}
	if cfg.Database == "" {
		return Config{}, fmt.Errorf("config: db.path is empty")
	}
	if cfg.RPCUser == "" && cfg.RPCPassword == "" && cfg.CookieFile == "" {
		return Config{}, fmt.Errorf("config: set node.cookie_file or NEXAPOOL_RPC_USER and NEXAPOOL_RPC_PASSWORD")
	}
	cfg.StartDiff = diffMicros(f.Stratum.StartDifficulty, 0.2)
	cfg.MinDiff = diffMicros(f.Stratum.MinDifficulty, 0.05)
	cfg.MaxDiff = diffMicros(f.Stratum.MaxDifficulty, 4096)
	if cfg.MaxPerIP <= 0 {
		cfg.MaxPerIP = 16
	}
	if cfg.MinDiff > cfg.StartDiff || cfg.StartDiff > cfg.MaxDiff {
		return Config{}, fmt.Errorf("config: difficulty range is out of order")
	}
	return cfg, nil
}

func parseDuration(s string, fallback time.Duration) (time.Duration, error) {
	if strings.TrimSpace(s) == "" {
		return fallback, nil
	}
	d, err := time.ParseDuration(s)
	if err != nil || d <= 0 {
		return 0, fmt.Errorf("config: bad duration %q", s)
	}
	return d, nil
}

func requireLoopbackListen(addr string) error {
	host, _, err := net.SplitHostPort(addr)
	if err != nil {
		return fmt.Errorf("config: api listen: %w", err)
	}
	if !nexa.LoopbackHost(host) {
		return fmt.Errorf("config: api listen must be localhost")
	}
	return nil
}

func diffMicros(v, fallback float64) uint64 {
	if v <= 0 {
		v = fallback
	}
	return uint64(v*float64(nexa.Micros) + 0.5)
}
