package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strings"
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
	if len(os.Args) > 1 {
		logger := log.New(os.Stderr, "nexapool: ", log.LstdFlags|log.LUTC)
		switch os.Args[1] {
		case "review":
			if err := reviewCommand(logger, os.Args[2:]); err != nil {
				logger.Fatal(err)
			}
			return
		case "comment":
			if err := commentCommand(logger, os.Args[2:]); err != nil {
				logger.Fatal(err)
			}
			return
		case "inputs":
			if err := inputsCommand(logger, os.Args[2:]); err != nil {
				logger.Fatal(err)
			}
			return
		}
	}
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
	node.PoolAddress = cfg.CoinbaseAddress
	node.Log = logger
	svc, err := pool.New(pool.Config{
		FeePercent: cfg.FeePercent, FeeAddress: cfg.FeeAddress, CoinbaseAddress: cfg.CoinbaseAddress,
		MinPayout: cfg.MinPayout, Maturity: cfg.Maturity, PPLNSBlocks: cfg.PPLNSBlocks,
		HashrateWindow: cfg.HashrateWindow, PayoutEvery: cfg.PayoutEvery, TxReserve: cfg.TxReserve,
		PublicStratum: cfg.PublicStratum, PayoutConfs: cfg.PayoutConfs, HotWalletMax: cfg.HotWalletMax,
		Tailstorm: cfg.Tailstorm, TailstormAt: cfg.TailstormAt, ReleaseNoneMinAge: cfg.ReleaseNoneMinAge,
		ReleaseConflictDepth: cfg.ReleaseConflictDepth,
	}, db, node, logger)
	if err != nil {
		logger.Fatal(err)
	}
	if cfg.PassphraseFile != "" {
		raw, err := nexa.ReadPrivateFile(cfg.PassphraseFile)
		if err != nil {
			logger.Fatalf("wallet passphrase file: %v", err)
		}
		svc.SetPassphrase(string(raw))
	}
	if err := refuseUnlocked(svc.LockReservedCoins()); err != nil {
		logger.Fatal(err)
	}

	stratumSrv := &stratum.Server{
		Hooks:     stratum.Hooks{Authorize: svc.Authorize, Submit: svc.Submit},
		StartDiff: cfg.StartDiff, MinDiff: cfg.MinDiff, MaxDiff: cfg.MaxDiff, VarDiff: cfg.VarDiff,
		MaxPerIP:    cfg.MaxPerIP,
		SubmitRate:  cfg.SubmitRate,
		SubmitBurst: cfg.SubmitBurst,
		BanAfter:    cfg.BanAfter,
		SubmitGrace: cfg.SubmitGrace,
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

func reviewCommand(logger *log.Logger, args []string) error {
	fs := flag.NewFlagSet("review", flag.ContinueOnError)
	path := fs.String("config", "/etc/nexapool/nexapool.toml", "path to the TOML configuration")
	id := fs.Int64("id", 0, "payout id to resolve")
	action := fs.String("resolve", "", "complete or release")
	confirm := fs.String("confirm", "", "for release: the stored txidem after a different txidem has spent an input at release_conflict_depth, or none when the row was never signed and is old enough")
	fs.SetOutput(os.Stderr)
	if err := fs.Parse(args); err != nil {
		return err
	}
	cfg, err := config.Load(*path)
	if err != nil {
		return err
	}
	db, err := store.Open(cfg.Database)
	if err != nil {
		return err
	}
	defer db.Close()
	node, err := nexa.NewClient(cfg.NodeURL, cfg.RPCUser, cfg.RPCPassword, cfg.CookieFile)
	if err != nil {
		return err
	}
	node.PoolAddress = cfg.CoinbaseAddress
	node.Log = logger
	svc, err := pool.New(pool.Config{
		FeePercent: cfg.FeePercent, FeeAddress: cfg.FeeAddress, CoinbaseAddress: cfg.CoinbaseAddress,
		MinPayout: cfg.MinPayout, Maturity: cfg.Maturity, PPLNSBlocks: cfg.PPLNSBlocks,
		HashrateWindow: cfg.HashrateWindow, PayoutEvery: cfg.PayoutEvery, TxReserve: cfg.TxReserve,
		PublicStratum: cfg.PublicStratum, PayoutConfs: cfg.PayoutConfs, HotWalletMax: cfg.HotWalletMax,
		Tailstorm: cfg.Tailstorm, TailstormAt: cfg.TailstormAt, ReleaseNoneMinAge: cfg.ReleaseNoneMinAge,
		ReleaseConflictDepth: cfg.ReleaseConflictDepth,
	}, db, node, logger)
	if err != nil {
		return err
	}
	if cfg.PassphraseFile != "" {
		raw, err := nexa.ReadPrivateFile(cfg.PassphraseFile)
		if err != nil {
			return err
		}
		svc.SetPassphrase(string(raw))
	}
	if *id == 0 {
		rows, err := svc.Reviews()
		if err != nil {
			return err
		}
		if len(rows) == 0 {
			fmt.Println("no review rows")
			return nil
		}
		for _, p := range rows {
			fmt.Printf("id=%d address=%s amount=%s key=%s txid=%s txidem=%s\n",
				p.ID, p.Address, nexa.FormatNEX(p.Amount), p.Key, p.TxID, p.TxIdem)
		}
		return nil
	}
	if *action == "" {
		rows, err := svc.Reviews()
		if err != nil {
			return err
		}
		for _, p := range rows {
			if p.ID != *id {
				continue
			}
			fmt.Printf("id=%d address=%s amount=%s key=%s txid=%s txidem=%s\n",
				p.ID, p.Address, nexa.FormatNEX(p.Amount), p.Key, p.TxID, p.TxIdem)
			fmt.Println("resolve with -resolve complete, or -resolve release -confirm <txidem|none>")
			fmt.Println("-confirm <txidem> is accepted only when it is the stored txidem and a different txidem has spent an input with at least release_conflict_depth confirmations")
			fmt.Println("-confirm none is accepted only when the row was never signed and the reservation is at least release_none_min_age old")
			return nil
		}
		return fmt.Errorf("payout %d is not in review", *id)
	}
	if *action == "release" && strings.TrimSpace(*confirm) == "" {
		return fmt.Errorf("release requires -confirm with the stored txidem, or -confirm none when the row was never signed")
	}
	unlock, err := db.LockPayouts()
	if err != nil {
		return err
	}
	defer unlock()
	if err := svc.ResolveReview(*id, *action, *confirm); err != nil {
		return err
	}
	if *action == "release" {
		fmt.Printf("payout %d released; coins returned to the payable balance\n", *id)
		return nil
	}
	fmt.Printf("payout %d marked sent\n", *id)
	return nil
}

// refuseUnlocked stops startup when reserved outpoints cannot be locked.
// lockunspent is memory only; listening without it lets a second payout
// select the same coins.
func refuseUnlocked(err error) error {
	if err != nil {
		return fmt.Errorf("lockunspent failed: %w", err)
	}
	return nil
}

func inputsCommand(_ *log.Logger, args []string) error {
	fs := flag.NewFlagSet("inputs", flag.ContinueOnError)
	path := fs.String("config", "/etc/nexapool/nexapool.toml", "path to the TOML configuration")
	prune := fs.Bool("prune", false, "delete payout_inputs rows that are not held by a reserved, review, or sent payout")
	fs.SetOutput(os.Stderr)
	if err := fs.Parse(args); err != nil {
		return err
	}
	cfg, err := config.Load(*path)
	if err != nil {
		return err
	}
	db, err := store.Open(cfg.Database)
	if err != nil {
		return err
	}
	defer db.Close()
	unlock, err := db.LockPayouts()
	if err != nil {
		return err
	}
	defer unlock()
	rows, err := db.OrphanedInputs()
	if err != nil {
		return err
	}
	if !*prune {
		if len(rows) == 0 {
			fmt.Println("no orphaned payout_inputs")
			return nil
		}
		for _, row := range rows {
			status := row.Status
			if status == "" {
				status = "missing"
			}
			fmt.Printf("payout_id=%d outpoint=%s status=%s\n", row.PayoutID, row.Outpoint, status)
		}
		fmt.Printf("%d orphaned payout_inputs; rerun with -prune to delete them\n", len(rows))
		return nil
	}
	n, err := db.PruneOrphanedInputs()
	if err != nil {
		return err
	}
	fmt.Printf("pruned %d orphaned payout_inputs\n", n)
	return nil
}

func commentCommand(logger *log.Logger, args []string) error {
	fs := flag.NewFlagSet("comment", flag.ContinueOnError)
	path := fs.String("config", "/etc/nexapool/nexapool.toml", "path to the TOML configuration")
	text := fs.String("text", "", "wallet comment to look up")
	fs.SetOutput(os.Stderr)
	if err := fs.Parse(args); err != nil {
		return err
	}
	if strings.TrimSpace(*text) == "" {
		return fmt.Errorf("comment requires -text")
	}
	fmt.Println("comment search is informational only; it does not pay, reserve, or release")
	cfg, err := config.Load(*path)
	if err != nil {
		return err
	}
	node, err := nexa.NewClient(cfg.NodeURL, cfg.RPCUser, cfg.RPCPassword, cfg.CookieFile)
	if err != nil {
		return err
	}
	node.Log = logger
	pay, found, err := node.FindComment(*text)
	if err != nil {
		return err
	}
	if !found {
		fmt.Println("not found")
		return nil
	}
	fmt.Printf("txid=%s txidem=%s confirmations=%d\n", pay.TxID, pay.TxIdem, pay.Confirmations)
	return nil
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
