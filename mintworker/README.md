# mintworker

Policy Worker for event-NFT mints. It is not the tip Worker (`tipworker/`).

The tip Worker takes reader tips and newsletter signups, and its database holds email addresses. A key that can spend does not belong in that process.

When `NC_EVENT_NFT=1` and `MINT_NETWORK=testnet`, this Worker signs a Nexa NFT plus the 1,000 NEXA airdrop, or a Bitcoin Cash CashTokens mint plus the 10,000 sat airdrop, and broadcasts it. The key is the Worker secret. UTXOs are read from the testnet electrum nodes, not from the client. A mainnet address is refused. With the flag off, `signs` in `/api/health` is false and nothing is broadcast. The Worker has not been deployed.

A public node was given a signed mint with unfunded inputs. Nexa testnet answered `Missing inputs`. Chipnet answered `Missing inputs`. Neither reported a decode error. A confirming mint needs coins in the hot wallet, which this draft does not have. `keygen.sh` has not been run.

`GET /api/treasury` and `GET /api/treasury/history` return the public ledger and `balance_series`. The hourly cron writes a balance snapshot and records refills it can see on the hot address. A row is the time, the kind, the amount and the txid. It does not name the sender.

## Hot key

The key is a Cloudflare Worker secret: `NEXA_HOT_KEY` and `BCH_HOT_KEY`.

Cloudflare injects those bindings into every isolate. A process restart, a new instance, and `wrangler deploy` keep the same secret. The handler calls `loadHotKey` and never puts the value on a response, in D1, or in a log. Observability is off.

The operator installs the key with `keygen.sh` (see that file). The script refuses to run unless `MINT_KEYGEN_I_AM_THE_OPERATOR=yes`. It reads the key with echo off and pipes it to `wrangler secret put`. It does not write a file.

An optional copy in a password manager is the operator's own note. The running service does not use that copy. Recovery after a restart is the Worker secret, automatically.

The public refill address is the same hot wallet. It is a var (`NEXA_HOT_ADDRESS`, `BCH_HOT_ADDRESS`) or, until that is set, the placeholder. The address is not a secret. The prototype pages still show the placeholder.

## Caps

`caps.json` is the source of the numbers. `src/policy.js` refuses a mint when:

- the observed balance is missing, at or under the reserve, or too small for one mint (`below_reserve`, `needs_funding`)
- this identity already minted for this event (`identity_used`) — one NexaID per event, one Bitcoin Cash address per event
- the event cap or the day cap is reached

Tests: `npm test` (no network, no key).

## What is not deployed

`publish.sh` does not deploy this Worker. Nothing in git is a private key.
