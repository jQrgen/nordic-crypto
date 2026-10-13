# Threat model

The pool pays real NEX from a hot wallet. The things that can go wrong are a stolen RPC credential, a forged share, a double payment, and a public page that invents numbers. This note is the model those controls are written against, and the record of the security review of draft PR #136.

## What the pool trusts

- A hot-wallet nexad on the same machine, reached only at `127.0.0.1`. The pool does not open the RPC port and refuses any node URL that is not loopback.
- That hot wallet, and not the cold wallet under `/var/lib/nexa`. The process runs as `nexapool`. `hot_wallet_max` stops a payout pass when the balance is above the cap.
- The operator who sets `fee_address` and `coinbase_address`. An empty or invalid fee address stops the process before it listens. Block reward is only the coinbase output that pays `coinbase_address`.
- SQLite on the local disk as the only ledger. One process holds the payout lock.

## Credentials

The RPC password is not in the repository. The client reads the hot wallet cookie, or `NEXAPOOL_RPC_USER` and `NEXAPOOL_RPC_PASSWORD` from the environment. A wallet passphrase, if the wallet is encrypted, is a separate file outside the repository. Both files must be regular files, mode `0600` or tighter. A symlink or a group-readable file is refused. The process never writes either secret to the log. The RPC client refuses HTTP redirects, so the cookie cannot follow a redirect off the box.

Anyone who can call `sendtoaddress` on the hot wallet can empty it, up to whatever balance was left there. Keep port 7227 on localhost. Keep the API on `127.0.0.1` and let nginx be the only public HTTP listener. Do not open nexad's P2P port 7228.

## Shares

A share is accepted only after NexaPow matches the published echelon construction, including the Bitcoin Cash Schnorr step, and the digest is at or below the miner's share target. The test vectors from the echelon specification are checked in `internal/nexa`. A repeated job-and-nonce, or a repeated proof hash, is a duplicate and is not paid twice. A share for an unknown job is stale. `clean: true` drops every previous job id. The solution nonce must be 1 to 16 bytes and must carry the session extranonce.

The username is the payout address. Anyone can mine to any valid address. That is the pool's account model: knowing an address lets you add hashrate to it, and it does not let you withdraw it.

Variable difficulty starts at 0.2 and will not fall below 0.05. `mining.suggest_difficulty` is ignored until authorize and cannot lower the session below its current difficulty. One IP can hold 16 connections, not the whole listener. Submits are rate limited. A run of bad shares bans the address. A client that does not read is disconnected so it cannot stall the job broadcast. Maturity reads the PPLNS window backwards and stops when the window is full.

## Blocks, reorgs, and maturity

A share that also meets the network target is submitted with `submitminingsolution`. The coinbase is credited only after `getblock` reports at least 5001 confirmations. That is `COINBASE_MATURITY + 1`, the depth at which nexad's wallet will spend the coinbase. Until then the credit is immature and `Payable` ignores it. A `getblock` error, including "Block not found on disk", is retried on the next pass. Negative confirmations orphan the block. A block that has already matured is not reversed.

## Payouts

A payout is inserted as `reserved` in the same transaction that checks the mature balance, and that transaction is `BEGIN IMMEDIATE`. Reserved, review, and sent rows all reduce what is still payable. The wallet comment is `nexapool:` plus 16 random bytes, written on that row before `sendtoaddress`.

`sendtoaddress` returns the transaction idem. The pool resolves it with `gettransaction` and stores the txid (`GetId`) on every path. A restart looks the row up by that id, then by comment, using `listtransactionsfrom` paged to the end of the wallet. There is no 200-row window. A row that already existed at the start of the pass is never sent again. If the lookup itself fails, the row stays `reserved` and is checked again next pass. If the search finishes and the send is absent, the row moves to `review` and stays deducted until an operator has checked the hot wallet. A payout is marked sent only after `payout_confirmations` (default 1).

A definite wallet error on the first send marks the payout failed and returns the coins. A timeout or a dropped connection leaves the reservation in place.

The fee is one percent, floored. Rounding dust from the miner split is added to the fee so the credits sum to the coinbase output and no miner is paid more than their work.

To return coins from a `review` row, confirm the hot wallet has no send with that comment, then set the row to `failed`. Doing that while a send exists pays the same coins twice.

## Tailstorm

Hard Fork 2 activates at unix time 1793495471, 2026-11-01 01:11:11 UTC. Before that, `mining.notify` is the echelon five-tuple and a zero previous hash is the pre-fork hash. At and after that time the notify gains `previousBlockHash` (display order, the same hex as `getminingcandidate`) and the pool rejects a candidate that does not carry a real parent. Miners that still hash the old way will produce shares this pool rejects.

## The public site and API

The API is read-only. It returns addresses, shares, balances, and payouts. It does not return idempotency keys, the cookie, or the passphrase. When the node is down, hashrate, miner count, network hashrate, and pool share are JSON null. Queries use bound parameters. Address lookup rejects anything that is not a mainnet Nexa cashaddr with a valid polymod.

nginx rate-limits `/api/` and sends HSTS, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and a Content-Security-Policy. TLS is 1.2 and 1.3.

## Review findings

Reviewed against commit `0ac9ba466`. The fixes are on `cursor/nexa-pool-4f40`.

| Severity | Where | Finding | Fix |
| --- | --- | --- | --- |
| Critical | `rpc.go` `FindComment`, `account/payout.go` `finish` | A crashed payout was sent again once its comment left the newest 200 wallet rows. `sendtoaddress` stored the idem while reconcile stored `GetId`. | The reserved row is written before the send. Restarts reconcile with `gettransaction` and `listtransactionsfrom` paged to the end of the wallet, store `GetId` on both paths, and never send a pre-existing row. A finished search that misses the send moves the row to `review`. `TestBlindReconcileSendsTheReservedPayoutAgain` asserts there is no second send. |
| High | `stratum/server.go` | One IP could hold every session. No submit limit, no ban, a 15 minute read deadline, `suggest_difficulty` before authorize could pin the floor, and a slow client stalled `SetJob`. `SharesBefore` loaded the whole share table. | 16 sessions per IP, a submit token bucket, bans after repeated bad shares, a 60 second read deadline, suggest ignored until authorize and never below the current difficulty, per-session writes that drop a stalled client, and a backward PPLNS window that stops when it is full. |
| High | `go.mod`, `rpc.go` `Call` | Go 1.22, and the RPC client followed redirects with the cookie in Basic auth (`GO-2025-3751`, `GO-2025-3420`, plus other stdlib findings). | `go 1.27.2` / `toolchain go1.27.2`. `CheckRedirect` refuses redirects. |
| High | `stratum/server.go` `notify`, Tailstorm time 1793495471 | `mining.notify` never carried `previousBlockHash`, so miners could not build the post-fork digest. | Before the activation time the notify stays the echelon five-tuple. At and after it, `previousBlockHash` is appended and a zero parent is rejected. Tests cover one second before and the activation instant. |
| Medium | `service.go` `publish` | `clean: true` still paid the previous 32 jobs. | A clean job replaces the job map. Older ids are stale. |
| Medium | `service.go` `MatureOnce` | `getblock` "not found" orphaned a block forever, including nexad's "Block not found on disk". | That error is retried. Only negative confirmations orphan. |
| Medium | maturity default 5000 | The wallet spends a coinbase at `coinbaseMaturity + 1` (5001). | Default maturity is 5001. |
| Medium | `rpc.go` `GetBlock` | Every coinbase output was credited. | Only outputs paying `coinbase_address` count. |
| Medium | `MarkSent` | A payout was marked sent with zero confirmations. | `payout_confirmations` (default 1) is required before `sent`. |
| Medium | `store.go` | No process lock and no `BEGIN IMMEDIATE`, so a second process failed busy or could race. | `_txlock=immediate` and an exclusive flock around `PayOnce`. |
| Medium | `config.go` | `node.url` and the API bind could be public. | Both must be loopback or the process will not start. |
| Medium | `deploy/nginx-pool.nordiccrypto.no.conf` | No rate limit and no security headers. | `limit_req`, HSTS, nosniff, frame denial, referrer policy, CSP, TLS 1.2+. |
| Medium | `deploy/nexapool.service`, cookie and passphrase reads | The unit ran as `nexa` and could spend the whole node wallet. Cookie and passphrase modes were not checked. | Unit user is `nexapool`, with the sandbox flags from the review. `hot_wallet_max` refuses an oversized balance. Secret files must be mode `0600` regular files. |
| Low | `address.go` | `staticcheck` reported an ignored `HasPrefix`. | The dead check was removed. |
| Low | `payout_test.go` | Dead assignment. | Removed. |
| Low | `server.go` extranonce | `rand.Read`'s error was ignored and two sessions were not checked for a collision. | A failed read closes the connection. Live extranonces are unique. |
| Low | `README.md` | Firewall text omitted P2P port 7228. | 7228 stays closed; outbound peering does not need it open. |
| Accepted | submit timestamp | The submitted time is checked for being non-empty. It is not an input to NexaPow. | Unchanged. It does not weaken a share. |

## What this does not defend against

A miner with a lot of hashrate can take a large part of the PPLNS window. That is how the window works. A person who can spend the hot wallet can take its balance, which is why the balance is capped and the cold wallet is a different account. The pool is not a second custody layer on top of the node.
