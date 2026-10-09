# Electrum server (BCH and Nexa)

Nordic Crypto runs its own Electrum server for Bitcoin Cash and Nexa. Wallets and apps (voter.cash, the event NFT prototype) can read chain state from it instead of depending on public servers.

It was set up on 9 October 2026, after voter.cash could not load the block height: its primary server, `electrs.bitcoinunlimited.info`, accepted connections but did not answer, and its fallback, `bitcoincash.network`, was down.

## Endpoints

| Chain | WebSocket (wss) | TLS (raw TCP) | Behind it |
|---|---|---|---|
| Nexa | `wss://electrum-nexa.nordiccrypto.no:20004` | `electrum-nexa.nordiccrypto.no:20002` | Rostrum on `127.0.0.1:20003` (ws) and `127.0.0.1:20001` (TCP) |
| Bitcoin Cash | `wss://electrum-bch.nordiccrypto.no:50004` | `electrum-bch.nordiccrypto.no:50002` | Rostrum on `127.0.0.1:50003` (ws) and `127.0.0.1:50001` (TCP) |

These are the standard Electrum ports (Rostrum and Fulcrum use the same defaults). Port 443 also answers wss for both hostnames, for clients set up while the servers were behind a Cloudflare Tunnel (9 October 2026, before the same day's move to direct access).

nginx on the server terminates TLS with a Let's Encrypt certificate for both hostnames and forwards to Rostrum on localhost. The DNS records in Cloudflare are A/AAAA records to the server, **DNS only** (not proxied): Cloudflare cannot proxy ports 20002/20004/50002/50004.

## Server

| | |
|---|---|
| Provider | Hetzner Cloud, Falkenstein (`fsn1`) |
| Server | `electrum-1`, CX43 (8 vCPU, 16 GB RAM, 80 GB disk), Ubuntu 24.04 |
| Data volume | `electrum-data`, 300 GB, mounted at `/mnt/HC_Volume_107087011` |
| Firewall | `electrum-ssh-only` (name kept): inbound SSH 22, ICMP, HTTP 80 (certificate renewal), 443, 20002, 20004, 50002, 50004 |
| Addresses | `91.99.122.75`, `2a01:4f8:c01e:36d9::1` |
| Cost | About €33.15 a month (€15.99 server, €17.16 volume), billed hourly |

It started as a CX33 (8 GB RAM). On 9 October 2026 it ran out of memory with BCHN at `dbcache=3000` and both Rostrum instances indexing: no free RAM, disk thrashing and SSH timing out. It was moved to a CX43 the same day, with BCHN at `dbcache=4000` and a 4 GB swap file (`/swapfile`, `vm.swappiness=10`). The disk was not enlarged, so the server can still go back to a CX33. Check memory use after the first sync (`free -m`, `ps -eo rss,comm --sort=-rss | head`) before downgrading, and lower `dbcache` to 1000 if you do.

The hostnames are one level below `nordiccrypto.no` (`electrum-bch`, not `bch.electrum`). That was needed for Cloudflare's free certificate while the servers were behind the tunnel, and stays as the public name.

Rostrum itself only listens on localhost. nginx is the only thing facing the internet on the Electrum ports. The servers are not behind Cloudflare's proxy, so there is no DDoS protection in front of them.

## What runs

Everything runs as the system user `electrum`. Each part is a systemd service.

| Service | Software | Config | Data |
|---|---|---|---|
| `bchn` | Bitcoin Cash Node 29.2.0, `/opt/bchn` | `bchn/bitcoin.conf` | `bchn/` |
| `rostrum-bch` | Rostrum 14.0.1 built with `--features bch`, `/usr/local/bin/rostrum-bch` | flags in the unit file, RPC login in `/etc/rostrum-bch.env` | `rostrum-bch/` |
| `nexad` | Nexa 2.2.0.0, `/opt/nexa` | `nexa/nexa.conf` | `nexa/` |
| `nginx` | TLS front end: wss on 20004/50004/443, TLS over TCP on 20002/50002, ACME on 80 | `/etc/nginx/conf.d/electrum-wss.conf`, `/etc/nginx/stream.d/electrum-tls.conf` | |
| `certbot` (timer) | Let's Encrypt certificate `electrum` for both hostnames, renewed automatically, reloads nginx | `/etc/letsencrypt/` | |

Paths in the Config and Data columns are under the data volume.

`nexad` starts its own bundled Rostrum (`-electrum=1`), listening only on localhost: TCP `20001`, WebSocket `20003`. BCHN has no built-in Electrum server, so Rostrum for BCH runs as its own service against BCHN's RPC on `127.0.0.1:8332`, listening only on localhost: TCP `50001`, WebSocket `50003`. It opens those ports once BCHN has caught up with the chain.

The BCHN RPC password is generated on the server and kept only in `bitcoin.conf` and `/etc/rostrum-bch.env` (both mode 600). The certificate's private key is in `/etc/letsencrypt/` (root only). Neither is in this repo. `cloudflared` is still installed but disabled; the tunnel `electrum-1` is no longer used.

## Checking it

```sh
ssh root@<electrum-1>
systemctl status bchn rostrum-bch nexad nginx

V=/mnt/HC_Volume_107087011
/opt/bchn/bin/bitcoin-cli -datadir=$V/bchn -conf=$V/bchn/bitcoin.conf getblockcount
sudo -u electrum /opt/nexa/bin/nexa-cli -datadir=$V/nexa -conf=$V/nexa/nexa.conf getblockcount
journalctl -u rostrum-bch -f
```

The server's address is in the Hetzner console. The Hetzner API token is kept in the operator's macOS Keychain as `hetzner-api-token`.

## Public status

The `/api` page lists both endpoints and checks them live from the reader's browser: `tools/electrum_status.js` sends `server.version` and `blockchain.headers.subscribe` over WebSocket and shows up or down, the block height, the response time and the Rostrum version. A failed row means that browser could not reach the server within 8 seconds.

## Who uses it

- **voter.cash (BCH):** through `@bitcoinunlimited/votepeerjs`, [bitcoinunlimited/votepeerjs!58](https://gitlab.com/bitcoinunlimited/votepeerjs/-/merge_requests/58).
- **VotePeer on Nexa:** the Firebase functions, [nexa/votepeer/votepeer-node-firebase!2](https://gitlab.com/nexa/votepeer/votepeer-node-firebase/-/merge_requests/2).

Both keep the earlier public servers as fallbacks and give up on a server that does not answer within a few seconds. votepeerjs uses Nexa on 20004 and BCH on 50004 (https://gitlab.com/nexa/votepeer/votepeerjs/-/merge_requests/1).

The VotePeer Android library (`votepeer-library`) connects over raw TLS on port 50002, which these servers now offer, so it can use `electrum-bch.nordiccrypto.no:50002` too.

## First sync

Rostrum answers queries only after its node has synced and the index is built. Nexa takes a few hours. Bitcoin Cash takes a day or more: the node downloads the full chain (pruning is off, since Rostrum needs every block) and then Rostrum indexes it.

## Upgrading

- **BCHN and Nexa:** download the new release tarball, unpack it over `/opt/bchn` or `/opt/nexa`, and restart the service.
- **Rostrum for BCH:** `/root/build-rostrum-bch.sh` builds a tagged release with Ubuntu's `rustc-1.91` / `cargo-1.91` packages and installs it to `/usr/local/bin/rostrum-bch`. Change the tag in the script, run it, and restart `rostrum-bch`. Read the release notes first: a major release can trigger a full reindex.
- **Rostrum for Nexa** comes with the Nexa release.
