# Security review of draft PR #136

Reviewed commit `0ac9ba466` (`cursor/nexa-pool-4f40`) against nexad `dev` (`GetMiningHash` in `src/primitives/block.cpp`, `CheckProofOfWork` in `src/pow.cpp`, `submitminingsolution` in `src/unlimited.cpp`, `sendtoaddress` / `listtransactions` in `src/wallet/rpcwallet.cpp`). This file is the review only. Nothing here was pushed onto the PR branch.

**Verdict: not ready.**

The share checker matches nexad for today's pre-Tailstorm NexaPow, and it does not trust a client-reported difficulty. The launch blockers are a payout path that can send the same coins twice, a public stratum listener that one host can pin and fill, a Go 1.22 build that still leaks the RPC password on redirect, and a Tailstorm cutover on 1 November 2026 that miners cannot follow because the job notification never carries the parent hash.

## Blockers

### 1. A crashed payout is sent again once the comment leaves the last 200 wallet rows

Severity: **critical**. `pool/internal/nexa/rpc.go:234`, `pool/internal/account/payout.go:109`.

`RunPayouts` reserves a row, then calls `sendtoaddress` with comment `nexapool:` plus 16 random bytes. If the process dies after nexad accepts the transaction and before `MarkSent`, the next pass is supposed to find that comment and record the txid. `FindComment` only requests `listtransactions "*" 200 0`. nexad returns the 200 newest wallet entries (a send is one entry per output, and coinbase credits count too). A comment older than that window is invisible, `FindComment` returns not found, and `finish` calls `Send` again on the still-reserved row.

`TestFindCommentMissesACommentOutsideTheLatest200` shows the client never asks past 200 rows. `TestBlindReconcileSendsTheReservedPayoutAgain` shows the second pass transmits the payout again. `pool/SECURITY.md` describes this reconcile path as if the comment were always found. It is not.

The happy path also stores the wrong identifier. nexad `sendtoaddress` returns `wtx.GetIdem()` (`src/wallet/rpcwallet.cpp`), and `SendToAddress` (`pool/internal/nexa/rpc.go:214`) saves that string as the txid. The reconcile path stores `listtransactions`' `txid` field, which is `GetId()`. Explorers and a later audit will not agree which id was paid.

### 2. Stratum on :3333 can be pinned by one IP

Severity: **high**. `pool/internal/stratum/server.go:167`, `pool/internal/stratum/server.go:214`, `pool/internal/stratum/server.go:249`, `pool/internal/stratum/server.go:383`, `pool/internal/pool/service.go:324`, `pool/internal/store/store.go:166`.

What is in place: a 64 KiB line cap (`server.go:216`, covered by `TestOversizedLineIsDropped`), a 15 minute read deadline, a global cap of 4096 sessions, and malformed JSON that does not drop the connection (`TestMalformedJSONDoesNotDropTheSession`).

What is not:

- No per-address connection limit. One IP can hold all 4096 sessions.
- The read deadline refreshes only after a full line, so a slow drip holds a slot for 15 minutes. There is no ban list.
- `mining.submit` has no rate limit. Every submit runs NexaPow, including a Schnorr signature, and a rejected proof still inserts into `rejects`.
- `mining.suggest_difficulty` is honored before authorize and clamps only to the configured floor (0.05). Calling it again pins the session there, so variable difficulty never stays up. `TestSuggestDifficultyPinsTheFloor` covers that. Each accepted share is a row. The floor stops a zero-difficulty flood; it does not stop a flood.
- `SetJob` writes to every session on the caller goroutine with no write deadline (`server.go:144` and `server.go:427`). A client that does not read stalls the next job for everyone else.
- `SharesBefore` loads every share ever stored, on every maturity pass, for every immature block (`service.go:324`). The table is never pruned. Filling it from :3333 grows both disk and the maturity pass without bound.

Variable difficulty itself does not mint extra payout. Credit is the session difficulty in micros, and a share must fall at or under `ShareTarget` of that value. Lowering difficulty makes more rows, not more money. The damage is the database and the CPU.

### 3. Do not ship a binary built with Go 1.22

Severity: **high**. `pool/go.mod:3`, `pool/internal/nexa/rpc.go:63`, `pool/README.md:73`.

`go vet ./...` is clean. `govulncheck ./...` against the Go 1.22.2 toolchain in this environment reports 55 standard-library issues and no third-party module advisories. The ones that touch this process:

- `GO-2025-3751` and `GO-2025-3420`: `net/http` can keep `Authorization` across a cross-origin redirect. `Client.Call` uses the default client, which follows redirects, and puts the RPC cookie in Basic auth (`rpc.go:95`). A redirect from the configured URL sends the cookie off-box. `CheckRedirect` should refuse redirects, and the binary needs a toolchain where those two advisories are fixed (Go 1.23 is not new enough for `GO-2025-3751`).
- `GO-2025-3849`: `database/sql` `Rows.Scan` can return wrong values. The trace includes `MarkSent` (`store.go:461`).
- Several `net/http` server advisories (HTTP/2 window and header parsing) apply to `ListenAndServe` in `cmd/nexapool/main.go:100`. The sample binds the API to localhost, which limits who can hit them, and does not remove them from the binary.

`staticcheck ./...` reports two existing nits, neither of which is a payout bug: ignored `HasPrefix` in `internal/nexa/address.go:37`, and a dead assignment in `internal/store/payout_test.go:177`.

### 4. After 1 November 2026 miners cannot produce a share this pool will accept

Severity: **high**. Activation `1793495471` is 2026-11-01 01:11:11 UTC. `pool/internal/nexa/pow.go:50`, `pool/internal/stratum/server.go:402`, `pool/SECURITY.md:49`.

Until Tailstorm, `previousBlockHash` is 64 zero bytes and both sides use the pre-fork hash. That part matches nexad. After the fork, nexad puts the real parent in the candidate and `CheckProofOfWork` signs `SHA256(SHA256(miningHash || parent))`. The pool does the same mix, and it reverses the display-order parent the way `nexa-miner` does. `mining.notify` still sends only job id, header commitment, nBits, an 8-byte timestamp, and the clean flag. The parent hash is never on the wire, so a miner cannot compute the post-fork digest. Shares hashed the old way fail the new check. The pool will stop paying work on the fork day, and it will not submit those shares as blocks.

## Share and block validation

Pre-Tailstorm NexaPow matches nexad and the echelon full-hashing vectors.

| Step | nexad | pool |
| --- | --- | --- |
| Header commitment | `getminingcandidate` returns `GetMiningHeaderCommitment().GetHex()` (display order). `GetMiningHash` writes the internal 32 bytes. | `PowHash` reverses the hex before hashing (`pow.go:40`). |
| Nonce | `CHashWriter << uint256 << vector`: one-byte compact size for length 1..16, then the raw nonce bytes. Max 16 (`MAX_NONCE_SIZE`). | Length byte plus nonce (`pow.go:41`). `submitminingsolution` does `ParseHex` into that vector; the pool sends `hex.EncodeToString` of the same bytes (`service.go:267`). |
| Digest | Internal SHA-256 output, compared with `UintToArith256` (little-endian integer). Fail when `hash > target`. | Reversed to display order, then `big.Int.SetBytes`. `Meets` is `<=` (`target.go:58`). |
| nBits | `arith_uint256::SetCompact`. Negative and overflow targets fail. | `CompactToTarget` rejects the sign bit, a zero mantissa, and a target wider than 256 bits (`target.go:25`). |
| Tailstorm mix | `CSHA256Writer` is a single SHA-256. `h1 = SHA256(SHA256(internal mining hash \|\| internal parent))`. A null parent skips it. | Same two single SHA-256s, parent reversed from display hex (`pow.go:50`). An all-zero parent is treated as null. |

`TestPowHashOfficialVectors` locks both published final digests, including the Schnorr step. `TestCraftedShareCountedOnlyUnderShareTarget` accepts the vector under a tiny share target and rejects it at difficulty 1, and it does not call `submitminingsolution` when nBits is `1d00ffff`. `TestCraftedBlockUsesCandidateTargetNotClientDifficulty` submits candidate id `9` and the raw nonce only when nBits is `207fffff`. There is no difficulty field in that RPC.

Duplicates: `UNIQUE(job_id, nonce)` and `UNIQUE(pow_hash)` (`store.go:97`). A second job with the same commitment and nonce is rejected (`TestReplayAcrossJobsWithTheSameCommitmentIsDuplicate`). An unknown job is code 21.

Extranonce: 8 random bytes per connection (`server.go:200`). A 16-byte nonce that does not start with this session's extranonce is rejected; a shorter counter is prefixed with it (`TestCraftedNonceMustCarryThisConnectionExtranonce`). `rand.Read`'s error is ignored (`server.go:201`). Two live sessions are not checked for a collision. At 8 bytes that collision is not a practical replay, and the pow-hash unique index would still refuse a repeated proof.

The submitted timestamp is checked only for being non-empty (`server.go:331`). The hash does not include it. The notify timestamp is `time.Now()` (`service.go:197`), not a field nexad currently returns (the candidate's `time` is compiled out of `MkMiningCandidateJson`). That does not let a miner weaken the block.

Stale work is only half handled. Jobs older than 32 are dropped (`service.go:203`, `TestJobOlderThanTheWindowIsStale`). A new candidate is announced with `clean: true`, but the previous job is still paid (`TestUnknownJobIsStaleAndStoredJobsSurviveCleanNotify`). Echelon says a clean job means prior job ids are rejected. A modified miner can keep submitting the previous 32 commitments. Those shares are real proofs of those commitments, credited at session difficulty, and a block is submitted only if that old job's own nBits still matches. nexad deletes the candidate id on submit and rejects an unknown id, so this is paid stale work, not a forged block.

## Payouts

What holds:

- The balance check and the `reserved` insert are one transaction (`store.go:413`). Reserved and sent rows both reduce `Payable`.
- A second sequential pass does not send again when the comment is still visible. The existing timeout test covers the crash where `FindComment` still sees the send.
- Eight overlapping `RunPayouts` produced one send. The others returned `SQLITE_BUSY` immediately (`TestConcurrentPayoutReservesTheBalanceOnce`). The 5 second `busy_timeout` in `store.go:62` did not absorb that contention. `cmd/nexapool/main.go:83` runs payouts on one goroutine, so a single process does not overlap itself. A second nexapool on the same database fails the extra run instead of waiting. There is no process lock and no `BEGIN IMMEDIATE`.
- Immature credits are not payable. `OrphanBlock` will not reverse a row already marked mature (`store.go:290`). At 5000 confirmations that matches the "past the checkpoint, do not claw back" note in `SECURITY.md`.
- Fee is `reward * percent / 100`, floored. Per-share dust is added to the fee and the credits must sum to the reward (`account/pplns.go:63`). A negative reward, a negative payout, and a uint64 work sum that wraps are refused (`TestSplitDoesNotPayWrappedWork`, `TestNegativePayoutIsNotSent`). A wrapped window would stick the block in `immature` rather than overpay. That stick happens if `int64(total)` overflows, which is above `2^63` micros, far past the configured max share difficulty of 4096.
- `PayOnce` will not reserve more than `getbalance - already reserved - tx_reserve` (`service.go:360`).

What does not:

- The reconcile window in blocker 1.
- One `getblock` error whose text contains "not found" or "no such" orphans an immature block forever (`service.go:300`, `service.go:410`). `TestOneMissingBlockReplyOrphansImmatureWork` shows a later successful `getblock` does not revive it. nexad uses "Block not found on disk" when the header is known and the body is not. Miners are never credited; the coins stay in the wallet.
- The pool marks mature at `confirmations >= 5000` (`service.go:317`). nexad's spend rule is `coinbaseMaturity + 1`, and mainnet `COINBASE_MATURITY` is 5000, so the wallet spends the coinbase at 5001. `getbalance` still refuses to pay coins the wallet cannot spend. The ledger is one confirmation early.
- `GetBlock` sums every coinbase vout (`rpc.go:195`), not the amount that landed on the pool address. A second paying output would be credited to miners and then paid from whatever else is in the wallet.
- A reserved payout that nexad accepted is marked sent without waiting for a confirmation. If that transaction is later dropped, the ledger still says paid.

Wallet boundary, which is the launch condition underneath the blockers:

- The unit runs as `nexa` (`deploy/nexapool.service:8`), the same user as nexad, and reads `/var/lib/nexa/.nexa/.cookie`. Anyone who gets this process gets `sendtoaddress` on the whole node wallet. There is no separate hot wallet and no cap other than the 1 NEX fee reserve.
- The cookie file mode is not checked (`rpc.go:49`). The passphrase file mode is not checked (`cmd/nexapool/main.go:49`). Neither value is written to the log by the code reviewed here. The API does not return the idempotency key (`store.go:340`, `api.go:173`).
- `node.url` is not required to be loopback (`config.go:158`). The example is `127.0.0.1:7227`. A non-local URL would send the cookie there, and the redirect bug above makes that worse.

## API

All six routes are `GET` and unauthenticated (`api.go:27`): `/api/v1/stats`, `/blocks`, `/miners`, `/address/{address}`, `/payouts`, `/health`. `POST` is 405 (`TestAPIIsReadOnlyAndHidesInternals`). There is no admin or write route. `web_root` is empty in the example, so the API process does not also serve the site.

Queries use placeholders. An address that is not a mainnet cashaddr with a valid polymod is rejected before it reaches SQL, including a quote-injection attempt. `limit` is capped at 100 (`api.go:139`). Failures return `{"error":"unavailable"}` and the detail goes to the log (`api.go:134`). Responses do not set `Access-Control-Allow-Origin`. Worker names and connection addresses are not in the JSON. Idempotency keys are not either.

The stats and miners queries sum the hashrate window. They are not the unbounded read. That read is `SharesBefore` on the maturity timer.

`config.go:157` defaults the API to `127.0.0.1:8080` and will happily bind `0.0.0.0` if the file says so.

## Deploy

systemd (`deploy/nexapool.service`): `User=nexa`, `NoNewPrivileges=true`, `ProtectSystem=strict`, `PrivateTmp=true`, `ProtectHome=true`, `ReadWritePaths=/var/lib/nexapool`. The cookie under `/var/lib/nexa` stays readable, which is what lets the pool see the wallet. Missing from the unit: `ProtectKernelTunables`, `ProtectKernelModules`, `ProtectControlGroups`, `PrivateDevices`, `RestrictAddressFamilies`, `RestrictSUIDSGID`, `LockPersonality`, `MemoryDenyWriteExecute`, `SystemCallFilter`, `CapabilityBoundingSet`, `UMask=0077`.

nginx (`deploy/nginx-pool.nordiccrypto.no.conf`): port 80 redirects to HTTPS, port 443 has a certificate path, `/api/` proxies to localhost. No `limit_req`, no HSTS, no `X-Content-Type-Options` / `X-Frame-Options` / `Referrer-Policy` / CSP, no explicit `ssl_protocols`. Stratum is correctly left off the proxy.

Firewall text in `pool/README.md:95` says open 80, 443, and 3333, and do not open 7227 or 8080. Port 80 is the ACME listener. It does not mention nexad's P2P port 7228. Outbound peering works with 7228 closed. RPC must stay on `127.0.0.1:7227` only; the pool does not check that nexad is bound that way.

Secrets: the RPC password is not in the tree. `deploy/nexapool.env.example` is empty. The passphrase path is outside the repo. The sample config tells the operator not to put either in the TOML file.

## Tests and tools

From `pool/`, on Go 1.22.2:

| Command | Result |
| --- | --- |
| `go test -race -count=1 ./...` | pass, including the crafted-share tests in `internal/pool/share_security_test.go`, `internal/stratum/security_test.go`, `internal/nexa/findcomment_test.go`, `internal/store/concurrent_payout_test.go` |
| `go vet ./...` | pass |
| `staticcheck ./...` | fail, two existing nits cited above |
| `govulncheck ./...` | fail, 55 standard-library findings on Go 1.22.2 |

## Before launch

1. Reconcile payouts with a key that cannot scroll out of view: persist the txid only after the send, and on restart search by that key with `listtransactionsfrom` or `gettransaction` until the row is resolved. Store nexad's txid, not the idem, in both paths.
2. Cap connections per IP, rate-limit `mining.submit`, stop honoring `mining.suggest_difficulty` below the vardiff result (or ignore it), set write deadlines, and stop loading the full share history on every maturity pass.
3. Build with a current Go, and refuse HTTP redirects on the RPC client.
4. Before 1 November 2026, put `previousBlockHash` on the job and confirm a Tailstorm-capable miner against the pool's mix.
5. Run the pool wallet as a hot wallet with a balance cap, on an account that is not the same login as the nexad datadir, and keep 7227 on localhost.

## Re-review at 1109d60b

Reviewed `1109d60b192d025129ad1378a41b130490debef8` on `cursor/nexa-pool-4f40` by reading the code. The finding table in `pool/SECURITY.md` was not used as evidence. nexad is `dev` at `37fe286` (`listtransactionsfrom` and `ListTransactions` in `src/wallet/rpcwallet.cpp`, `CheckProofOfWork` in `src/pow.cpp`, `MkMiningCandidateJson` in `src/unlimited.cpp`, `IsUpgrade2Activated` in `src/validation/forks.cpp`, `NEXT_FORK_ACTIVATION_TIME` in `src/chainparams.cpp`). Nothing in this file was pushed onto the PR branch.

**Verdict: not ready.**

The payout state machine no longer sends a reserved row a second time, the RPC client refuses redirects, `govulncheck` is clean on Go 1.27.2, and a clean job notification drops the previous job. Four launch blockers remain: comment recovery still does not walk the wallet, the Tailstorm gate does not match nexad and will stop work on 1 November 2026, an empty `coinbase_address` never credits a block, and the new submit cap bans a miner before variable difficulty can move.

### Blocker 1, double payout — the second send is closed, recovery is not

Severity of what remains: **high**. `pool/internal/nexa/rpc.go:347`, `pool/internal/account/payout.go:127`.

What the code does now, and the crash tests that lock it (`internal/account/crash_test.go`):

| Step | What happens | Test |
| --- | --- | --- |
| Reserve, then the process dies before `Send` | The next pass does not send. A completed miss moves the row to `review`. The coins stay deducted. | `TestCrashAfterReserveBeforeSendDoesNotSend` |
| `Send` returns, `NotePayment` never commits | The error propagates. The row stays `reserved` with empty ids. The next pass finds the comment and marks it sent with `TxID`, not the idem. One send. | `TestCrashAfterSendBeforeNoteDoesNotSendAgain` |
| `NotePayment` commits, `MarkSent` does not | The txid is durable. The next pass does not send. | `TestCrashAfterNoteBeforeMarkSentDoesNotSendAgain`, `TestCrashInsideMarkSentLeavesTheNoteAndDoesNotResend` |
| `Find` returns an error | The row stays `reserved`. No send, no review. | `TestFindErrorStaysReservedAndDoesNotSend` |
| `Find` finishes and the comment is absent | `review`. Not sent again. Still deducted from `Payable`. | `TestFindMissMovesToReviewAndDoesNotSend` |
| `sendtoaddress` succeeded and `gettransaction` did not | `SendHeld` stores the idem and does not send again. A later lookup by that idem marks `TxID`. | `TestSendHeldRecordsIdemAndDoesNotSendAgain` |
| Definite wallet rejection | `failed`, coins return, the next pass sends once. | `TestDefiniteSendFailureRetriesOnce` |
| Dropped connection, no id in the error | Stays `reserved` (the word `connection` is treated as ambiguous). A later find does not send again. | `TestAmbiguousSendWithoutIDStaysReserved` |
| Zero confirmations | Not marked sent. `minConfs` below 1 is raised to 1 (`payout.go:81`). | `TestZeroConfirmationsAreNotMarkedSent` |
| Already `sent` | `Reserved()` does not return it. | `TestSentRowIsNotSentAgain` |

`sendtoaddress` still returns `GetIdem`. `SendToAddress` (`rpc.go:269`) resolves it with `gettransaction`, which nexad accepts for either id (`mapWallet` stores both `GetId` and `GetIdem`). `MarkSent` writes `Payment.TxID` only (`payout.go:184`). A failed lookup after a successful send returns `SendHeld` (`rpc.go:278`) so the caller must not send again. `review` is included in the payable subtraction (`store.go:511`, `store.go:546`). That part of the original critical bug is closed.

The recovery scan is not. `findComment` (`rpc.go:347`) pages `listtransactionsfrom "*" 1000 from`. In nexad, `from` and `count` count `wtxOrdered` items (`rpcwallet.cpp` around the `std::advance(it, nFrom)` loop), and `ListTransactions` appends one JSON object per output. A normal send with change is two rows. The pool then does `from = from + len(txs)`. After the first page of 1000 wallet items that each emit two rows, `from` becomes 2000 and the next call skips the rest of the wallet. The newest comment — the one a crash just created — is the one that is skipped. A page that returns fewer JSON rows than wallet items is treated as the end, so one item that emits nothing stops the scan early.

`TestFindCommentMissesACommentPastTheFirstWalletPage` and `TestFindCommentStopsWhenAPageHasFewerJSONRowsThanItems` show both misses against a handler that implements nexad's item cursor. `TestCrashedPaymentMissedByPagingIsReviewedNotResent` is the crash after the send and before the note: the comment is in the wallet, `LookupPayment` reports a completed miss, the row goes to `review`, and nothing is sent again. There is no admin route to release or complete a `review` row. It stays held until a later `Find` succeeds, and this `Find` will not succeed while the wallet is longer than one mis-counted page. The coins are not paid twice. They are also not paid.

`TestFindCommentScansPastTheLatest200` in `rpc_test.go` does not catch this. Its fake server treats `from` as a JSON-row cursor, which is the same mistake as the client.

### Blocker 2, stratum — the caps landed, and the submit limit bans miners

Per-IP cap 16 (`server.go:114`, `server.go:224`), 60 second read deadline (`server.go:119`), authorize-before-suggest and no lowering (`server.go:534`), a writer goroutine with a 5 second deadline (`server.go:348`), and a non-blocking broadcast that drops a slow session (`server.go:625`) are in place. `ShareWindow` reads backwards in pages of 1024 and stops when the work target is filled (`store.go:221`). `TestShareWindowStopsAtTheTarget` covers that. `suggest_difficulty` before authorize no longer pins 0.05 (`TestSuggestDifficultyCannotLowerTheSession`). This closes the original pinning, stall, and full-table findings.

What it adds: `Listen` defaults `SubmitRate` to 4 per second, burst 8, and `BanAfter` to 20 (`server.go:120`). A rate-limit miss calls `penalise` (`server.go:477`), and 20 hits ban the IP for 10 minutes (`server.go:583`). Variable difficulty will not double until 60 seconds and four accepted samples have passed (`vardiff.go:40`). `cmd/nexapool/main.go:57` does not set `SubmitRate`, `SubmitBurst`, or `BanAfter`, and the TOML file has no fields for them. At the sample start difficulty of 0.2, four accepted shares per second is about 3.4 GH/s. A faster miner is banned in a few seconds, before the difficulty can rise. That is a launch blocker for any miner above that rate.

### Blocker 3, Go, redirects, govulncheck — closed

`pool/go.mod` says `go 1.27.2`. `NewClient` sets `CheckRedirect` to refuse every redirect (`rpc.go:109`). `TestRPCRefusesRedirect` checks the cookie does not follow. On this machine, with `GOTOOLCHAIN=go1.27.2`:

| Command | Result |
| --- | --- |
| `go test -race -count=1 ./...` | pass |
| `go vet ./...` | pass |
| `staticcheck` 2026.2.2 (0.8.2) `./...` | pass. The ignored `HasPrefix` and the dead assignment from the first review are gone. |
| `govulncheck` v1.9.0 `./...` | pass. Go 1.27.2, vuln DB updated 2026-10-08. No vulnerabilities found. |

The API server sets `ReadHeaderTimeout`, `ReadTimeout`, and `WriteTimeout` (`cmd/nexapool/main.go:96`).

### Blocker 4, Tailstorm — the parent is on the wire, the gate is the wrong clock

`NotifyParams` appends `previousBlockHash` when `job.Time >= 1793495471` (`server.go:197`). `publish` uses the same wall clock, refuses an all-zero parent after that instant, and `Submit` mixes that parent in (`service.go:193`, `service.go:272`). `TestNotifyParamsSwitchAtActivation` and `TestNotifySwitchesAtTailstormActivation` lock the one-second boundary: five parameters at `1793495470`, six at `1793495471`, and the pre-fork echelon vector is rejected once the parent is mixed. `TestTailstormActivationInstant` checks that `1793495471` is 2026-11-01 01:11:11 UTC.

The mix matches `src/pow.cpp` for `powAlgorithm == 1` when `prevhash` is not null: one SHA-256 over the internal mining hash concatenated with the internal parent (`CSHA256Writer::GetHash` is a single SHA-256, then `sha256` of that digest), parent reversed from `GetHex`. `TestPowHashTailstormMatchesPowCpp` rebuilds that construction and compares it to `PowHash`. nexad's tree has no published final post-fork digest. `src/test/activation_tests.cpp` only checks median-time boundaries.

The activation constant is not nexad's. `src/chainparams.cpp` sets `NEXT_FORK_ACTIVATION_TIME` to `4102488000` (2100-01-01 12:00:00 UTC) and copies it into every chain's `nextForkActivationTime`. `1793495471` does not appear in that tree. `IsUpgrade2Activated` is the previous block's median time past, not the pool's wall clock, and `fTailstormEnabled` (which is what makes `getminingcandidate` emit a real parent) turns on when the tip is pending, one block earlier. Against this nexad, `previousBlockHash` stays 64 zero bytes on 1 November 2026. `publish` then returns an error (`service.go:199`) and the pool stops issuing jobs. Gating on the candidate's non-zero parent, or on the node's upgrade time, is what follows the node. A wall-clock constant the node does not use will halt the pool 19 days after this review.

### Hot wallet — closed, with one stuck-reconcile note

The unit runs as `nexapool`, not `nexa` (`deploy/nexapool.service:10`), with `UMask=0077` and the kernel, syscall, and device sandbox flags that were missing. `PayOnce` refuses to run when `getbalance` is above `HotWalletMax` (`service.go:402`). The default cap is 5,000,000 NEX (`config.go:161`). The cookie and the passphrase file must be regular files, mode without group or world access (`secret.go:14`). `node.url` must be loopback http(s) with no userinfo (`secret.go:40`, `config.go:184`). The API bind must be loopback (`config.go:178`). A second process fails the payout flock instead of paying (`store.go:123`, `TestPayoutLock`).

If the balance is already over the cap, `PayOnce` returns before `RunPayouts` (`service.go:413`). In-flight rows are not reconciled until someone sweeps the wallet back under the cap. They are not sent twice.

### Original mediums

| Finding | At 1109d60b |
| --- | --- |
| `clean: true` still paid the previous 32 jobs | Closed. `publish` always sets `Clean` and replaces the job map (`service.go:220`). `TestUnknownJobIsStaleAndCleanNotifyDropsThePreviousJob`. |
| One `getblock` "not found" orphaned the block | Closed. Any `getblock` error is retried (`service.go:338`). Only `confirmations < 0` orphans (`service.go:345`). `TestOneMissingBlockReplyDoesNotOrphanImmatureWork`. |
| Ledger matured at 5000, wallet spends at 5001 | Closed as a default. `Maturity <= 0` becomes 5001 (`config.go:136`). The sample sets 5001. A positive value below 5001 is still accepted. |
| `GetBlock` summed every coinbase output | Closed only when `coinbase_address` is set. See the blocker above. `rpc.go:247` skips every output when `PoolAddress` is empty, and `main.go:39` copies that empty string through. `MatureOnce` will not credit a zero reward (`service.go:367`). `config.example.toml:8` says empty uses the wallet default. It does not. The example ships `coinbase_address = ""`. |
| Sent payout not required to confirm | Closed for zero confirmations (`payout.go:180`). A reorg after the configured count (default 1) still leaves the row `sent`. |
| Overlapping payouts returned `SQLITE_BUSY` immediately, no process lock | Closed. `LockPayouts` is a non-blocking flock (`store.go:123`). The DSN sets `busy_timeout` and `txlock=immediate` (`store.go:65`). `TestConcurrentPayoutReservesTheBalanceOnce` still sees one send. |
| `node.url` and the API bind were not forced to localhost | Closed. `config.go:178`, `config.go:184`. |
| nginx had no rate limit or security headers | Closed. `limit_req`, HSTS, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, CSP, and `ssl_protocols` are in `deploy/nginx-pool.nordiccrypto.no.conf`. CSP still allows `'unsafe-inline'` scripts (`nginx` line 35). |

### Original lows

| Finding | At 1109d60b |
| --- | --- |
| systemd sandbox flags | Closed. The flags listed in the first review are in `deploy/nexapool.service`. This review did not boot the unit. `MemoryDenyWriteExecute` should be smoked on the host before the first start. |
| Firewall text omitted P2P 7228 | Closed. `pool/README.md:100` says keep 7227, 7228, and 8080 closed. |
| `rand.Read` error ignored, extranonces not checked unique | Closed. `uniqueExtraLocked` checks the error and the live set (`server.go:265`). |
| Submitted timestamp is not compared to the job and is not in the hash | Still true (`server.go:472`). Unchanged, and still not a way to weaken a block. |

### Open items

1. **High.** `findComment` advances `from` by JSON rows. nexad counts wallet items. A crash between `sendtoaddress` and `NotePayment` sticks the payout in `review` once the wallet has more than one page of multi-output transactions. `pool/internal/nexa/rpc.go:347`. No operator action except a database edit. `pool/internal/account/payout.go:135`.
2. **High.** Tailstorm flips on wall clock `1793495471`. nexad `37fe286` flips on median time past of `4102488000`, and it sends a real parent only once `fTailstormEnabled` is set. `pool/internal/nexa/fork.go:10`, `pool/internal/pool/service.go:193`.
3. **High.** Empty `coinbase_address` counts no coinbase output, so blocks never mature. `pool/internal/nexa/rpc.go:247`, `pool/config.example.toml:8`, `pool/cmd/nexapool/main.go:39`.
4. **High.** Submit rate 4/s, burst 8, ban after 20, none of them configurable. Variable difficulty waits 60 seconds. `pool/internal/stratum/server.go:120`, `pool/internal/stratum/server.go:477`, `pool/internal/stratum/server.go:583`, `pool/internal/stratum/vardiff.go:40`, `pool/cmd/nexapool/main.go:57`.
5. **Low.** A payout marked sent after one confirmation is not revisited if that transaction is later dropped. `pool/internal/account/payout.go:180`. `payout_confirmations` can be raised.
6. **Low.** `maturity` may be set below 5001. `pool/internal/config/config.go:136`.
7. **Low.** While any immature block exists, the 14-day share prune does not run. Id prune runs only when every immature block's window is filled. The maturity pass no longer loads the whole table. `pool/internal/pool/service.go:380`.
8. **Low.** A hot wallet over the cap skips reconciliation until it is swept. `pool/internal/pool/service.go:413`.
9. **Low.** The submitted timestamp is still not checked against the job. `pool/internal/stratum/server.go:472`.
10. **Low.** CSP allows inline scripts. `pool/deploy/nginx-pool.nordiccrypto.no.conf:35`.
