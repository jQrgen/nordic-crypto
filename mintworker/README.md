# mintworker

Policy Worker for event-NFT mints. It is not the tip Worker (`tipworker/`).

The tip Worker takes reader tips and newsletter signups, and its database holds email addresses. A key that can spend does not belong in that process.

When `NC_EVENT_NFT=1` and `MINT_NETWORK=testnet`, this Worker signs a Nexa NFT plus the 1,000 NEXA airdrop, or a Bitcoin Cash CashTokens mint plus the 10,000 sat airdrop, and broadcasts it. The key is the Worker secret. UTXOs are read from the testnet electrum nodes, not from the client. A mainnet address is refused. With the flag off, `signs` in `/api/health` is false and nothing is broadcast. The Worker has not been deployed.

The Bitcoin Cash signer is pure JavaScript (`@noble/curves` and `@noble/hashes`, plus a small CashAddr and transaction codec in `src/bch/`). It does not import `@bitauth/libauth`. That library compiles WASM from bytes when the module loads, and workerd rejects that (`Wasm code generation disallowed by embedder`, then `Top-level await in module is unsettled`). `libnexa-ts` is also pure JavaScript. It uses `Buffer`, so `wrangler.toml` sets `compatibility_flags = ["nodejs_compat"]`.

`GET /api/treasury` and `GET /api/treasury/history` return the public ledger and `balance_series`. Amounts in the database are satoshis. The public Nexa balance is those satoshis divided by 100. The hourly cron reads each hot-wallet balance from electrum and stores it, including when signing is off. A mint reads that stored balance. It does not call electrum for a missing balance, and it does not call electrum until the in-memory rate limit (8 requests per 10 minutes per client, 40 per isolate) and the caps have allowed the request. The raw IP is hashed in memory and not stored. `POST /api/treasury/observe` does the same balance read on demand and requires `ADMIN_TOKEN`. A row is the time, the kind, the amount and the txid. It does not name the sender.

## Hot key

The key is a Cloudflare Worker secret: `NEXA_HOT_KEY` and `BCH_HOT_KEY` on the Worker `nordic-crypto-mint`.

Cloudflare injects those bindings into every isolate. A process restart, a new instance, and `wrangler deploy` keep the same secret. The handler calls `loadHotKey` and never puts the value on a response, in D1, or in a log. Observability is off.

The operator installs the key with `keygen.sh` (see that file). The script refuses to run unless `MINT_KEYGEN_I_AM_THE_OPERATOR=yes`. It reads the key with echo off and pipes it to `wrangler secret put`. It does not write a file.

An optional copy in a password manager is the operator's own note. The running service does not use that copy. Recovery after a restart is the Worker secret, automatically.

The public refill address is the same hot wallet. It is a var (`NEXA_HOT_ADDRESS`, `BCH_HOT_ADDRESS`). The testnet addresses are already in `wrangler.toml`. The address is not a secret.

## Token setup

The hot keys exist only as Worker secrets, so the operator creates the Nexa group and the CashTokens category through the Worker. The route is `POST /api/admin/setup-tokens?chain=nexa` or `?chain=bch`. It runs only when `NC_EVENT_NFT=1` and `MINT_NETWORK=testnet`. A mainnet address or a mainnet key is refused. Each chain can succeed once: the public id and txid are stored in D1 (`token_setup`), and a second call returns `already_setup` without signing again.

The request needs `Authorization: Bearer <ADMIN_TOKEN>`. The compare is constant-time. A missing token is `unauthorized` and does not open a socket.

```
printf '%s' "$ADMIN_TOKEN" | npx wrangler secret put ADMIN_TOKEN
npx wrangler d1 migrations apply nordic-crypto-mint --remote
curl -sS -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  "https://nordic-crypto-mint.nordiccrypto.workers.dev/api/admin/setup-tokens?chain=nexa"
curl -sS -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  "https://nordic-crypto-mint.nordiccrypto.workers.dev/api/admin/setup-tokens?chain=bch"
npx wrangler secret delete ADMIN_TOKEN
```

The body contains the public id and the txid only. It does not contain the key or the raw transaction. Copy the ids into `wrangler.toml` as `NEXA_PARENT_GROUP` and `BCH_CATEGORY` and deploy again, so a rebuilt database is not required. Until that deploy, the mint reads the D1 row when the var is unset. The var wins when both are set.

Nexa needs a plain coin of at least 5,000 sats. Bitcoin Cash needs a vout-0 coin of at least 1,746 sats (800 token dust + 546 change + 400 fee). If the only coin is not at vout 0 and is at least 2,146 sats, the Worker pays the hot address first and then creates the category. An empty wallet returns `unfunded` with `have_sats`, `need_sats` and `detail` (`no_coins` or `no_vout0`).

`scripts/setup-tokens.mjs` remains for a machine that has the key locally. It refuses mainnet. The deployed keys are not in that script.

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

`compatibility_date` is `2026-09-01`, which includes custom-port subrequests (the default since 2024-09-02) and the Workers WebSocket client on those ports. Port 25 is blocked; 30004 and 50004 are not. Checked from this environment on 2026-10-07, including from `wrangler dev`: each socket answered, and `POST /api/treasury/observe` stored the public balances.

Rostrum's `blockchain.address.get_balance` is satoshis. Its verbose transaction `value` is NEXA (two decimal places). The refill sync converts that to satoshis before writing the ledger. A Bitcoin Cash verbose `value` in whole coins is a float and is skipped.

## What is not deployed

`publish.sh` does not deploy this Worker. A signing deploy is manual:

```
npx wrangler deploy --var NC_EVENT_NFT:1 --var MINT_NETWORK:testnet
```

A plain `wrangler deploy` leaves signing off, because those two vars are not in `wrangler.toml`. Nothing in git is a private key.
