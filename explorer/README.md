# Nordic Crypto Explorer

Bitcoin Cash and Nexa explorer at [explorer.nordiccrypto.no](https://explorer.nordiccrypto.no). It uses the same North Sea, sea foam and gold, and the same type, as [nordiccrypto.no](https://nordiccrypto.no).

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

## Routes

Blocks, transactions, addresses and tokens are query strings, so the static export can serve them:

- `/bch/block/?height=972620`
- `/bch/tx/?txid=` a 64-character id
- `/bch/address/?address=` a cashaddr
- `/bch/token/?id=` a token category or group id
- `/nexa/capd/` the CAPD message pool, and `/nexa/capd/?hash=` one message

CAPD is Nexa-only, so it is linked from the Nexa section nav. The page asks the same Rostrum servers, in the same order, for `capd.info`, `blockchain.capd.info`, and `capd` with the parameter `info`. Rostrum 14.0.1 does not implement those methods (JSON-RPC −32601). The page then says so and leaves the figures blank. It does not invent a pool. A read-only `capd.info` / `capd.list` / `capd.get` on Rostrum, matching nexad’s `capd` RPC, is what would fill them in. `capd list` is ordered from lowest priority to highest; the page reads the high-priority end and sorts that by creation time.

`/bch/block/972620/` is rewritten to the query form by `deploy/nginx-explorer.conf`. The deploy workflow does not install that file. Until nginx is reloaded with it, the page script in the 404 shell performs the same redirect.

## Run it

```sh
npm install
npm run dev
```

Open http://127.0.0.1:43123. Bitcoin Cash is the front page. Nexa is at `/nexa`.

```sh
npm test
npm run lint
npm run build
```
