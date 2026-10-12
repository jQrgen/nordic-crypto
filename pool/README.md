# Nordic Crypto Nexa pool

A small pool for Nexa. Miners speak the echelon stratum dialect used by lolMiner, BzMiner, Rigel and SRBMiner. The pool checks NexaPow, submits blocks to a local nexad 2.2, and pays PPLNS from that node's wallet after the coinbase has matured.

The fee is 1%. It is credited to `fee_address` and paid out under the same rules as every other address. The public site is https://pool.nordiccrypto.no. Stratum is `stratum+tcp://pool.nordiccrypto.no:3333`.

Nothing here deploys itself. The steps for `nexa-pool-1` are at the bottom.

## Layout

- `cmd/nexapool` is the process: stratum, the payout loop, and the JSON API.
- `cmd/poolsite` writes the static site into `web/public`.
- `internal/nexa` is NexaPow, cashaddr, amounts, and the RPC client.
- `internal/account` is the PPLNS split, the fee, and the payout state machine.
- `internal/store` is the SQLite ledger.
- `deploy/` holds the systemd unit, an env file with no secrets, and an nginx sample.

## Configuration

Copy `config.example.toml`. The process will not start until `fee_address` is a valid Nexa address. A zero `fee_percent` is read as the default 1%, so a blank field cannot turn the fee off.

RPC credentials stay out of the file. Prefer nexad's cookie (`/var/lib/nexa/.nexa/.cookie` on the pool server). `NEXAPOOL_RPC_USER` and `NEXAPOOL_RPC_PASSWORD` override the cookie when both are set. An encrypted wallet uses `passphrase_file`, mode `0600`, owned by `nexa`. That file is not in this repository.

`coinbase_address` must belong to the node wallet when it is set. Miners are not paid from the coinbase directly. The wallet receives the block, and the payout loop sends from the wallet.

Amounts use nexad's two decimal places. The default minimum payout is `1000000.00` NEX, which is 100,000,000 subunits. Coinbase maturity defaults to 5000 confirmations. The PPLNS window is two network difficulties. Payouts run about once an hour.

## Stratum

The listener is newline-delimited JSON. `mining.subscribe` returns the set-difficulty and notify subscriptions, an 8-byte extranonce, and an extranonce2 size of 8, so the solution nonce is 16 bytes. `mining.authorize` takes the Nexa address as the username. A worker is `address.worker` or `address/worker`. The password is ignored.

`mining.notify` is the standard and BzMiner shape: job id, header commitment, nBits, an 8-byte big-endian timestamp, and a clean flag. `mining.submit` accepts four parameters (user, job, nonce, time) or WildRig's five (user, job, extranonce2, time, nonce).

Share difficulty uses the Bitcoin difficulty-1 target. New connections start at 0.2. Variable difficulty aims at a share about every 15 seconds, waits at least a minute and four samples, and stays between 0.05 and 4096.

## API

All of these are `GET` and unauthenticated.

- `/api/v1/stats`
- `/api/v1/blocks`
- `/api/v1/miners`
- `/api/v1/address/{address}`
- `/api/v1/payouts`
- `/api/v1/health`

`pool_hashrate`, `miners`, `network_hashrate`, and `pool_share` are null when the node is offline. Block links point at `https://explorer.nordiccrypto.no/nexa/block/{height}`.

## Tests

```sh
cd pool
go test ./...
```

The NexaPow tests use the two full hashing examples from the echelon specification. The ledger tests cover a single payment, a timeout that must not send twice, a failed send that may be retried once, immature coins, and a mature credit that an orphan must not delete. The pool tests submit the official vector as a block, check the 1% split, and stop a payout that would spend the wallet reserve.

## Site

English is at `/`. The other site languages are under `/nn/`, `/nb/`, and the rest of the same list as nordiccrypto.no. Regenerate after editing `web/locales.json`:

```sh
cd pool
go run ./cmd/poolsite -out web/public -assets ../assets
```

The page reads `/api/v1/stats` and `/api/v1/blocks`. It does not contain sample hashrate figures.

## Deploy on nexa-pool-1

Host `167.233.122.241`, Ubuntu 24.04. nexad is already installed as the systemd service `nexad`, user `nexa`, datadir `/var/lib/nexa/.nexa`. Do this on the server. This repository does not deploy it.

1. Build on a machine with Go 1.22 or newer, from this repository:

   ```sh
   cd pool
   go build -o nexapool ./cmd/nexapool
   go run ./cmd/poolsite -out web/public -assets ../assets
   go test ./...
   ```

2. Copy `nexapool` to `/usr/local/bin/nexapool` on the server. Copy `web/public/` to `/var/www/nexapool/`. Copy `deploy/nexapool.service` to `/etc/systemd/system/nexapool.service` and `deploy/nginx-pool.nordiccrypto.no.conf` to `/etc/nginx/sites-available/pool.nordiccrypto.no`.

3. Create the runtime directories and install the config:

   ```sh
   sudo install -d -o nexa -g nexa -m 750 /var/lib/nexapool /etc/nexapool
   sudo cp pool/config.example.toml /etc/nexapool/nexapool.toml
   sudo chown root:nexa /etc/nexapool/nexapool.toml
   sudo chmod 640 /etc/nexapool/nexapool.toml
   ```

   Edit `fee_address`. Use an address Nordic Crypto controls. If the wallet is encrypted, put the passphrase in `/etc/nexapool/wallet.passphrase` (mode `0600`, owner `nexa`) and set `passphrase_file`. Leave the RPC user and password unset so the pool reads `/var/lib/nexa/.nexa/.cookie`. The pool runs as `nexa`, the same user nexad uses, so it can read that cookie. Do not chmod the cookie to be world-readable.

4. Confirm nexad listens on `127.0.0.1:7227` only, with `server=1`. Do not open 7227 or 8080 in the firewall. Open 80, 443, and 3333.

5. Point nginx at the site and ask certbot for a certificate for `pool.nordiccrypto.no`. The certificate stays on the server.

   ```sh
   sudo ln -s /etc/nginx/sites-available/pool.nordiccrypto.no /etc/nginx/sites-enabled/
   sudo nginx -t && sudo systemctl reload nginx
   sudo certbot --nginx -d pool.nordiccrypto.no
   ```

6. Start the pool and check it locally:

   ```sh
   sudo systemctl daemon-reload
   sudo systemctl enable --now nexapool
   curl -sS http://127.0.0.1:8080/api/v1/health
   ```

   `node_online` should become true once nexad answers `getmininginfo`. The first payout cannot happen until a block this pool found has 5000 confirmations and the mature balance is at least the minimum. Leave the default 1 NEX reserve in the wallet so transaction fees have somewhere to come from.

7. A miner connects with its Nexa address as the username, for example:

   ```sh
   lolMiner --algo NEXA --pool stratum+tcp://pool.nordiccrypto.no:3333 --user nexa:ADDRESS
   ```
