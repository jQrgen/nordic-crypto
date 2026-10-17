# Threat model

The pool pays real NEX from a hot wallet. The things that can go wrong are a stolen RPC credential, a forged share, a double payment, and a public page that invents numbers. This note is the model those controls are written against, and the record of the security review of draft PR #136.

## What the pool trusts

- A hot-wallet nexad on the same machine, reached only at `127.0.0.1`. The pool does not open the RPC port and refuses any node URL that is not loopback.
- That hot wallet, and not the cold wallet under `/var/lib/nexa`. The process runs as `nexapool`. `hot_wallet_max` stops new sends when the balance is above the cap. In-flight rows are still reconciled.
- The operator who sets `fee_address` and `coinbase_address`. An empty or invalid fee address or coinbase address stops the process before it listens. Block reward is only the coinbase output that pays `coinbase_address`.
- SQLite on the local disk as the only ledger. One process holds the payout lock.

## Credentials

The RPC password is not in the repository. The client reads the hot wallet cookie, or `NEXAPOOL_RPC_USER` and `NEXAPOOL_RPC_PASSWORD` from the environment. A wallet passphrase, if the wallet is encrypted, is a separate file outside the repository. Both files must be regular files, mode `0600` or tighter. A symlink or a group-readable file is refused. The process never writes either secret to the log. The RPC client refuses HTTP redirects, so the cookie cannot follow a redirect off the box.

Anyone who can call `sendtoaddress` on the hot wallet can empty it, up to whatever balance was left there. Keep port 7227 on localhost. Keep the API on `127.0.0.1` and let nginx be the only public HTTP listener. Do not open nexad's P2P port 7228.

## Shares

A share is accepted only after NexaPow matches the published echelon construction, including the Bitcoin Cash Schnorr step, and the digest is at or below the miner's share target. The test vectors from the echelon specification are checked in `internal/nexa`. A repeated job-and-nonce, or a repeated proof hash, is a duplicate and is not paid twice. A share for an unknown job is stale. `clean: true` drops every previous job id. The solution nonce must be 1 to 16 bytes and must carry the session extranonce.

The username is the payout address. Anyone can mine to any valid address. That is the pool's account model: knowing an address lets you add hashrate to it, and it does not let you withdraw it.

Variable difficulty starts at 0.2 and will not fall below 0.05. For the first three minutes it retargets every 10 seconds, then it waits a minute. `mining.suggest_difficulty` is ignored until authorize and cannot lower the session below its current difficulty. One IP can hold 16 connections, not the whole listener. Submits are rate limited at `submit_rate` (default 128 per second, about 110 GH/s at the start difficulty). Rate-limit misses during `submit_grace` do not ban, so a faster miner can climb before the ban applies. A run of bad shares still bans the address. A client that does not read is disconnected so it cannot stall the job broadcast. The submitted ntime must match the job. Maturity reads the PPLNS window backwards and stops when the window is full. Shares older than 14 days are pruned even while a block is still immature.

## Blocks, reorgs, and maturity

A share that also meets the network target is submitted with `submitminingsolution`. The coinbase is credited only after `getblock` reports at least 5001 confirmations. That is `COINBASE_MATURITY + 1`, the depth at which nexad's wallet will spend the coinbase. Until then the credit is immature and `Payable` ignores it. A `getblock` error, including "Block not found on disk", is retried on the next pass. Negative confirmations orphan the block. A block that has already matured is not reversed.

## Payouts

A payout selects its own inputs, skipping every outpoint still stored on a reserved, review, or sent row, and builds the transaction with `createrawtransaction` from those explicit inputs. `fundrawtransaction` is called with the hex only. Its second argument is `includeWatching`, not a coin lock, so it is not passed. The funded inputs are locked with `lockunspent false` before `signrawtransaction`, and the same outpoints are inserted in the reservation's database transaction. `signrawtransaction` returns the txid (`GetId`) and the txidem (`GetIdem`). The txidem is the identifier. The txid is informational and can change if the satisfier scripts change. Both, the signed raw hex, and the input outpoints are inserted on the `reserved` row in the same `BEGIN IMMEDIATE` transaction that checks the mature balance. Only then does the pool call `sendrawtransaction`. The id that call returns is not stored. Reserved, review, and sent rows all reduce what is still payable. At startup, and again at the start of each payout pass, every unresolved outpoint is locked again, because `lockunspent` is memory only.

Every lookup uses the stored txidem: `gettransaction`, then `gettxpoolentry`, then `getrawtransaction`. The txid is not a lookup key. A result with one or more confirmations is this payment, whatever txid the wallet reports for that txidem. The stored hex is broadcast again whenever that txidem is absent or its confirmation count is 0. Depth 0 is not kept back by wallet flags: `abandontransaction` only removes the transaction from this node's mempool and leaves the wallet entry at 0 confirmations, so the same hex has to be sent again or the payout stays stuck. A row that already has a txidem is never given a new transaction. A row with no txidem was never signed: it moves to `review` and is not signed. If a lookup fails, the row stays where it is and is checked again. A broadcast error, including a timeout, leaves the reserved row and its signed hex in place. `gettransaction` has no abandoned field, and the pool does not read one. The process exits at startup if `lockunspent` fails, and it does not listen while those coins are unlocked.

`nexapool review` lists `review` rows. `-resolve complete` marks one sent when that stored txidem is in the wallet or in a block and has `payout_confirmations` (default 1). `-resolve release -confirm <txidem>` returns the coins only when `<txidem>` is the stored txidem and a different txidem has spent one of its inputs with at least `release_conflict_depth` confirmations (default 10, minimum 6). `-confirm none` is only for a row that was never signed, and only once the reservation is at least `release_none_min_age` old (default 24 hours). Each later pass rechecks sent rows and rebroadcasts the stored hex until that deep spend exists. A shallower conflict, a missing UTXO, and `abandontransaction` do not drop the row and do not sign another transaction. Inputs stay locked until the stored txidem itself reaches `release_conflict_depth`, or until that deep spend releases the row.

Wallet comments are not part of this decision. Accounting entries from `move`, including entries reloaded at startup, are in `wtxOrdered` and not in `mapWallet`, so `getwalletinfo.txcount*3` is not an upper bound and a comment scan can miss a payout that was sent. `nexapool comment -text` still walks `listtransactionsfrom` and prints what it finds. That command does not pay, reserve, or release. The idempotency key on the row is `nexapool:` plus 16 random bytes. It is not how a payout is found.

The fee is one percent, floored. Rounding dust from the miner split is added to the fee so the credits sum to the coinbase output and no miner is paid more than their work.

To return coins from a signed payout, run `nexapool review -id N -resolve release -confirm <txidem>` only after a different txidem has spent one of its inputs and that spend has at least `release_conflict_depth` confirmations. Use `-confirm none` only when the row has no txidem and the reservation is old enough. Release refuses a txidem that is still live, a confirmation that does not match the stored txidem, a competing spend below that depth, and `none` on a row that was signed or is younger than `release_none_min_age`. `abandontransaction` only drops the transaction from this node's mempool. It is not a release. Doing it by hand in the database while the signed transaction can still confirm pays the same coins twice.

A reorg deeper than `release_conflict_depth` is an accepted risk. After a competing spend reaches that depth the pool unlocks the inputs and may sign a new payout. If that spend is later reorganised out, the stored transaction and the new one can both be valid. Raising `release_conflict_depth` reduces how often that happens. It does not remove the possibility. The default of 10 is the operating choice.

`nexapool inputs` lists `payout_inputs` rows whose payout is missing or no longer reserved, in review, or sent. `nexapool inputs -prune` deletes those rows so a freed outpoint can be reserved again. It does not delete inputs of a payout that is still held, and it does not pay or release.

## Tailstorm

Tailstorm follows the node. `getminingcandidate` leaves `previousBlockHash` as 64 zero bytes until the node enables it, and the pool publishes the echelon five-tuple while that field is zero. A real parent is appended to `mining.notify` and mixed into the share hash. `tailstorm = on` requires a parent and `tailstorm = off` ignores one. `tailstorm_activation`, when set, is compared with the node's median time past from `getblockchaininfo`, not with the wall clock. Miners that still hash the old way will produce shares this pool rejects once the parent is on the wire.

## The public site and API

The API is read-only. It returns addresses, shares, balances, and payouts. It does not return idempotency keys, the cookie, or the passphrase. When the node is down, hashrate, miner count, network hashrate, and pool share are JSON null. Queries use bound parameters. Address lookup rejects anything that is not a mainnet Nexa cashaddr with a valid polymod.

nginx rate-limits `/api/` and sends HSTS, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and a Content-Security-Policy that does not allow inline scripts. Translations are `pool-text.js`. TLS is 1.2 and 1.3.

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
| High | `rpc.go` `findComment`, `payout.go` | `listtransactionsfrom` advanced `from` by JSON rows. nexad counts wallet items, so a crash between send and `NotePayment` stuck the payout in `review` once the wallet was longer than one page. Nothing but a database edit could release it. | Page by the requested wallet-item count. `nexapool review` completes a row when the wallet has the transaction. |
| High | `fork.go`, `service.go` `publish` | Tailstorm flipped on the wall clock 2026-11-01 01:11:11 UTC. nexad activates by median time and emits a parent only when Tailstorm is enabled, so the pool would stop publishing jobs. | The mining candidate's previous hash decides. `tailstorm = on` or `off` forces it. `tailstorm_activation` is compared with the node's median time, not the wall clock. |
| High | `rpc.go` `GetBlock`, empty `coinbase_address` | An empty pool address matched no coinbase output, so a block never matured. | `coinbase_address` is required at startup. `GetBlock` refuses to count a reward without it. |
| High | `server.go` submit cap, `vardiff.go` | 4 submits/s and a ban after 20 misses banned a miner above about 3.4 GH/s before variable difficulty could move. The limits were not in the config. | `submit_rate`, `submit_burst`, `ban_after`, and `submit_grace` are configurable. Defaults are 128/s, burst 256, and a 3 minute grace. During the grace, rate-limit misses do not ban and variable difficulty retargets every 10 seconds. |
| Low | `payout.go` `settle` | A payout marked sent at one confirmation was not revisited if that transaction later dropped. | Each pass rechecks sent rows. A transaction that leaves the wallet is broadcast again from the stored hex. |
| Low | `config.go` maturity | A positive maturity below 5001 was accepted. | Values below 5001 are rejected. Unset still defaults to 5001. |
| Low | `service.go` `MatureOnce` | The 14-day share prune did not run while any block was immature. | The time prune runs on every pass. A filled window's shares are kept. |
| Low | `service.go` `PayOnce` | A hot wallet over the cap skipped reconciliation until it was swept. | In-flight rows are reconciled. New sends wait until the balance is under the cap. |
| Low | `server.go` submit time | The submitted ntime was not compared with the job. | The ntime must decode and must match the job's timestamp. |
| Low | nginx CSP | `script-src` allowed `'unsafe-inline'`. | The policy has no `'unsafe-inline'`. Translations load from `pool-text.js`. |
| High | `rpc.go` `findComment`, `payout.go` `ResolveReview` | `getwalletinfo.txcount` is `mapWallet.size()/3`, not the length of `wtxOrdered`. The scan stopped at that count, including when it was 0, and `release` treated the miss as proof the send was absent. The next pass paid the coins again. | `txcount` is not the stop index. `release` requires a finished scan and `-confirm` naming the row's txid, or `none` when the row has no txid. |
| High | `rpc.go` `findComment`, `payout.go` `ResolveReview` | A short JSON page ended the scan. A change-only debit or a conflicted receive emits no row, so a full item page can return fewer than 1000 rows while later items still exist. `release -confirm none` then paid the crashed send again. | A short page does not end the scan. It stops only after two consecutive empty pages, and only once `from` is past `txcount*3` plus a margin. A missing bound is an unfinished search. The final `from` is logged. `-confirm none` also requires the reservation to be at least `release_none_min_age` old (default 24 hours). |
| High | `rpc.go` `findComment`, `payout.go` `ResolveReview` | Accounting entries from `move`, and the same entries reloaded at startup, are in `wtxOrdered` but not in `mapWallet`. No `txcount` bound covers them, so two empty pages can finish the scan before the payout comment. `release -confirm none` then pays the coins again. | The payout is signed before `sendrawtransaction`. The txidem and raw hex are stored in the reservation transaction. Recovery rebroadcasts that same hex. The comment scan is not used to pay or release. |
| High | `payout.go` `LookupTx`, `rpc.go` `CreatePayout` | A conflicted or abandoned row was dropped and the next pass signed a new transaction. `gettransaction` was keyed by txid first, so a conflicted stored txid hid the confirmed txidem. `fundrawtransaction`'s second argument does not lock coins, `lockunspent` is memory only, and `gettransaction` has no abandoned field. | Lookups use the txidem only. A confirmed txidem is paid whatever its txid is. Abandon is not a release. Coins return only when a different txidem has spent an input at `release_conflict_depth` (default 10, minimum 6). Until then the stored hex is rebroadcast and no second transaction is signed. Reserved outpoints are stored with the reservation, locked after funding and again at startup, and skipped by coin selection. |

## What this does not defend against

A miner with a lot of hashrate can take a large part of the PPLNS window. That is how the window works. A person who can spend the hot wallet can take its balance, which is why the balance is capped and the cold wallet is a different account. The pool is not a second custody layer on top of the node.
