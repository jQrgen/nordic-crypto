# mintworker

Policy Worker for event-NFT mints. It is not the tip Worker (`tipworker/`).

The tip Worker takes reader tips and newsletter signups, and its database holds email addresses. A key that can spend does not belong in that process.

When `NC_EVENT_NFT=1` and `MINT_NETWORK=testnet`, this Worker signs a Nexa NFT plus the 1,000 NEXA airdrop, or a Bitcoin Cash CashTokens mint plus the 10,000 sat airdrop, and broadcasts it. The key is the Worker secret. UTXOs are read from the testnet electrum nodes, not from the client. A mainnet address is refused. With the flag off, `signs` in `/api/health` is false and nothing is broadcast. The Worker has not been deployed.

The Bitcoin Cash signer is pure JavaScript (`@noble/curves` and `@noble/hashes`, plus a small CashAddr and transaction codec in `src/bch/`). It does not import `@bitauth/libauth`. That library compiles WASM from bytes when the module loads, and workerd rejects that (`Wasm code generation disallowed by embedder`, then `Top-level await in module is unsettled`). `libnexa-ts` is also pure JavaScript. It uses `Buffer`, so `wrangler.toml` sets `compatibility_flags = ["nodejs_compat"]`.

`GET /api/treasury` and `GET /api/treasury/history` return the public ledger and `balance_series`. Amounts in the database are satoshis. The public Nexa balance is those satoshis divided by 100. The hourly cron reads each hot-wallet balance from electrum and stores it, including when signing is off, so the first mint is not refused with `balance_unknown`. `POST /api/treasury/observe` does the same read on demand. A row is the time, the kind, the amount and the txid. It does not name the sender.

## Hot key

The key is a Cloudflare Worker secret: `NEXA_HOT_KEY` and `BCH_HOT_KEY` on the Worker `nordic-crypto-mint`.

Cloudflare injects those bindings into every isolate. A process restart, a new instance, and `wrangler deploy` keep the same secret. The handler calls `loadHotKey` and never puts the value on a response, in D1, or in a log. Observability is off.

The operator installs the key with `keygen.sh` (see that file). The script refuses to run unless `MINT_KEYGEN_I_AM_THE_OPERATOR=yes`. It reads the key with echo off and pipes it to `wrangler secret put`. It does not write a file.

An optional copy in a password manager is the operator's own note. The running service does not use that copy. Recovery after a restart is the Worker secret, automatically.

The public refill address is the same hot wallet. It is a var (`NEXA_HOT_ADDRESS`, `BCH_HOT_ADDRESS`). The testnet addresses are already in `wrangler.toml`. The address is not a secret.

## Token setup

Nothing in the Worker creates the Nexa group or the CashTokens category. The operator runs this once, locally:

```
MINT_SETUP_I_AM_THE_OPERATOR=yes node scripts/setup-tokens.mjs
```

The script reads `NEXA_HOT_KEY` and `BCH_HOT_KEY` from the environment, or asks once on a terminal with echo off. It does not write a file and it does not print the key. Default is Nexa testnet and Bitcoin Cash chipnet. `--mainnet` is required before it will touch mainnet. `--chain nexa` or `--chain bch` limits the run. `--dry-run` builds the transaction and prints the ids without broadcasting.

It prints only:

```
NEXA_PARENT_GROUP=nexatest:...
BCH_CATEGORY=<64 hex chars>
```

Set those as Worker vars before a signing deploy. The hot wallet needs a coin to spend: Nexa at least 5,000 sats for the group transaction, and Bitcoin Cash a vout-0 coin of at least 1,746 sats (800 token dust + 546 change + 400 fee). If the only coin is larger and not at vout 0, the script first pays the hot address so genesis has a vout-0 parent.

## Caps

`caps.json` is the source of the numbers. `src/policy.js` refuses a mint when:

- the observed balance is missing, at or under the reserve, or too small for one mint (`below_reserve`, `needs_funding`)
- this identity already minted for this event (`identity_used`) — one NexaID per event, one Bitcoin Cash address per event
- the event cap or the day cap is reached

The reserve is 2,040 NEXA and 23,000 sats. A balance equal to the reserve is refused, so the wallet has to sit strictly above it. One Nexa mint draws 1,020 NEXA (1,000 airdrop plus up to 20 NEXA of fee). One Bitcoin Cash mint draws 11,500 sats.

Tests: `npm test` (no network, no key).

## Electrum

Broadcast and balance reads use outbound WebSocket:

- `wss://testnet-electrum.nexa.org:30004` (Rostrum)
- `wss://chipnet.imaginary.cash:50004` and `wss://chipnet.bch.ninja:50004` (Fulcrum)

`compatibility_date` is `2026-09-01`, which includes custom-port subrequests (the default since 2024-09-02) and the Workers WebSocket client on those ports. Port 25 is blocked; 30004 and 50004 are not. Checked from this environment on 2026-10-07: each socket answered `server.version`.

## What is not deployed

`publish.sh` does not deploy this Worker. A signing deploy is manual:

```
npx wrangler deploy --var NC_EVENT_NFT:1 --var MINT_NETWORK:testnet
```

A plain `wrangler deploy` leaves signing off, because those two vars are not in `wrangler.toml`. Nothing in git is a private key.
