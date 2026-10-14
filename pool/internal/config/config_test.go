package config

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestLoadRejectsEmptyFeeAddress(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "pool.toml")
	if err := os.WriteFile(path, []byte(`
[pool]
fee_percent = 1
fee_address = ""
[node]
cookie_file = "/var/lib/nexa/.nexa/.cookie"
[db]
path = "/var/lib/nexapool/pool.sqlite"
`), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := Load(path); err == nil {
		t.Fatal("empty fee address was accepted")
	}
}

func TestLoadDefaults(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "pool.toml")
	if err := os.WriteFile(path, []byte(`
[pool]
fee_percent = 1
fee_address = "nexa:qqqqzqsrqszsvpcgpy9qkrqdpc83qygjzv5cxgkyhm"
coinbase_address = "nexa:qqqqzqsrqszsvpcgpy9qkrqdpc83qygjzv5cxgkyhm"
[node]
cookie_file = "/var/lib/nexa/.nexa/.cookie"
[db]
path = "/var/lib/nexapool/pool.sqlite"
`), 0o600); err != nil {
		t.Fatal(err)
	}
	t.Setenv("NEXAPOOL_RPC_USER", "rpcuser")
	t.Setenv("NEXAPOOL_RPC_PASSWORD", "secret-not-in-repo")
	cfg, err := Load(path)
	if err != nil {
		t.Fatal(err)
	}
	if cfg.FeePercent != 1 || cfg.MinPayout != 100_000_000 || cfg.Maturity != 5001 || cfg.PPLNSBlocks != 2 {
		t.Fatalf("%+v", cfg)
	}
	if cfg.RPCUser != "rpcuser" || cfg.RPCPassword != "secret-not-in-repo" {
		t.Fatal("environment credentials were not applied")
	}
	if cfg.StartDiff != 200_000 || cfg.StratumListen != "0.0.0.0:3333" || cfg.APIListen != "127.0.0.1:8080" {
		t.Fatalf("defaults %+v", cfg)
	}
	if cfg.TxReserve != 100 {
		t.Fatalf("reserve %d", cfg.TxReserve)
	}
	if cfg.Maturity != 5001 || cfg.PayoutConfs != 1 || cfg.MaxPerIP != 16 || cfg.HotWalletMax <= 0 {
		t.Fatalf("security defaults %+v", cfg)
	}
	if cfg.CoinbaseAddress == "" || cfg.SubmitRate != 128 || cfg.SubmitBurst != 256 || cfg.BanAfter != 20 || cfg.SubmitGrace != 3*time.Minute {
		t.Fatalf("submit and coinbase defaults %+v", cfg)
	}
	if cfg.Tailstorm != "" && cfg.Tailstorm != "auto" {
		t.Fatalf("tailstorm %+v", cfg.Tailstorm)
	}
	if cfg.ReleaseNoneMinAge != 24*time.Hour {
		t.Fatalf("release none age %s", cfg.ReleaseNoneMinAge)
	}
	if cfg.ReleaseConflictDepth != 10 {
		t.Fatalf("release conflict depth %d", cfg.ReleaseConflictDepth)
	}
}

func TestLoadRejectsPublicBind(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "pool.toml")
	body := `
[pool]
fee_percent = 1
fee_address = "nexa:qqqqzqsrqszsvpcgpy9qkrqdpc83qygjzv5cxgkyhm"
coinbase_address = "nexa:qqqqzqsrqszsvpcgpy9qkrqdpc83qygjzv5cxgkyhm"
[api]
listen = "0.0.0.0:8080"
[node]
url = "http://127.0.0.1:7227/"
cookie_file = "/var/lib/nexa/.nexa/.cookie"
[db]
path = "/var/lib/nexapool/pool.sqlite"
`
	if err := os.WriteFile(path, []byte(body), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := Load(path); err == nil {
		t.Fatal("public api bind was accepted")
	}
	body = strings.ReplaceAll(body, `listen = "0.0.0.0:8080"`, `listen = "127.0.0.1:8080"`)
	body = strings.ReplaceAll(body, `url = "http://127.0.0.1:7227/"`, `url = "http://203.0.113.5:7227/"`)
	if err := os.WriteFile(path, []byte(body), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := Load(path); err == nil {
		t.Fatal("public node url was accepted")
	}
}

func TestLoadRejectsEarlyMaturityAndEmptyCoinbase(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "pool.toml")
	body := `
[pool]
fee_percent = 1
fee_address = "nexa:qqqqzqsrqszsvpcgpy9qkrqdpc83qygjzv5cxgkyhm"
coinbase_address = "nexa:qqqqzqsrqszsvpcgpy9qkrqdpc83qygjzv5cxgkyhm"
maturity = 5000
[node]
cookie_file = "/var/lib/nexa/.nexa/.cookie"
[db]
path = "/var/lib/nexapool/pool.sqlite"
`
	if err := os.WriteFile(path, []byte(body), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := Load(path); err == nil {
		t.Fatal("maturity 5000 was accepted")
	}
	body = strings.ReplaceAll(body, "maturity = 5000", "maturity = 5001")
	body = strings.ReplaceAll(body, `coinbase_address = "nexa:qqqqzqsrqszsvpcgpy9qkrqdpc83qygjzv5cxgkyhm"`, `coinbase_address = ""`)
	if err := os.WriteFile(path, []byte(body), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := Load(path); err == nil {
		t.Fatal("empty coinbase address was accepted")
	}
}

func TestLoadRejectsShallowConflictDepth(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "pool.toml")
	body := `
[pool]
fee_percent = 1
fee_address = "nexa:qqqqzqsrqszsvpcgpy9qkrqdpc83qygjzv5cxgkyhm"
coinbase_address = "nexa:qqqqzqsrqszsvpcgpy9qkrqdpc83qygjzv5cxgkyhm"
release_conflict_depth = 5
[node]
cookie_file = "/var/lib/nexa/.nexa/.cookie"
[db]
path = "/var/lib/nexapool/pool.sqlite"
`
	if err := os.WriteFile(path, []byte(body), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := Load(path); err == nil {
		t.Fatal("release_conflict_depth 5 was accepted")
	}
	body = strings.ReplaceAll(body, "release_conflict_depth = 5", "release_conflict_depth = 6")
	if err := os.WriteFile(path, []byte(body), 0o600); err != nil {
		t.Fatal(err)
	}
	cfg, err := Load(path)
	if err != nil {
		t.Fatal(err)
	}
	if cfg.ReleaseConflictDepth != 6 {
		t.Fatalf("depth %d", cfg.ReleaseConflictDepth)
	}
}
