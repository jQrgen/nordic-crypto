# Nordic Crypto Explorer

Bitcoin Cash, Nexa and Bitcoin explorer at [explorer.nordiccrypto.no](https://explorer.nordiccrypto.no). It uses the same North Sea, sea foam and gold, and the same type, as [nordiccrypto.no](https://nordiccrypto.no).

Figures are read in the browser. The site is a Next.js static export: there is no Node server in production. Each page opens an Electrum WebSocket, asks the primary server, and moves to the next server if that one does not answer within a few seconds. The line under the title names the server that answered. Fiat prices come from CoinGecko; if that request fails, amounts stay in coins.

## Servers

Checked on 12 Oct 2026. A browser `Origin` of `https://explorer.nordiccrypto.no` completed the WebSocket handshake on each of these:

| Chain | Order | URL |
|---|---|---|
| Bitcoin Cash | Primary | `wss://electrum-bch.nordiccrypto.no:50004` (Fulcrum) |
| Bitcoin Cash | Same host, port 443 | `wss://electrum-bch.nordiccrypto.no` |
| Bitcoin Cash | Public fallback | `wss://bch.imaginary.cash:50004` |
| Bitcoin Cash | Public fallback | `wss://cashnode.bch.ninja:50004` |
| Nexa | Primary | `wss://electrum-nexa.nordiccrypto.no:20004` (Rostrum) |
| Nexa | Same host, port 443 | `wss://electrum-nexa.nordiccrypto.no` |
| Nexa | Public fallback | `wss://electrum.nexa.org:20004` |

`wss://electroncash.de:60002` and `wss://bch.loping.net:50004` did not accept a connection from this network, so they are not used. Port 443 is the same nginx TLS vhost as the published Electrum port, with no extra path. The news site lists the published ports on [nordiccrypto.no/api/](https://nordiccrypto.no/api/).

## Bitcoin

Bitcoin (`/btc`) is read from the public [mempool.space REST API](https://mempool.space/docs/api/rest), not from a node of ours. The browser calls `https://mempool.space/api` directly; it answers with `Access-Control-Allow-Origin: *`. The client is `lib/mempool-space.ts`.

- mempool.space rate-limits per IP and does not publish the limit. Too many requests get HTTP 429; repeated abuse can get an IP banned. Replies are cached in memory (30 s for tip, fees, mempool, addresses and transactions; 10 min for a block by hash), failures are not cached, and no page polls.
- Each page makes a handful of calls: overview 3 (`/v1/blocks`, `/v1/fees/recommended`, `/mempool`), transaction 2, address 2, block 3 to 4.
- The [terms of service](https://mempool.space/terms-of-service) give the data "as is", with no warranty of accuracy or uptime. They ask for no attribution; the footer and overview credit mempool.space anyway. The mempool name and logos are trademarks, so the explorer names mempool.space in text and uses none of its logos.
- If traffic grows past what the public API tolerates, point `MEMPOOL_API` at a self-hosted mempool instance.

## Routes

Blocks, transactions, addresses and tokens are query strings, so the static export can serve them:

- `/bch/block/?height=972620`
- `/bch/tx/?txid=` a 64-character id
- `/bch/address/?address=` a cashaddr
- `/bch/token/?id=` a token category or group id
- `/btc/block/?hash=` a 64-character block hash (Bitcoin only)

`/bch/block/972620/` is rewritten to the query form by `deploy/nginx-explorer.conf`. The deploy workflow does not install that file. Until nginx is reloaded with it, the page script in the 404 shell performs the same redirect.

## Run it

```sh
npm install
npm run dev
```

Open http://127.0.0.1:43123. Bitcoin Cash is the front page. Nexa is at `/nexa`, Bitcoin at `/btc`.

```sh
npm test
npm run lint
npm run build
```

The Nexa tokens page reads `/data/nexa-tokens.json`, written hourly on the server by `deploy/token-stats.mjs` (`token-stats.service` + `token-stats.timer`) from the [explorer.nexa.org Token Tracker](https://explorer.nexa.org/tokens). nginx serves it from `/var/www/explorer-data/` (see `deploy/nginx-explorer.conf`).
