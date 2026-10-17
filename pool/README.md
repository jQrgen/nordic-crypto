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

RPC credentials stay out of the file. The pool reads the hot wallet's cookie (`/var/lib/nexapool/hotwallet/.cookie`). `NEXAPOOL_RPC_USER` and `NEXAPOOL_RPC_PASSWORD` override the cookie when both are set. An encrypted wallet uses `passphrase_file`, mode `0600`, owned by `nexapool`. The process refuses a cookie or passphrase file that is group- or world-readable, or a symlink. Neither file is in this repository.

The pool pays from a hot wallet, not from the cold nexad wallet. `hot_wallet_max` (default `5000000.00` NEX) is a cap: if `getbalance` is above it, the payout pass does not start a new send. Rows that are already reserved are still reconciled. Sweep the excess to a cold wallet the pool user cannot sign for. The systemd unit runs as `nexapool` and does not read `/var/lib/nexa`.

`coinbase_address` is required and must belong to the hot wallet. The process will not start while it is empty. Block reward is the coinbase output that pays that address. Other coinbase outputs are not credited. Miners are not paid from the coinbase directly.

`node.url` and the API listen address must be loopback. The RPC client refuses HTTP redirects, so a redirect cannot carry the cookie off the machine.

Amounts use nexad's two decimal places. The default minimum payout is `1000000.00` NEX, which is 100,000,000 subunits. Coinbase maturity is at least 5001 confirmations, which is when nexad's wallet will spend the coinbase (`COINBASE_MATURITY + 1`). A lower value is rejected. A payout is signed before it is broadcast. The txidem, the raw hex, and the input outpoints are stored on the reservation, and a later pass broadcasts that same hex if that txidem is absent or still at 0 confirmations. Wallet flags do not skip that rebroadcast. A row that has a txidem is never signed again. A payout is marked sent only after `payout_confirmations` (default 1), and a later pass rechecks it. If that transaction disappears, the same hex is broadcast again. The coins can be paid once more only when a different txidem has spent an input and that spend has `release_conflict_depth` confirmations (default 10, minimum 6). Abandoning the transaction does not do that. The inputs stay locked until the stored txidem reaches that depth or the deep spend releases the row. A reorg deeper than `release_conflict_depth` is an accepted risk: the pool may already have signed a second payout, and both can be valid if the competing spend disappears. The PPLNS window is two network difficulties. Payouts run about once an hour, under a process lock. A reservation that never received a txidem is held for review and is not signed. Startup exits if the reserved outpoints cannot be locked.

`nexapool review -config /etc/nexapool/nexapool.toml` lists those rows. `-id N -resolve complete` marks one sent when the stored txidem is in the wallet or in a block and has enough confirmations. `-id N -resolve release -confirm <txidem>` returns the coins only when that txidem is the one stored on the row and a different txidem has spent an input with at least `release_conflict_depth` confirmations. `-confirm none` is accepted only when the row was never signed and the reservation is at least `release_none_min_age` old (default 24 hours). `nexapool inputs` lists `payout_inputs` rows that are no longer held, and `-prune` deletes them. `nexapool comment -text` searches wallet comments and does not pay or release.

## Stratum

The listener is newline-delimited JSON. `mining.subscribe` returns the set-difficulty and notify subscriptions, an 8-byte extranonce, and an extranonce2 size of 8, so the solution nonce is 16 bytes. `mining.authorize` takes the Nexa address as the username. A worker is `address.worker` or `address/worker`. The password is ignored.

`mining.notify` is the echelon five-tuple: job id, header commitment, nBits, an 8-byte big-endian timestamp, and a clean flag. When `getminingcandidate` carries a real `previousBlockHash`, a sixth parameter is appended in the display order the node returns. Miners reverse it before the Tailstorm mix, the same way nexa-miner does. A zero previous hash stays the pre-fork job. `tailstorm = on` or `off` forces the mode, and `tailstorm_activation` is compared with the node's median time past, not the wall clock. `clean: true` retires every previous job id. `mining.submit` accepts four parameters (user, job, nonce, time) or WildRig's five (user, job, extranonce2, time, nonce). The submitted time has to match the job.

Share difficulty uses the Bitcoin difficulty-1 target. New connections start at 0.2. Variable difficulty aims at a share about every 15 seconds and stays between 0.05 and 4096. For the first three minutes it retargets every 10 seconds so a fast miner can climb; after that it waits a minute and four samples. `mining.suggest_difficulty` is ignored until authorize, and it cannot set a difficulty below the session's current value or the configured floor. One IP is limited to 16 connections. Submits are rate limited (`submit_rate` defaults to 128 per second). Rate-limit misses during `submit_grace` do not ban. A run of bad shares does. A client that does not read is disconnected instead of stalling the next job.

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

The NexaPow tests use the two full hashing examples from the echelon specification. The ledger tests cover a single payment, a crash after the signed transaction is stored, a crash after broadcast, an abandoned transaction that is not signed again, a depth-0 payout that is rebroadcast, a conflicting spend that is signed again only after `release_conflict_depth`, immature coins, and a mature credit that an orphan must not delete. The pool tests submit the official vector as a block, check the 1% split, and stop a payout that would spend the wallet reserve.

## Site

English is at `/`. The other site languages are under `/nn/`, `/nb/`, and the rest of the same list as nordiccrypto.no. Regenerate after editing `web/locales.json`:

```sh
cd pool
go run ./cmd/poolsite -out web/public -assets ../assets
```

The page reads `/api/v1/stats` and `/api/v1/blocks`. It does not contain sample hashrate figures.

## Deploy on nexa-pool-1

Host `167.233.122.241`, Ubuntu 24.04. nexad is already installed as the systemd service `nexad`, user `nexa`, datadir `/var/lib/nexa/.nexa`. Do this on the server. This repository does not deploy it.

1. Build on a machine with Go 1.27.2, from this repository:

   ```sh
   cd pool
   go build -o nexapool ./cmd/nexapool
   go run ./cmd/poolsite -out web/public -assets ../assets
   go test ./...
   ```

2. Copy `nexapool` to `/usr/local/bin/nexapool` on the server. Copy `web/public/` to `/var/www/nexapool/`. Copy `deploy/nexapool.service` to `/etc/systemd/system/nexapool.service` and `deploy/nginx-pool.nordiccrypto.no.conf` to `/etc/nginx/sites-available/pool.nordiccrypto.no`.

3. Create the runtime directories and install the config:

   ```sh
   sudo useradd --system --home-dir /var/lib/nexapool --shell /usr/sbin/nologin nexapool
   sudo install -d -o nexapool -g nexapool -m 750 /var/lib/nexapool /var/lib/nexapool/hotwallet /etc/nexapool
   sudo cp pool/config.example.toml /etc/nexapool/nexapool.toml
   sudo chown root:nexapool /etc/nexapool/nexapool.toml
   sudo chmod 640 /etc/nexapool/nexapool.toml
   ```

   Edit `fee_address` and `coinbase_address`. Both are required. Use addresses Nordic Crypto controls. Run the hot-wallet nexad as `nexapool`, datadir `/var/lib/nexapool/hotwallet`, RPC on `127.0.0.1` only. Leave the cold wallet under user `nexa` in `/var/lib/nexa`, and do not give `nexapool` read access to it. Point `cookie_file` at the hot wallet cookie, mode `0600`, owner `nexapool`. If the wallet is encrypted, put the passphrase in `/etc/nexapool/wallet.passphrase` (mode `0600`, owner `nexapool`). Leave the RPC user and password unset so the pool reads the cookie. Keep the hot wallet balance under `hot_wallet_max` by sweeping to cold storage.

4. Confirm both nexad RPC ports listen on `127.0.0.1` only, with `server=1`. Do not open 7227, 7228, or 8080 in the firewall. Port 7228 is nexad's P2P port; outbound peering works with it closed. Open 80, 443, and 3333.

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

   `node_online` should become true once nexad answers `getmininginfo`. The first payout cannot happen until a block this pool found has 5001 confirmations and the mature balance is at least the minimum. Leave the default 1 NEX reserve in the hot wallet so transaction fees have somewhere to come from. This repository does not start the service.

7. A miner connects with its Nexa address as the username, for example:

   ```sh
   lolMiner --algo NEXA --pool stratum+tcp://pool.nordiccrypto.no:3333 --user nexa:ADDRESS
   ```
