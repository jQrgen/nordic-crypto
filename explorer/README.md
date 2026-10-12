# Nordic Crypto Explorer

Design prototype for a Bitcoin Cash and Nexa explorer at [explorer.nordiccrypto.no](https://explorer.nordiccrypto.no). It uses the same North Sea, sea foam and gold, and the same type, as [nordiccrypto.no](https://nordiccrypto.no).

The figures are samples for the layout, drawn as of 12 October 2026. They are not read from a node.

## Run it

```sh
npm install
npm run dev
```

Open http://127.0.0.1:43123. Bitcoin Cash is the front page. Nexa is at `/nexa`.

Useful paths:

- `/nexa/block/1168213` a quiet block
- `/nexa/tx/agnar-250` a group-token transfer
- `/nexa/address/sigrid` an address with tokens
- `/bch/tx/fjord-send` a CashToken transfer
- `/search?q=Sigrid` a name on both chains
- `/design/loading`, `/design/catching-up`, `/design/empty-mempool`, `/design/fault`

```sh
npm test
npm run lint
```
