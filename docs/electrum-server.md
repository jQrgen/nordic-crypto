# Electrum server (BCH and Nexa)

Nordic Crypto runs its own Electrum server for Bitcoin Cash and Nexa. Wallets and apps (voter.cash, the event NFT prototype) can read chain state from it instead of depending on public servers.

It was set up on 9 October 2026, after voter.cash could not load the block height: its primary server, `electrs.bitcoinunlimited.info`, accepted connections but did not answer, and its fallback, `bitcoincash.network`, was down.

## Endpoints

| Chain | URL | Behind it |
|---|---|---|
| Nexa | `wss://nexa.electrum.nordiccrypto.no` | Rostrum on `127.0.0.1:20003` (WebSocket) |
| Bitcoin Cash | `wss://bch.electrum.nordiccrypto.no` | Rostrum on `127.0.0.1:50003` (WebSocket) |

Both use the Electrum protocol over WebSocket on port 443. TLS is handled by Cloudflare.

The hostnames go live when `nordiccrypto.no` is active on Cloudflare. On 9 October 2026 the domain was still on the Domeneshop nameservers (`ns1–3.hyp.net`).

## Server

| | |
|---|---|
| Provider | Hetzner Cloud, Falkenstein (`fsn1`) |
| Server | `electrum-1`, CX33 (4 vCPU, 8 GB RAM, 80 GB disk), Ubuntu 24.04 |
| Data volume | `electrum-data`, 300 GB, mounted at `/mnt/HC_Volume_107087011` |
| Firewall | `electrum-ssh-only`: inbound SSH (22) and ICMP only |
| Cost | About €25.65 a month (€8.49 server, €17.16 volume), billed hourly |

No Electrum port is open to the internet. The only way in is the Cloudflare Tunnel, which `cloudflared` opens from the server.

## What runs

Everything runs as the system user `electrum`. Each part is a systemd service.

| Service | Software | Config | Data |
|---|---|---|---|
| `bchn` | Bitcoin Cash Node 29.2.0, `/opt/bchn` | `bchn/bitcoin.conf` | `bchn/` |
| `rostrum-bch` | Rostrum 14.0.1 built with `--features bch`, `/usr/local/bin/rostrum-bch` | flags in the unit file | `rostrum-bch/` |
| `nexad` | Nexa 2.2.0.0, `/opt/nexa` | `nexa/nexa.conf` | `nexa/` |
| `cloudflared` | Cloudflare Tunnel `electrum-1` (`4f897872-1d89-4e30-8a5c-a3c902ddc9d0`) | `/etc/cloudflared/config.yml` | |

Paths in the Config and Data columns are under the data volume.

`nexad` starts its own bundled Rostrum (`-electrum=1`), listening only on localhost: TCP `20001`, WebSocket `20003`. BCHN has no built-in Electrum server, so Rostrum for BCH runs as its own service against BCHN's RPC on `127.0.0.1:8332`.

The BCHN RPC password is generated on the server and kept only in `bitcoin.conf` (mode 600). The tunnel credentials are in `/etc/cloudflared/` (mode 600). Neither is in this repo.

## Checking it

```sh
ssh root@<electrum-1>
systemctl status bchn rostrum-bch nexad cloudflared

V=/mnt/HC_Volume_107087011
/opt/bchn/bin/bitcoin-cli -datadir=$V/bchn -conf=$V/bchn/bitcoin.conf getblockcount
sudo -u electrum /opt/nexa/bin/nexa-cli -datadir=$V/nexa -conf=$V/nexa/nexa.conf getblockcount
journalctl -u rostrum-bch -f
```

The server's address is in the Hetzner console. The Hetzner API token is kept in the operator's macOS Keychain as `hetzner-api-token`.

## Who uses it

- **voter.cash (BCH):** through `@bitcoinunlimited/votepeerjs`, [bitcoinunlimited/votepeerjs!58](https://gitlab.com/bitcoinunlimited/votepeerjs/-/merge_requests/58).
- **VotePeer on Nexa:** the Firebase functions, [nexa/votepeer/votepeer-node-firebase!2](https://gitlab.com/nexa/votepeer/votepeer-node-firebase/-/merge_requests/2).

Both keep the earlier public servers as fallbacks and give up on a server after 8 seconds without an answer.

The VotePeer Android library (`votepeer-library`) connects over raw TLS on port 50002. A Cloudflare Tunnel only carries HTTP and WebSocket, so the Android app cannot use these endpoints as they stand.

## First sync

Rostrum answers queries only after its node has synced and the index is built. Nexa takes a few hours. Bitcoin Cash takes a day or more: the node downloads the full chain (pruning is off, since Rostrum needs every block) and then Rostrum indexes it.

## Upgrading

- **BCHN and Nexa:** download the new release tarball, unpack it over `/opt/bchn` or `/opt/nexa`, and restart the service.
- **Rostrum for BCH:** `/root/build-rostrum-bch.sh` builds a tagged release with Ubuntu's `rustc-1.91` / `cargo-1.91` packages and installs it to `/usr/local/bin/rostrum-bch`. Change the tag in the script, run it, and restart `rostrum-bch`. Read the release notes first: a major release can trigger a full reindex.
- **Rostrum for Nexa** comes with the Nexa release.
