package main

import (
	"context"
	"flag"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/jQrgen/nordic-crypto/pool/internal/api"
	"github.com/jQrgen/nordic-crypto/pool/internal/config"
	"github.com/jQrgen/nordic-crypto/pool/internal/nexa"
	"github.com/jQrgen/nordic-crypto/pool/internal/pool"
	"github.com/jQrgen/nordic-crypto/pool/internal/store"
	"github.com/jQrgen/nordic-crypto/pool/internal/stratum"
)

func main() {
	path := flag.String("config", "/etc/nexapool/nexapool.toml", "path to the TOML configuration")
	flag.Parse()
	logger := log.New(os.Stderr, "nexapool: ", log.LstdFlags|log.LUTC)

	cfg, err := config.Load(*path)
	if err != nil {
		logger.Fatal(err)
	}
	db, err := store.Open(cfg.Database)
	if err != nil {
		logger.Fatal(err)
	}
	defer db.Close()
	node, err := nexa.NewClient(cfg.NodeURL, cfg.RPCUser, cfg.RPCPassword, cfg.CookieFile)
	if err != nil {
		logger.Fatal(err)
	}
	svc, err := pool.New(pool.Config{
		FeePercent: cfg.FeePercent, FeeAddress: cfg.FeeAddress, CoinbaseAddress: cfg.CoinbaseAddress,
		MinPayout: cfg.MinPayout, Maturity: cfg.Maturity, PPLNSBlocks: cfg.PPLNSBlocks,
		HashrateWindow: cfg.HashrateWindow, PayoutEvery: cfg.PayoutEvery, TxReserve: cfg.TxReserve,
		PublicStratum: cfg.PublicStratum,
	}, db, node, logger)
	if err != nil {
		logger.Fatal(err)
	}
	if cfg.PassphraseFile != "" {
		raw, err := os.ReadFile(cfg.PassphraseFile)
		if err != nil {
			logger.Fatalf("wallet passphrase file: %v", err)
		}
		svc.SetPassphrase(string(raw))
	}

	stratumSrv := &stratum.Server{
		Hooks:     stratum.Hooks{Authorize: svc.Authorize, Submit: svc.Submit},
		StartDiff: cfg.StartDiff, MinDiff: cfg.MinDiff, MaxDiff: cfg.MaxDiff, VarDiff: cfg.VarDiff,
	}
	svc.Attach(stratumSrv)
	if err := stratumSrv.Listen(cfg.StratumListen); err != nil {
		logger.Fatal(err)
	}
	defer stratumSrv.Close()
	logger.Printf("stratum listening on %s", cfg.StratumListen)

	if err := svc.Poll(); err != nil {
		logger.Printf("node is not ready: %v", err)
	}

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()
	go every(ctx, 5*time.Second, func() {
		if err := svc.Poll(); err != nil {
			logger.Printf("candidate: %v", err)
		}
	})
	go every(ctx, time.Minute, func() {
		if err := svc.MatureOnce(); err != nil {
			logger.Printf("maturity: %v", err)
		}
	})
	go every(ctx, cfg.PayoutEvery, func() {
		result, err := svc.PayOnce()
		if err != nil {
			logger.Printf("payout: %v", err)
			return
		}
		if result.Sent > 0 || result.Failed > 0 || result.Deferred > 0 {
			logger.Printf("payout sent %d failed %d deferred %d", result.Sent, result.Failed, result.Deferred)
		}
	})

	httpSrv := &http.Server{
		Addr: cfg.APIListen, Handler: api.Handler(svc, cfg.WebRoot, logger),
		ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 15 * time.Second, WriteTimeout: 30 * time.Second,
	}
	go func() {
		logger.Printf("api listening on %s", cfg.APIListen)
		if err := httpSrv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Fatal(err)
		}
	}()
	<-ctx.Done()
	shut, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	_ = httpSrv.Shutdown(shut)
}

func every(ctx context.Context, interval time.Duration, fn func()) {
	tick := time.NewTicker(interval)
	defer tick.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-tick.C:
			fn()
		}
	}
}
