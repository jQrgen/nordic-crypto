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
