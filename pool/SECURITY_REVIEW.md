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

## Re-review at e1e3bac

Reviewed `e1e3bacaa61fbca4f684fb7a12d13733afb20ee1` on `cursor/nexa-pool-4f40` by reading the code and running the tests below. The finding table in `pool/SECURITY.md` was not used as evidence. nexad is still `dev` at `37fe286` (`getwalletinfo` in `src/wallet/rpcwallet.cpp`, `AddToWallet` in `src/wallet/wallet.cpp`, `CheckProofOfWork` in `src/pow.cpp`, `fTailstormEnabled` in `src/validation.cpp`, `IsUpgrade2Activated` in `src/validation/forks.cpp`). Nothing in this file was pushed onto the PR branch.

**Verdict: not PASS.** One blocker remains.

Comment recovery now pages by wallet-item count, and `nexapool review` cannot mark a row sent unless the wallet lookup returns a confirmed txid. The scan's end condition trusts `getwalletinfo.txcount`, which is `mapWallet.size()/3` and not the `wtxOrdered` length `listtransactionsfrom` walks. A crashed no-change payout that lands on a 1000-item boundary is reported as a completed miss. `nexapool review -resolve release` then returns those coins, and the next payout pass sends them again. Tailstorm follows the candidate parent, an empty coinbase address is refused at startup, and the submit cap is configurable with the per-IP and global caps still in front of it.

### Blocker 1, comment recovery — the stride is fixed, the stop count is not

Severity: **high**. `pool/internal/nexa/rpc.go:361`, `pool/internal/nexa/rpc.go:384`, `pool/internal/account/payout.go:332`.

`findComment` (`rpc.go:358`) requests `listtransactionsfrom "*" 1000 from` and sets `from` to `from + 1000`. It no longer adds the JSON row count, and a short JSON page is not the end when `txcount` is unknown. `TestFindCommentPagesByWalletItemCount` covers two rows per item, one silent item, and a full silent page when `txcount` equals the item count. `TestCrashedPaymentPastTheFirstPageIsSettledNotResent` is the crash after `sendtoaddress` and before `NotePayment` with no `txcount`: the comment on item 1000 is found, the row is marked sent with `TxID`, and the second pass does not send.

The stop uses `getwalletinfo.txcount` (`rpc.go:408`). nexad sets that field to `(int)pwalletMain->mapWallet.size() / 3` (`src/wallet/rpcwallet.cpp:3054`). `mapWallet` stores `GetId`, `GetIdem`, and each output `IsMine` accepts (`src/wallet/wallet.cpp` around the `AddToWallet` inserts). A send with change is three entries and the integer division matches `wtxOrdered`. A send with no change to an address outside the wallet is two entries, id and idem, and no output. One thousand ordinary wallet items (3000 map entries, `txcount` 1000) plus that payout (`wtxOrdered` index 1000) makes `txcount` stay 1000. The loop reads items 0–999, then `next >= items` (`rpc.go:384`) and returns not found. `TestFindCommentTrustsTxCountPastTheLastPage` shows `LookupPayment` returning a completed miss for that comment. When `txcount` is 0 (`mapWallet.size() < 3`), `rpc.go:361` returns not found without calling `listtransactionsfrom`.

A completed miss still does not send by itself. `finishExisting` moves the row to `review` (`payout.go:172`). `Reconcile` does not create a send. `recheckSent` moves a previously sent row whose lookup misses back to `review` (`payout.go:219`) and does not send either.

`nexapool review` (`cmd/nexapool/main.go:125`) is the operator path, under `LockPayouts`. `ResolveReview` (`payout.go:305`):

- `complete` requires the lookup to find the payment, a non-empty `TxID`, and `Confirmations >= minConfs` (`payout.go:321`). A miss, an empty id, and zero confirmations are refused. An unsent row cannot be marked sent through this action.
- `release` requires the lookup to finish and report the payment absent (`payout.go:332`). It then sets the row `failed` (`store.go:628`), which returns the coins to `Payable`.

The false miss satisfies `release`. `TestReleaseOfATxCountMissPaysAgain` reserves the crashed row, sees `review` and zero sends, sees `complete` refuse, sees `release` succeed, and sees the next `RunPayouts` transmit the payout. The original send is still in the wallet. That is a second payment of the same coins. The command is doing what its comment says — return coins when a finished search does not find the send — and the search is wrong at the page boundary.

### Blocker 2, Tailstorm — closed on the default

`TailstormParent` (`pool/internal/nexa/fork.go:10`) is true only for a 64-hex parent that is not all zeros. `publish` calls `tailstormActive` (`service.go:206`). The default mode `auto` with `TailstormAt == 0` returns that parent check (`service.go:286`). There is no `1793495471` gate. `NotifyParams` appends `previousBlockHash` only when `TailstormParent` is true (`server.go:209`). `Submit` mixes `job.prev` only when those 32 bytes are present and not zero (`service.go:324`).

The mix still matches `src/pow.cpp` for `powAlgorithm == 1`: one SHA-256 over the internal mining hash concatenated with the internal parent, then SHA-256 of that digest, parent reversed from `GetHex`. `TestPowHashTailstormMatchesPowCpp` rebuilds that and compares it to `PowHash`. nexad still publishes no post-fork final digest. `fTailstormEnabled` is what makes `getminingcandidate` emit a real parent, and it turns on when the tip is pending the upgrade. Following a non-zero parent is the same signal.

`on` forces the mix and `publish` returns an error when the parent is missing or zero (`service.go:214`), so jobs stop instead of being hashed the wrong way. `off` ignores a real parent. `tailstorm_activation` compares `getblockchaininfo.mediantime` (`rpc.go:421`) with the configured unix time and ignores the parent until that median time is reached (`service.go:279`). A median-time RPC error fails `publish`. The sample leaves `tailstorm = "auto"` and the override commented (`config.example.toml:30`). `TestTailstormFollowsTheCandidateNotTheClock` pins the pool clock at 2030, keeps a zero parent pre-fork, switches when the parent appears, rejects the pre-fork vector once it is mixed, and keeps the pre-fork hash when `TailstormAt` is still ahead of the node's median time even though the candidate already has a parent. Forcing `off`, or setting `tailstorm_activation` in the future, mines the pre-fork hash while nexad may already be mixing. The shipped default does not do that.

### Blocker 3, empty coinbase — closed

`config.Load` refuses an empty or invalid `coinbase_address` (`config.go:141`). `pool.New` does the same (`service.go:101`). `GetBlock` returns an error when `PoolAddress` is empty (`rpc.go:246`) instead of summing zero. `main.go` copies the address onto the RPC client before `New`. The sample says the field is required (`config.example.toml:8`). The example value is still `""`, so the process will not start until it is set. `TestGetBlockRequiresPoolAddress` and `TestMaturityAndCoinbaseAreRequired` cover the refusal.

### Blocker 4, submit limits — closed, grace does not lift the caps

Defaults are 128 submits per second, burst 256, ban after 20, grace 3 minutes (`server.go:126`). The same numbers are the TOML defaults (`config.go:224`) and `config.example.toml:47`, and `main.go` wires them into the listener. At the sample start difficulty of 0.2, 128/s is about 110 GH/s, which the sample comment states. Variable difficulty uses a 10 second retarget while `now.Sub(started) < grace`, and 60 seconds after that (`vardiff.go:42`). It still waits for four samples. `TestVarDiffRampsDuringGrace` covers the shorter wait.

`accept` refuses a banned address, a host already at `MaxPerIP` (default 16), and a 4097th connection before a session exists (`server.go:232`). That check does not look at the grace window. `TestPerIPCap` still refuses the second connection when `MaxPerIP` is 1.

`mining.submit` parses `ntime` and rejects a stamp that does not match the current job before the rate limit (`server.go:491`). A rate-limit miss returns `"rate limit"` and returns before `bindNonce` and before `Submit`, so NexaPow does not run (`server.go:497`). During grace, that miss does not call `penalise` (`rateLimitBans`, `server.go:607`). A bad nonce, a low share, and a bad `ntime` still increment `bad` during grace, and `BanAfter` still closes the connection. `TestRateLimitDoesNotBanDuringGrace` covers the grace exemption.

`started`, `bad`, and the token bucket are per session (`newSession`, `server.go:326`). A new connection starts `tokens` at `SubmitBurst` and restarts the 3 minute grace. Cycling connections avoids the rate-limit ban. The sustained accepted rate on each connection is still `SubmitRate`, and concurrent sockets from one address are still `MaxPerIP`. A reconnect can spend another burst of 256. That is leftover headroom on top of the cap, not a way around the per-IP or global limits, and the Schnorr check stays inside the bucket.

### Spot checks

| Item from 1109d60b | At e1e3bac |
| --- | --- |
| Sent payout not revisited after it is dropped | Closed. `RunPayouts` calls `Reconcile` first (`payout.go:93`). A sent row whose lookup misses moves to `review` and is not sent again (`payout.go:219`). Confirmations below 0 call `Drop` (`payout.go:226`), which marks `failed` and returns the coins so they can be paid once. `settle` does the same for a conflicted in-flight row (`payout.go:248`). |
| `maturity` below 5001 | Closed. `0` becomes 5001 and any smaller value is an error in `config.Load` (`config.go:158`) and `pool.New` (`service.go:113`). The sample sets 5001. |
| Share prune skipped while any block is immature | The time prune always runs (`service.go:442`). `TestSharePruneRunsWhileBlockIsImmature` deletes a 20-day-old share while the block stays immature and keeps a 1-minute-old share. Id prune still waits until every immature window is filled (`service.go:386`). While any window is unfilled, or a `getblock` errors, `keep` is 0, so the 14-day prune can delete shares that unfilled window still needs. |
| Hot wallet over the cap skipped reconciliation | Closed. `PayOnce` unlocks, and when `getbalance` is over the cap it calls `Reconcile` and returns the cap error without a new send (`service.go:468`). `TestReconcileWhenWalletIsOverTheCap` marks the reserved row sent and records no send. |
| Submitted `ntime` not checked | Closed. Stratum rejects a stamp that is not the job's `ntime` and penalises (`server.go:491`). `Service.Submit` rejects `sh.NTime != job.wire.Time` with code 20 before hashing (`service.go:319`). `TestSubmitRejectsNTimeThatDoesNotMatchTheJob` and `TestSubmitRejectsMismatchedNTime` cover both. The hash still does not contain `ntime`. The job time is still the pool clock passed as the notify field. |
| CSP `'unsafe-inline'` | Closed. `script-src` is `'self'` (`deploy/nginx-pool.nordiccrypto.no.conf:35`). The pages load `pool-text.js` and `pool.js`. `web_test.go` rejects `unsafe-inline`, an inline `window.POOL_TEXT`, and a script tag without `src`. |

### Tests and tools

On this machine, `GOTOOLCHAIN=go1.27.2`, from `pool/`:

| Command | Result |
| --- | --- |
| `go test -race -count=1 ./...` | pass |
| `go vet ./...` | pass |
| `staticcheck` 2026.2.2 (0.8.2) `./...` | pass |
| `govulncheck` v1.9.0 `./...` | pass. Go 1.27.2, vuln DB updated 2026-10-08. No vulnerabilities found. |

### Open items

1. **High.** `findComment` stops at `getwalletinfo.txcount`, and nexad's `txcount` is `mapWallet.size()/3`, not the wallet-item count `listtransactionsfrom` uses. A no-change payout past a 1000-item boundary is a completed miss. `nexapool review -resolve release` then returns the coins and the next pass pays them again. `pool/internal/nexa/rpc.go:384`, `pool/internal/nexa/rpc.go:361`, `pool/internal/account/payout.go:332`. nexad `src/wallet/rpcwallet.cpp:3054`.
2. **Low.** `tailstorm = "off"`, or `tailstorm_activation` still above the node's median time, ignores a parent nexad is already sending. Shares are checked as pre-fork. The sample default is `auto` with the override unset. `pool/internal/pool/service.go:276`.
3. **Low.** A new connection restarts the 3 minute submit grace, the ban counter, and the burst of 256. Per-IP and the global cap still apply, and rejected submits do not run NexaPow. `pool/internal/stratum/server.go:326`, `pool/internal/stratum/server.go:607`.
4. **Low.** While an immature block's PPLNS window is unfilled, the 14-day share prune runs with `keep` 0. `pool/internal/pool/service.go:442`.

## Re-check at a93d1c6

Reviewed `a93d1c6704bee99a171c5fa56323be689f2a30ae` on `cursor/nexa-pool-4f40` by reading the code and running the tests below. nexad is still `dev` at `37fe286` (`listtransactionsfrom` and `ListTransactions` in `src/wallet/rpcwallet.cpp`, `GetAmounts` and `GetDepthInMainChain` in `src/wallet/wallet.cpp`). The diff from `e1e3bac` is the comment scan and `nexapool review -confirm`. Nothing in this file was pushed onto the PR branch.

**Verdict: not PASS.**

`getwalletinfo.txcount` is no longer the end of the scan, and the two tests that reproduced that miss now pass. A short JSON page is still treated as a finished search. nexad can return a short page while `wtxOrdered` has more items, and `release -confirm none` then pays the crashed payout again.

### What this commit closes

`findComment` (`pool/internal/nexa/rpc.go:362`) no longer calls `getwalletinfo`. `from` advances by the requested item count, 1000, which is the unit `listtransactionsfrom` uses for `from` and `count` (`src/wallet/rpcwallet.cpp:2202`). A page of two-row items no longer skips the next thousand wallet items. `TestFindCommentTrustsTxCountPastTheLastPage` finds the comment on item 1000 when `txcount` is 1000, and it finds the only item when `txcount` is 0. `TestReleaseOfATxCountMissPaysAgain` settles that row as sent and refuses `release` for `""`, `none`, and the stored txid. The second pass does not send.

`ResolveReview` (`payout.go:308`) returns the lookup error (`payout.go:320`), so an RPC failure is not a miss. `complete` still requires a found payment, a non-empty txid, and enough confirmations (`payout.go:324`). `release` refuses a found payment (`payout.go:336`), refuses an empty `-confirm` (`payout.go:340`), accepts `none` only when the row's txid is empty (`payout.go:343`), and otherwise requires `-confirm` to match the stored txid (`payout.go:347`). `TestResolveReviewCompletesOrReleases` covers those refusals.

A `Call` error or a JSON decode error returns from `findComment` (`rpc.go:370`, `rpc.go:374`). `finishExisting` leaves the row reserved (`payout.go:168`). `recheckSent` leaves a sent row sent (`payout.go:215`). The scan stops with an error once `from` passes 5,000,000 (`rpc.go:366`), which is 5,001 pages and then an unfinished search. `from` increases by 1000, and a `next <= from` result is also an error (`rpc.go:387`).

The rest of `e1e3bac` is untouched by this diff: Tailstorm, the coinbase address, the submit caps, maturity, prune, the hot-wallet reconcile, `ntime`, and the CSP. `go test -race -count=1 ./...` covers those packages and passed.

### Short page is not the end of the wallet

Severity: **high**. `pool/internal/nexa/rpc.go:383`, `pool/internal/account/payout.go:350`.

`listtransactionsfrom` walks `wtxOrdered` (`rpcwallet.cpp:2208`). Each step counts as one item toward `count`, then `ListTransactions` appends zero or more JSON objects. The function returns an empty array when `from` is already past the map (`rpcwallet.cpp:2203`). A page whose JSON array is shorter than 1000 is the end of the wallet only when that loop stopped because the iterator reached the end.

It also returns a short array when the loop consumed a full `count` and some of those items emitted nothing:

- `GetAmounts` skips every output `IsChange` accepts (`wallet.cpp:1777`). `IsChange` is an output that pays this wallet and is not in the address book (`wallet.cpp:1450`). If every output of a debit is change, `listSent` is empty. The send loop still enters when `nFee != 0`, and the inner loop appends nothing (`rpcwallet.cpp:1849`).
- Received rows are appended only when `GetDepthInMainChain() >= 0` (`rpcwallet.cpp:1878`). A conflicted transaction whose block is still on the active chain has negative depth (`wallet.cpp:4977`, `MarkConflicted` at `wallet.cpp:1325`). A receive with no debit then contributes no row.
- The pool passes `includeWatchonly` true (`rpc.go:370`), so the filter is `ISMINE_SPENDABLE | ISMINE_WATCH_ONLY` (`rpcwallet.cpp:2190`). Watch-only outputs are included. They do not shorten the page.
- Abandoned sends are still appended, with `abandoned` set (`rpcwallet.cpp:1872`). Abandoning a send does not remove its row.
- The account argument is `"*"`, so neither wallet transactions nor accounting `move` entries are dropped for the account name.

One silent item in a page of single-row transactions makes `len(txs)` 999. `findComment` then returns a completed miss (`rpc.go:383`). The comment's own code says an item can emit none, and the stop condition treats that page as the end. `TestFindCommentPagesByWalletItemCount` still finds a comment after one silent item only because the other items in that test emit two rows, so the JSON array stays longer than 1000. `TestFindCommentStopsOnAShortPageBeforeTheWalletEnds` is the one-row case: item 0 emits nothing, item 1000 holds the comment, and `LookupPayment` returns not found with a nil error.

That nil error is what `release` requires. The crash between `sendtoaddress` and `NotePayment` leaves the review row with an empty txid, so `-confirm none` is the accepted confirmation (`payout.go:343`). `TestReleaseOfAShortPageMissPaysAgain` reserves that row, sees `review` and zero sends, sees `complete` and a release without `-confirm` refused, sees `-confirm none` succeed, and sees the next `RunPayouts` transmit the payout. The original send is still in the wallet.

A final page that really is the end of `wtxOrdered` is also short, and stopping there is right. A page of multi-output items can be 1000 or more JSON rows even when fewer than 1000 items remain; the next request then comes back empty and the scan stops. The JSON length cannot tell a full item page that contained a silent entry from the last page of the wallet.

### Tests and tools

On this machine, `GOTOOLCHAIN=go1.27.2`, from `pool/`:

| Command | Result |
| --- | --- |
| `go test -race -count=1 ./...` | pass, including `TestFindCommentTrustsTxCountPastTheLastPage` and `TestReleaseOfATxCountMissPaysAgain` |
| `go vet ./...` | pass |
| `staticcheck` 2026.2.2 (0.8.2) `./...` | pass |
| `govulncheck` v1.9.0 `./...` | pass. Go 1.27.2, vuln DB updated 2026-10-08. No vulnerabilities found. |

### Open item

1. **High.** `findComment` ends a scan when a page has fewer than 1000 JSON rows. `listtransactionsfrom` can return that page after walking 1000 wallet items, because a change-only debit and a conflicted receive emit no row. The crash before `NotePayment` is then a completed miss, and `nexapool review -resolve release -confirm none` pays it again. `pool/internal/nexa/rpc.go:383`, `pool/internal/account/payout.go:350`. nexad `src/wallet/rpcwallet.cpp:2208` and `src/wallet/rpcwallet.cpp:1849`.

## Re-check at 01479f9

Reviewed `01479f9fc43bf88b2eb1a56476c457b5e7b2e1ba` on `cursor/nexa-pool-4f40`. nexad is still `dev` at `37fe286`. Nothing in this file was pushed onto the PR branch.

**Verdict: not PASS.**

A short page and a single empty page no longer end the scan, `txcount` is no longer trusted by itself, and `0` or a negative `release_none_min_age` is refused. `txcount*3` is not an upper bound on `wtxOrdered`. Accounting entries live in that map and not in `mapWallet`, so two zero-row pages can still finish the search before a later payout, and `release` then pays it again.

### What holds

`findComment` (`pool/internal/nexa/rpc.go:375`) advances `from` by 1000 wallet items. It stops only after two pages in a row return zero rows and `from` is greater than `txcount*3 + 1002` (`rpc.go:396`, `rpc.go:406`). A page of 999 rows resets the empty count. `TestFindCommentStopsOnAShortPageBeforeTheWalletEnds` finds the comment after one silent item and after 2000 silent items when `txcount` is 1000. `TestFindCommentTrustsTxCountPastTheLastPage` and `TestReleaseOfATxCountMissPaysAgain` still find the no-change payout that `txcount` used to hide, and `release` of that found payment is refused. `TestReleaseOfAShortPageMissPaysAgain` settles the short-page crash and does not send again.

`getwalletinfo` failure, a missing or negative `txcount`, and a multiplying overflow return an error (`rpc.go:421`). `TestFindCommentMissNeedsTheItemBound` shows an empty wallet with `txcount` 0 is a logged miss, and the same wallet with no `txcount` is an unfinished scan. The 5,000,000 cap and a `from` that does not advance are also errors (`rpc.go:379`, `rpc.go:411`). `finishScan` logs the final `from` (`rpc.go:445`).

`mapWallet.size()/3` truncated to an integer, then multiplied by 3, is at most 2 below `mapWallet.size()` (`src/wallet/rpcwallet.cpp:3054`). The `+2` in `walletItemMargin` covers that. The `+1000` covers one page of items added after the `getwalletinfo` call. A wallet whose ordered entries are only transactions has at least two `mapWallet` keys per transaction (`GetId` and `GetIdem`, `wallet.cpp:916`). For that wallet the bound is past the ordered length, and the scan reads every item before it will stop.

`release_none_min_age` of `0`, `0s`, or a negative duration fails `parseDuration` (`config.go:254`). An empty value stays 24 hours. `pool.New` also replaces a non-positive age with 24 hours (`service.go:125`). `none` still requires an empty stored txid (`payout.go:348`) and a reservation at least that old (`payout.go:352`). A found payment is refused (`payout.go:341`). `complete` still requires a found txid and enough confirmations. A lookup error is returned and is not a miss (`payout.go:324`).

### The bound is not the ordered length

Severity: **high**. `pool/internal/nexa/rpc.go:406`, `pool/internal/nexa/rpc.go:431`, `pool/internal/account/payout.go:358`.

`wtxOrdered` is a multimap of wallet transactions and accounting entries (`wallet.h:820`). `AddAccountingEntry` inserts `TxPair(nullptr, &entry)` and does not touch `mapWallet` (`wallet.cpp:4092`). Loading the wallet inserts every stored accounting entry the same way (`walletdb.cpp:686`). The `move` RPC writes two of them, a debit and a credit (`rpcwallet.cpp:1292`). `listtransactionsfrom` walks those entries. For account `"*"` each one appends a `move` row (`rpcwallet.cpp:1923`), so accounting entries do not create an empty page by themselves. They do push later wallet items to higher indexes while leaving `txcount` unchanged.

`txcount*3 + 1002` can therefore sit below `wtxOrdered.size()`. The stop needs two consecutive zero-row pages as well (`rpc.go:406`). A change-only debit and a conflicted receive still emit nothing (`rpcwallet.cpp:1849`, `wallet.cpp:1777`, `rpcwallet.cpp:1878`). Two thousand of those in a row are two empty pages. If accounting entries before that run make the second empty page start above the bound, the scan returns a completed miss and does not read the payout after the run.

`TestFindCommentMissesACommentPastAccountingEntries` builds that wallet: 5000 `move` rows, 2000 silent items, then the comment. The reported `txcount` is `(2000*2+2)/3`, which is what `mapWallet.size()/3` is when each silent transaction and the payout add two map keys and the moves add none. `LookupPayment` returns not found with a nil error.

That nil error is a finished search. The crash before `NotePayment` has an empty txid, so after `release_none_min_age` the operator's `-confirm none` calls `ReleaseReview` (`payout.go:358`) and the next pass sends the coins again. A row that already stored a txid does not wait for that age: `-confirm` equal to the stored txid releases immediately (`payout.go:355`). `ZapSelectTx` has the same shape as the accounting entries. `EraseFromRam` deletes the id, the idem, and the outpoints (`wallet.cpp:4929`) and leaves the `wtxOrdered` entry in place (`walletdb.cpp:797`), so a zapped silent transaction also occupies an index `txcount` no longer counts.

A hot wallet that never calls `move` and never zaps a transaction keeps the bound past its ordered length. The previous one-item and one-page misses are closed. This stop is still a completed miss for a wallet nexad can actually hold, and `release` still treats that miss as proof the send is absent.

### Tests and tools

On this machine, `GOTOOLCHAIN=go1.27.2`, from `pool/`:

| Command | Result |
| --- | --- |
| `go test -race -count=1 ./...` | pass, including `TestFindCommentTrustsTxCountPastTheLastPage`, `TestFindCommentStopsOnAShortPageBeforeTheWalletEnds`, `TestReleaseOfATxCountMissPaysAgain`, and `TestReleaseOfAShortPageMissPaysAgain` |
| `go vet ./...` | pass |
| `staticcheck` 2026.2.2 (0.8.2) `./...` | pass |
| `govulncheck` v1.9.0 `./...` | pass. Go 1.27.2, vuln DB updated 2026-10-08. No vulnerabilities found. |

### Open item

1. **High.** `txcount*3+1002` is not an upper bound on `wtxOrdered`. Accounting entries are ordered and are not in `mapWallet`, so two zero-row pages can end the scan before a later payout. `release` of that completed miss pays the coins again. `pool/internal/nexa/rpc.go:406`, `pool/internal/nexa/rpc.go:431`, `pool/internal/account/payout.go:358`. nexad `src/wallet/wallet.cpp:4099`, `src/wallet/rpcwallet.cpp:3054`.

## Re-review at e324f0c

Reviewed `e324f0cb2a549f864fe9bd1b350a3bb3c74c247a` on `cursor/nexa-pool-4f40`. nexad is still `dev` at `37fe286`. Nothing in this file was pushed onto the PR branch.

**Verdict: not PASS.**

The payout is now signed, stored, and then broadcast. A row that already has a txid is not given a new raw transaction by the recovery path, and the comment scan is no longer how a payment or a release is decided. Three holes remain. An abandoned or conflicted payout is dropped and the next pass signs a second transaction, with no depth on the competing spend. A re-signed transaction with the same txidem is reported as that conflict because lookup stops on the old txid. `fundrawtransaction` does not lock the coins it selects.

### What holds

`CreatePayout` calls `createrawtransaction`, `fundrawtransaction`, and `signrawtransaction`, and it does not call `sendrawtransaction` (`pool/internal/nexa/rpc.go:333`). `RunPayouts` stores that result and only then broadcasts (`pool/internal/account/payout.go:133`, `payout.go:144`, `payout.go:155`). `Reserve` checks the balance and inserts `txid`, `txidem`, and `raw_tx` in one SQL transaction (`pool/internal/store/store.go:547`). A crash before `Commit` rolls the insert back. The signed hex was never handed to the node, and the next pass is the first broadcast. `TestCrashBeforeReserveDoesNotBroadcast` fails `Reserve` after `Prepare` and records zero broadcasts. `TestCrashAfterStoreBroadcastsTheStoredTransaction` and `TestCrashAfterBroadcastDoesNotSignAgain` keep the stored txid and broadcast that same hex again.

`finishExisting` holds a row with an empty txid and, when the txid is set, only publishes the stored hex (`payout.go:205`). `publish` and `recheckSent` call `Broadcast` with `p.Raw` (`payout.go:225`, `payout.go:267`). `Prepare` runs for a new payable balance (`payout.go:133`). It runs again for that balance only after `Drop` or `ReleaseReview` has marked the row failed, which puts the coins back into `Payable`.

`release` with `-confirm none` requires an empty txid and a reservation at least `release_none_min_age` old (`payout.go:403`). A named `-confirm` has to equal the stored txid (`payout.go:412`). `complete` requires the stored transaction in the wallet or in a block, with enough confirmations, and refuses an abandoned or conflicted view (`payout.go:384`). `release_none_min_age` of `0` or a negative duration still fails `parseDuration`. `LookupPayment` ignores the comment (`rpc.go:477`). `FindComment` is still exported and `nexapool comment` prints it (`pool/cmd/nexapool/main.go:250`). Neither `RunPayouts` nor `ResolveReview` calls it. The scan can still miss a comment after accounting entries (`TestFindCommentMissesACommentPastAccountingEntries`). That miss no longer releases a payout. The open item from the `01479f9` re-check is closed for payment and release.

`gettxout` is called as the outpoint hash with `n = -1` (`rpc.go:630`). That matches nexad: the second argument `-1` means the first argument is the outpoint hash (`src/rpc/blockchain.cpp:1408`), and `decoderawtransaction` emits `prevout.GetHex()` (`src/core_write.cpp:122`). An input that is still in the txpool is not treated as a conflict (`TestLookupTxUsesTheStoredTransaction/unconfirmed_parent`).

### Identity

`GetTxIdem` hashes the transaction without the satisfier scripts (`src/primitives/transaction.h:253`). `GetTxId` hashes that idem together with the scriptSig bytes (`transaction.h:267`). txidem is the id that stays the same when the satisfier changes. txid changes. Outpoints are `SHA256(txidem || vout)` (`transaction.h:33`). The mempool index is unique by txidem (`src/txmempool.h:552`). `gettxpoolentry` looks up txid and then txidem (`src/txmempool.cpp:1689`). `gettransaction` looks up either key in `mapWallet` (`src/wallet/wallet.cpp:153`). `getrawtransaction` searches by txid and then by idem (`src/txlookup.cpp:65`). `-txindex` defaults off (`src/txdb.h:27`); without it, a confirmed transaction is found from an output that is still unspent.

A standard template satisfier is not something a third party can rewrite. A second signature from the wallet key is a new txid and the same txidem. When that transaction is mined, `AddToWalletIfInvolvingMe` sees a different `GetId()` in `mapTxSpends` and marks the stored txid conflicted (`wallet.cpp:1154`, `wallet.cpp:728`). `AddToWallet` then overwrites the idem map entry with the confirmed transaction and leaves the old txid entry in place (`wallet.cpp:950`).

`LookupTx` walks txid first and returns on the first wallet hit (`rpc.go:400`). Negative confirmations set `Conflict` (`rpc.go:418`) and the function returns at `rpc.go:421`. It does not read the idem entry, which is the confirmed payment. `TestLookupTxUsesTheStoredTransaction/conflicted_txid_hides_confirmed_idem` is that stop: `gettransaction` of the stored txid returns `-1`, and `gettransaction` of the txidem is never called. `recheckSent` and `applyState` then `Drop` the row (`payout.go:252`, `payout.go:306`). The next `RunPayouts` signs a new transaction for coins the confirmed idem already paid out.

### Abandoned and conflict depth

`AbandonTransaction` refuses a transaction whose depth is already positive, removes it from the local txpool, and then says there is no guarantee other nodes do not still have it, so it can still be committed (`wallet.cpp:1210`, `wallet.cpp:1215`). It also takes the inputs out of `mapTxSpends` (`wallet.cpp:1252`), which makes them selectable again.

`applyState` and `recheckSent` treat `Abandoned` as final and `Drop` the row (`payout.go:306`, `payout.go:252`). `Drop` returns the coins. The next pass calls `Prepare` and broadcasts a different transaction. `TestAbandonedSentPayoutIsSignedAgain` records that second signature. `release -confirm <txid>` accepts the same flag with no age and no depth (`payout.go:415`).

`gettransaction` does not emit `abandoned`. `WalletTxToJSON` writes confirmations, txid, and txidem (`src/wallet/rpcwallet.cpp:68`) and does not write the flag. The flag is written on `listtransactions` rows (`rpcwallet.cpp:1872`). `walletTx` reads the top-level `abandoned` field (`rpc.go:530`). A real abandon at depth 0, which is what `GetDepthInMainChain` returns when the hash is unset (`wallet.cpp:4968`), therefore arrives as an ordinary unconfirmed wallet transaction. `TestLookupTxUsesTheStoredTransaction/nexad_omits_abandoned` keeps `Abandoned` false and does not look at the txidem. The row stays reserved. The inputs are already free for another `fundrawtransaction`. `release` will not take `-confirm` of the stored txid, because neither `Abandoned` nor `Conflict` is set.

`confirmedInputSpent` is the other way a payout becomes a conflict (`rpc.go:598`). After the wallet, the txpool, and `getrawtransaction` all miss, any input absent from the chain UTXO set and from the txpool sets `Conflict` (`rpc.go:621`). There is no confirmation count of the transaction that spent it. One confirmation of a different spend is enough. `TestConflictingSpendPaysOnceMoreWithANewTransaction` drops the sent row and signs a replacement in the same pass. A reorg that drops that one block can still mine the stored hex, which other nodes may have kept, while the replacement spends other coins. Coinbase maturity on this node is 5000 confirms before the wallet will spend a coinbase (`GetBlocksToMaturity`, `wallet.cpp:4985`). The conflict drop does not wait for anything like that depth.

### Coin locks

`fundrawtransaction` on this nexad is `fundrawtransaction "hexstring" includeWatching` (`src/wallet/rpcwallet.cpp:3251`). The second argument is `includeWatching`. The pool passes `false` (`rpc.go:345`), which keeps watch-only coins out of the selection. `FundTransaction` selects coins and copies them onto the raw transaction (`wallet.cpp:3261`) and leaves `setLockedCoins` unchanged. That set is an in-memory `std::set` (`src/wallet/wallet.h:831`). The wallet database has no record of it, so a lock is gone after a restart, and this funding path does not take one.

`cs_wallet` is held for the duration of one `FundTransaction`, so two fund calls do not interleave inside the wallet. The coins are selectable again as soon as the call returns, until a broadcast puts the spend in the wallet. `Prepare` runs before `Reserve`. A broadcast error leaves the row reserved and the coins unspent, and the next payable address in the same pass can be funded from those same inputs. `TestConcurrentPayoutReservesTheBalanceOnce` shows overlapping runs each call `Prepare` before the reservation commits. The balance is reserved once. The inputs are not.

### Tests and tools

On this machine, `GOTOOLCHAIN=go1.27.2`, from `pool/`:

| Command | Result |
| --- | --- |
| `go test -race -count=1 ./...` | pass, including `TestCrashBeforeReserveDoesNotBroadcast`, `TestCrashAfterStoreBroadcastsTheStoredTransaction`, `TestCrashAfterBroadcastDoesNotSignAgain`, `TestConflictingSpendPaysOnceMoreWithANewTransaction`, and `TestAbandonedSentPayoutIsSignedAgain` |
| `go vet ./...` | pass |
| `staticcheck` 2026.2.2 (0.8.2) `./...` | pass |
| `govulncheck` v1.9.0 `./...` | pass. Go 1.27.2, vuln DB updated 2026-10-08. No vulnerabilities found. |

### Open items

1. **High.** A conflict or an abandoned flag drops the payout and the next pass signs a new transaction. Abandon does not stop another node's mempool from mining the stored hex, and a conflicting spend is accepted at the first missing UTXO, with no depth. `pool/internal/account/payout.go:252`, `pool/internal/account/payout.go:306`, `pool/internal/account/payout.go:415`, `pool/internal/nexa/rpc.go:418`, `pool/internal/nexa/rpc.go:621`. nexad `src/wallet/wallet.cpp:1215`.

2. **High.** Lookup of a re-signed transaction stops on the conflicted stored txid and never reads the txidem, which is the confirmed payment of the same outputs. The row is then dropped and paid again. `pool/internal/nexa/rpc.go:400`, `pool/internal/nexa/rpc.go:421`. nexad `src/primitives/transaction.h:253`, `src/wallet/wallet.cpp:955`, `src/wallet/wallet.cpp:1162`.

3. **High.** `gettransaction` does not report `abandoned`, so a real abandon is invisible, while `AbandonTransaction` has already freed the inputs. `fundrawtransaction` does not lock the coins it selects, and wallet locks are not stored. Another payout can be signed from those inputs while the abandoned hex can still be mined. `pool/internal/nexa/rpc.go:345`, `pool/internal/nexa/rpc.go:530`. nexad `src/wallet/rpcwallet.cpp:68`, `src/wallet/rpcwallet.cpp:3251`, `src/wallet/wallet.cpp:1252`, `src/wallet/wallet.h:831`.
