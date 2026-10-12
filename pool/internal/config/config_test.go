package config

import (
	"os"
	"path/filepath"
	"testing"
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
	if cfg.FeePercent != 1 || cfg.MinPayout != 100_000_000 || cfg.Maturity != 5000 || cfg.PPLNSBlocks != 2 {
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
}
