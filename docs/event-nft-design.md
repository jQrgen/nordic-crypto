# Event NFTs

A generated card for a public event, minted once per identity, paid for by a treasury anyone can fund. The person minting pays nothing. This document is the design. The public site stays off until the flag is on. The mint worker can sign and broadcast on testnet when that flag is on and `MINT_NETWORK` is `testnet`. No key is in git, and nothing here is deployed.

Two chains, two moments:

| | Before the event starts | While the event is running |
| --- | --- | --- |
| Nexa | Pre-event card, "I'm going". Received in Wally Wallet. | Ongoing card, "I was there". Received in Wally Wallet. |
| Bitcoin Cash | Pre-event card, "I'm going". CashTokens NFT. | Ongoing card, "I was there". CashTokens NFT. |

That is four cards per event. Each chain has its own treasury. The hard rule is one mint per identity, per chain, per event. The card kind does not grant a second mint: the same NexaID cannot take both the pre-event card and the ongoing card. Widening that to one card per kind is an open choice.

## What's on the NFT and visible in Wally

Wally Wallet reads a Nexa NFT v2 zip. The fields it shows on the token screen are `title`, `series`, `author`, the host of the signed document URL as the provider, `info` (rendered as HTML), and `license`. `keywords`, `appuri` and `data` travel in the same `info.json`. The zip also carries `cardf` (front, square, at most 300 px and 2 MB in the live format; the prototype preview is 640 px), `cardb` (back) and `public` (the image used in public listings). The subgroup id of a Nexa NFT is the double SHA-256 of that zip, so two identical zips are the same token definition.

The card carries general event facts only:

- event title, as the organiser published it
- start and end
- venue, city and country
- organiser
- event URL
- data-source name, source URL, and the time the record was retrieved
- the number of registered participants, only when that source states a number, with the count's own source and retrieval time

It never carries an attendee name, handle, email, photo of a person, NexaID, or Bitcoin Cash address. The minter's own identity is used only for the one-per-identity check and is not written into the public metadata.

The same sentences are what a CashTokens wallet shows, via the BCMR `description` and the NFT type. Wally is not the BCH wallet. See below.

### Example: Crypto killer apps (ongoing, Nexa)

This is a real row in `data/events.json` (`89ced460e4ca`). The source record does not state a registered count, so the field is null. A count is never invented.

```json
{
  "niftyVer": "2.0",
  "title": "Crypto killer apps",
  "series": "Nordic Crypto · I was there",
  "author": "Nordic Crypto",
  "keywords": "event, Oslo, Norway, 2026, I was there",
  "info": "<p>Crypto killer apps. I was there. 2026-10-14T17:30:00+02:00 – 2026-10-14T18:30:00+02:00. Rosenkrantz' gate 7, 0159 Oslo (inngang fra Kristian IVs gate), Oslo, Norway. Organiser: Polyteknisk Forening. Event page: https://www.polyteknisk.no/program/crypto-killer-apps. Data source: Polyteknisk Forening (program) (https://www.polyteknisk.no/program/crypto-killer-apps), retrieved 2026-10-03T15:23:20+00:00. Registered participants: not stated in the source record.</p>",
  "license": "CC BY 4.0",
  "appuri": "https://nordiccrypto.no/events/89ced460e4ca/",
  "data": {
    "event_id": "89ced460e4ca",
    "kind": "ongoing",
    "kind_label": "I was there",
    "title": "Crypto killer apps",
    "start": "2026-10-14T17:30:00+02:00",
    "end": "2026-10-14T18:30:00+02:00",
    "venue": "Rosenkrantz' gate 7, 0159 Oslo (inngang fra Kristian IVs gate)",
    "city": "Oslo",
    "country": "Norway",
    "organiser": "Polyteknisk Forening",
    "event_url": "https://www.polyteknisk.no/program/crypto-killer-apps",
    "source": {
      "name": "Polyteknisk Forening (program)",
      "url": "https://www.polyteknisk.no/program/crypto-killer-apps",
      "retrieved_at": "2026-10-03T15:23:20+00:00"
    },
    "registered": {
      "count": null,
      "source_name": null,
      "source_url": null,
      "retrieved_at": null,
      "note": "The source record does not state a number of registered participants."
    }
  }
}
```

When a source does state a count, `registered.count` is that integer and `source_name`, `source_url` and `retrieved_at` name where it came from. Capacity, "spots left" and estimates are not a count and are not used. That rule already exists in `tools/event_select.py`.

The pre-event card for the same event uses `series` "Nordic Crypto · I'm going" and the sentence "I'm going." The Bitcoin Cash description is the same paragraph. Its on-chain commitment is the SHA-256 of those public facts, hex-encoded. That hash identifies the card, not a person.

## Bitcoin Cash

CashTokens (CHIP-2022-02, final) gives Bitcoin Cash a native non-fungible token: a 32-byte category, a commitment of 0 to 40 bytes, and a capability of `minting`, `mutable` or `none`. The category id is the genesis transaction. A minting-capability output can be spent to create further NFTs in that category. The child we give the minter is `none` (immutable). The minting output returns to the treasury.

Metadata does not fit in 40 bytes. CHIP-2022-10 BCMR is the JSON registry wallets read for name, description, symbol and icon. Sequential NFTs map a commitment to a type in that registry. This design uses one type per event per kind. The commitment is the content hash above, so a wallet that understands BCMR shows the same facts as Wally's `info`.

Wallets that receive and display CashTokens, and that can attach a BCMR when a token is created:

- Paytaca, including its public BCMR indexer
- Cashonize, which creates tokens and reads BCMR, including parsable NFTs
- Electron Cash, which imports BCMR metadata

Wally Wallet does not. In the current Wally source, `supportedBlockchains` in `NewAccountScreen.kt` offers Nexa, testnet Nexa and regtest Nexa. The Bitcoin Cash lines are commented out, so a new Wally account cannot be a BCH wallet. The BCH card is received in Paytaca, Cashonize or Electron Cash. It is not sent to Wally.

There is no TDPP equivalent to lean on for BCH. The mint transaction is built and broadcast by the treasury, not by the minter's wallet. The wallet only proves it controls the receive address.

## Artwork

The picture is generated from the event id, the kind (`pre` or `ongoing`) and the chain. The same inputs always produce the same PNG. The front says "I'M GOING" or "I WAS THERE", the chain, the title, the time, the city and country, and the organiser. A strip of bars is taken from the SHA-256 of those inputs so two events do not look identical. The back repeats the facts and is labelled as the back.

No photograph is composited. This repository has no rights-cleared event photography, and a photo of people is out of bounds even when a licence exists. If a later event has an image we have a licence to use, it may sit on the card only with the credit and the licence stored beside it. A missing licence means the image is not used. The generated geometry needs no external licence. The card text is credited to the event source inside `info`.

The `license` field on the token is CC BY 4.0 for the generated card. The event name and the facts stay attributed to the organiser and the listed source. Whether that licence is the one the owner wants is an open question.

Every copy of one card is the same zip, so on Nexa they share one subgroup and on Bitcoin Cash they share one commitment. The marketplace sees one card, not a portrait of the holder. A public edition number ("copy 12") would make each zip unique and would reveal mint order. It would still not name the holder. The prototype uses identical copies. Numbered editions are an open question.

Files for a live mint are hosted at `https://nordiccrypto.no/assets/nft/`, which is this site. The token's `appuri` and the BCMR web URI point at the event page. The prototype writes those images only when the feature flag is on.

## Mint flow

The minter pays nothing. The treasury signs and broadcasts. The wallet's job is to prove an identity and name the address that should receive the card and the fee float.

Nexa:

1. The button is shown on the ongoing hero while the event is running, and the pre-event button is shown on the upcoming card and the event page before the start. After the end, neither button is offered. The server checks the same window. The page clock is not the authority.
2. Wally answers a NexaID login (`nexid://` challenge, wallet returns an address and a signature). That proves control of the address. It is not written onto the NFT.
3. The worker refuses the mint if `SHA-256(chain | identity | event id)` is already stored. The kind is not part of the hash.
4. The worker builds one transaction: treasury inputs pay the network fee; a new NFT output of this card's subgroup goes to the NexaID address; about 1000 NEXA goes to that same address; the mint authority and the change stay with the treasury.
5. The worker broadcasts. The minter does not sign a payment. TDPP is the wrong tool here, because TDPP is how a wallet approves a transaction it pays for. A "watch for the card in Wally" state is enough.

Bitcoin Cash:

1. The same windows: pre-event before the start, ongoing while it runs.
2. The wallet signs a challenge for a Bitcoin Cash address (a signed message, or CashID where the wallet still speaks it). Paytaca, Cashonize and Electron Cash can hold the resulting NFT. Wally cannot, as shipped today.
3. The same one-per-event check, with the BCH address as the identity. The proof is a signature over `nordic-crypto-mint|bch|<event id>|<address>`, the message Electron Cash and CashConnect's `bch_signMessage` produce. The worker checks that signature when testnet signing is on. The browser WalletConnect pairing screen is not in this draft.
4. The worker spends the minting-capability NFT, sends an immutable NFT with this card's commitment to the address, returns the minting NFT to the treasury, and adds the sat float in the same transaction.

The prototype does none of this. The button opens a preview, a QR code and a link to this site. The label says nothing is minted and no wallet is opened.

## One per identity

Store only `SHA-256(chain | identity | event id)` in the mint Worker's D1, with the time of the first mint. A unique constraint on the hash closes the race. The card kind is not in the hash, so one NexaID gets one Nexa mint for that event. Do not store the raw NexaID, the raw address, or an IP address on that row. The worker may rate-limit by IP on the login request itself, in memory, and then forget it. This draft does not insert the claim row, because it does not sign. A later signer inserts the row in the same step as the broadcast.

NexaID is the Nexa identity. It is the address Wally returns from the login, not a second account.

Bitcoin Cash has no NexaID. The code default is one mint per address per event, plus the day and event caps, plus Turnstile when `TURNSTILE_SECRET` is set. Trade-offs:

- A signature over a challenge proves control of the address and needs no account. It is not a person. Someone with two wallets can mint twice. Someone who loses the wallet cannot mint again from a new address. That is the v1 check, and the worker verifies it on the testnet path. The page does not yet open a WalletConnect session; a wallet that can sign the challenge string can already satisfy the worker.
- An address string with no signature is refused once signing is on (`signature_invalid`). The flag-off path still returns the policy decision and does not sign.
- CashID is a documented login, but support across Paytaca, Cashonize and Electron Cash is uneven. It is not the default.
- Linking a NexaID to a BCH address would give one identity across chains and would put a cross-chain identifier in the worker. That is more surveillance than this feature needs. Not recommended.
- Doing nothing on BCH leaves the sat float open to a fresh address every time. Not acceptable once the float is real.

Nexa does not consume Bitcoin Cash. The two chains are separate caps and separate keys.

## Minting treasury

Two hot wallets, one page at `/treasury/` (and `/faucet/` redirects there). The mint card links to that page. It does not embed the address, the QR or the balance.

Custody is a small hot key on the server, with a low cap. jQrgen refills it by hand from his own wallet. The published refill address is that hot wallet. It is meant to stay at or under the target. The page says the wallet is intentionally small.

The key is not in this repository, not in the static site, and not in the iOS or Android app.

### Where the key lives

The key is a Cloudflare Worker secret on a separate Worker, `mintworker/`: `NEXA_HOT_KEY` and `BCH_HOT_KEY`.

Cloudflare injects those secrets when an isolate starts. A process restart, a new instance, and `wrangler deploy` keep the same secret. The handler calls `loadHotKey` and uses the value only on a future signer path. It is not written to D1, not returned, and not logged. Observability on this Worker is off. Losing the process loses nothing, because the secret store and D1 are managed. Deleting the Worker would delete the secret. A restart is a redeploy or a new isolate, not a delete.

This is the persistence mechanism. A seed phrase on paper, and a copy in a password manager, are not required and are not how a new instance recovers. An optional export into the operator's own password manager can stay as a personal note. The server never reads that note.

The public refill address is a non-secret var, `NEXA_HOT_ADDRESS` or `BCH_HOT_ADDRESS`. Until the operator sets it, the site shows the placeholder. The address is not a secret.

`mintworker/` is separate from `tipworker/` because the tip Worker accepts public form posts and its database holds newsletter email addresses. A spend key does not belong there. This Worker signs with `libnexa-ts` (Nexa NFT and the 1,000 NEXA airdrop) and `@bitauth/libauth` (CashTokens and the 10,000 sat airdrop). Signing runs only when `NC_EVENT_NFT=1` and `MINT_NETWORK=testnet`. `signs` on `/api/health` is true only in that case, and the network field is `testnet`. A mainnet address or a mainnet key is refused. The Worker has not been deployed. UTXOs come from the testnet electrum nodes (`testnet-electrum.nexa.org` and chipnet), not from the client. If those coins are missing, the mint stops with `utxo_unavailable`.

If a later signer cannot run in a Worker, that process still does not invent a second key. It reads the same platform secret, or, if the key must sit in a database, an encrypted-at-rest column in D1 or Postgres whose encryption key is itself a platform secret. The process loads that key on startup. A new instance picks up the same key. That database path is the fallback, not the v1 store. v1 is the Worker secret.

The operator installs a key with `mintworker/keygen.sh`. The script refuses unless `MINT_KEYGEN_I_AM_THE_OPERATOR=yes`. The operator creates the key in Wally (Nexa) or Electron Cash (Bitcoin Cash), which know the address format. The script reads the key with echo off and pipes it to `wrangler secret put`. It writes no file and it does not derive an address. It is not part of the build, and it has not been run for this draft. No real key exists in git.

Until the address vars are set, the published addresses are placeholders:

- `placeholder:nexa:nordic-crypto-minting-treasury`
- `placeholder:bch:nordic-crypto-minting-treasury`

They are not valid payment addresses. The page says so. Do not send funds to them.

### Threat model

A stolen hot key, or a deleted Worker secret, loses at most the coins sitting in that hot wallet. The cap is the target: about 50,000 NEXA and about 0.002 BCH (200,000 sats). jQrgen's own wallet is untouched. The static site cannot spend. The placeholder strings in git are not keys.

The code cannot refuse an inbound payment. If a balance is observed above the target, the decision is still allowed when the other caps pass, and `above_target` is true so the page can say to sweep the excess back. The operator sends only up to the target.

A leak of the tip Worker does not reveal this key. A bug that logs request bodies must not log the mint identity. The health route returns booleans only.

### Refill

jQrgen sends NEXA or BCH from his own wallet to the hot address, up to the target and not beyond. The treasury page and `treasury.json` show that address as `refill_address` (the same string as `address`) and the target. When the observed balance is at or under the reserve, or too small for one mint, or unknown, the worker refuses and `needs_funding` is true. A missing balance fails closed. It does not trust a balance posted by the client. This prototype still shows sample balances from `data/event_nft_fixture.json`.

### Public history

Every refill and every mint is a public row: time, kind (`refill` or `mint`), amount, transaction id, and an explorer link. A mint also carries the event id. The row does not carry a name, a NexaID, or a funder label. The transaction id is already public on the chain; the page does not add who sent it.

The mint worker stores that ledger in D1 (`treasury_ledger`) when a testnet broadcast is accepted. A refill is recorded two ways. The hourly cron reads the hot address history from the testnet indexer and keeps an incoming payment whose inputs are someone else's address and whose amounts are integer satoshis. A float amount is skipped, because some explorers quote whole coins and a guessed conversion would be wrong. The same cron also accepts `REFILL_FEED`, a JSON document `{nexa:[], bch:[]}` of `{txid, amount, at}` in satoshis, and ignores any name or from field on those objects. `balance_snapshot` is written in that same hourly cron from the observed hot balance.

The static page, while the worker is not live, draws the same shape from the sample ledger in the fixture. `/treasury/` shows a left-aligned table and an SVG line chart per chain. `/api/v1/treasury.json` includes `history` and `balance_series`. `/api/v1/treasury/history.json` is those two fields on their own. The worker serves the same pair at `/api/treasury` and `/api/treasury/history`. Nexa amounts in the public JSON are NEXA (the ledger stores satoshis, 100 per NEXA). Bitcoin Cash amounts stay in satoshis.

### What one mint costs

The float dominates. The network allowance is a configuration ceiling. The live worker replaces it with the fee of the transaction it actually builds, and refuses the mint if that fee is above the ceiling.

| | Network allowance | Fee float to the minter | Drawn per mint | Where the numbers live |
| --- | --- | --- | --- | --- |
| Nexa | 20 NEXA | 1000 NEXA | 1020 NEXA | `mintworker/caps.json` |
| Bitcoin Cash | 1,500 sats | 10,000 sats | 11,500 sats | the same file |

1000 NEXA is the owner's figure for later transfer fees. 10,000 sats is the proposed BCH equivalent: enough for several token moves, small enough that the one-per-address rule matters. Both are config. A plain BCH output's dust is 546 sats; a token output is larger, which is why the network allowance sits above that.

The treasury page shows the balance, the hot-balance target, the mint caps, the number of mints paid, the network cost, the float, and the total drawn per mint. It says the hot wallet is intentionally small and names the refill address. Below that it shows the refill and mint table and the balance chart.

### Caps

`mintworker/caps.json` is the only copy of these numbers. The Worker and the treasury page both read it. jQrgen accepted the defaults below.

| | Hot target | Reserve (refuse at or under) | Low-water | Per event | Per day | One mint draws |
| --- | --- | --- | --- | --- | --- | --- |
| Nexa | 50,000 NEXA | 2,040 NEXA (2 × 1,020) | 10,200 NEXA (10 × 1,020) | 20 mints (20,400 NEXA) | 15 mints (15,300 NEXA) | 1,020 NEXA |
| Bitcoin Cash | 200,000 sats (0.002 BCH) | 23,000 sats (2 × 11,500) | 57,500 sats (5 × 11,500) | 8 mints (92,000 sats) | 6 mints (69,000 sats) | 11,500 sats |

A full Nexa hot wallet covers about 49 mints. The day cap of 15 and the event cap of 20 stop one day or one event from taking it. Bitcoin Cash is tighter because 0.002 BCH is a small purse.

### When the treasury runs low

`status` is `ok`, `low` or `empty`.

- `empty` when the balance is missing, cannot cover one more mint, or is at or under the reserve. The mint button becomes "Treasury empty, fund it" and links to `/treasury/`. No mint is attempted. `needs_funding` is true.
- `low` when the balance is under the low-water mark and still above the reserve. Minting still works. The card says the treasury is low and links to the page. `needs_funding` is true.
- `ok` otherwise. `needs_funding` is false. `above_target` may still be true.

The top-level `status` is the worse of the two chains. Identity, event-cap and day-cap refusals do not by themselves set `needs_funding` when the balance is otherwise ok.

Sample balances in the fixture (not a live lookup): 37,960 NEXA and 137,000 sats, which is where the sample ledger ends. Both sit under the target and above the low-water mark, so the sample app prompt stays off.

### Abuse

The float makes this a faucet. The limits, enforced in `mintworker/src/policy.js`:

- one mint per NexaID per event, and one per Bitcoin Cash address per event (the D1 unique hash; kind does not add a mint)
- the per-day and per-event caps in the table above
- the reserve, so the last coins are not spent
- Turnstile on Bitcoin Cash when `TURNSTILE_SECRET` is set
- an in-memory IP limit on the login endpoint, still to be wired with the signer
- the server re-checks that the event is actually upcoming or ongoing

A person who attends many events can still collect many floats. A monthly cap per identity is an open question. Whether the one-per-event rule should become one-per-kind again is an open question.

### Apps

The iOS app (public TestFlight, including Apple TV) and the Android app are not in this repository. They should read `GET /api/v1/treasury.json`.

Show a funding prompt only when `needs_funding` is true, that is when `status` is `low` or `empty`. When `status` is `ok`, show nothing. Use `nexa.needs_funding` and `bch.needs_funding` so the prompt can name the chain. The prompt links to `page` (`/treasury/`). The app does not embed a key and does not construct a mint transaction.

The discovery document lists the endpoint when the flag is on. The human page at `/api/` lists it with the other GET routes.

## Prototype

Off by default. It turns on when `NC_EVENT_NFT=1` or when `queue/approved.json` has `features.event_nft` set. The public build does neither, so the live site does not grow a treasury page or a mint button until the owner asks.

With the flag on, in every site language, left aligned:

- The ongoing hero has "Mint event NFT in Wally" and "Mint event NFT on Bitcoin Cash".
- An upcoming card, the calendar row, and `/events/<id>/` have the pre-event pair, "I'm going".
- Opening a button shows the generated image, the fields Wally or a CashTokens wallet would show, the fee-float sentence, the one-per-identity sentence, and a QR code of a link on this site. The static page does not broadcast. The mint worker broadcasts on testnet when the flag is on.
- If that chain is `empty`, the button is the funding link instead.
- `/treasury/` shows both placeholder addresses, both QR codes, the sample balance, the hot-wallet target, the event and day caps, the mint count and the cost. It says the hot wallet is intentionally small. It also shows the refill and mint table and a balance chart for each chain. `/faucet/` redirects there. The nav and the footer link to it.
- `/api/v1/treasury.json` is the document above, with `prototype: true`, `history` and `balance_series`. `/api/v1/treasury/history.json` repeats the history and the series.

Copy is in `i18n/event_nft_strings.py` for all 21 languages. The brand name stays Nordic Crypto.

## Privacy and security

The public token is the event, not the person. The worker's dedupe table is a hash. Logs for a mint should keep the event id, the chain and the success or refusal, not the address and not the IP. The hot key never appears in a log or a response.

Abuse of the float is limited by the caps above. The worker must not mint when the event is outside its window, even if a modified page still shows the button. The static site does not mint. The worker will sign a testnet transaction when the flag is on. It has not been deployed, and a mainnet broadcast is refused. A confirming testnet mint still needs a funded hot wallet; the public nodes parsed a signed mint and rejected it for missing inputs.

## Open questions for the owner

Custody is decided: a small hot key in the Worker secret store, refilled by hand, persisted across redeploy. The cap defaults in `mintworker/caps.json` are accepted. The Bitcoin Cash check is a signature over the challenge, verified by the worker on the testnet path; the browser WalletConnect session is not built. These are still open:

1. Is there a monthly cap per identity, on top of the day cap and the one-per-event rule?
2. Keep one mint per NexaID per event (what the code does), or allow the pre-event card and the ongoing card as two mints.
3. Identical cards for every minter (this design), or public edition numbers that do not name the holder.
4. Is CC BY 4.0 the licence for the generated card?
5. The prototype adds `/events/<id>/` while the flag is on. Should that page stay when minting goes live?
6. The apps need a small change to read `needs_funding`. The app source is not in this repo.
