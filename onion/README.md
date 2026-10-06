# Onion tip page

A small Tor v3 hidden service for the same private tip inbox as `https://cryptonordic.no/tip/`. The page is static HTML. It does not use JavaScript, external fonts, analytics, or Cloudflare Turnstile, so it works in Tor Browser with the security level set to Safest.

The app forwards each tip to the Worker `POST /api/tip` with `Authorization: Bearer <ONION_INGEST_TOKEN>`. If the Worker does not answer, the tip is appended to a file on this server (`queue.jsonl`, mode 0600) and retried. Invalid tips are not kept. Nothing about the request is written to logs.

GitHub Pages and Cloudflare cannot host an onion service. This runs on a VPS you control. **Do not start it from this repository's build, and do not commit `.env`.**

The clearnet `/tip/` page mentions Tor. Until `workers/tips/public.json` has an `onion` value, the page says the address is not published yet. It does not invent an address.

## What you need

- `WORKER_URL` — `https://tips.cryptonordic.no` after the Worker in `workers/tips/` is deployed.
- `ONION_INGEST_TOKEN` — the same secret as the Worker's `ONION_INGEST_TOKEN`, and not the same as `READ_TOKEN`.
- A machine with a public IP is not required for the onion itself. Tor makes the outbound connection. You still need a host that can run Tor and reach the Worker over HTTPS.

## Cheap VPS

One small Debian server is enough (about 1 GB of RAM). Pick a provider that allows Tor. Do not install a monitoring agent that ships logs off the box.

Suggested layout:

```bash
sudo mkdir -p /opt/nordic-crypto
sudo rsync -a onion/ /opt/nordic-crypto/onion/
cd /opt/nordic-crypto/onion
cp .env.example .env
# edit .env: set ONION_INGEST_TOKEN. Leave ONION_HOST empty for the first start.
docker compose up -d --build
```

The v3 address is created on first start and kept in the `onionkeys` volume:

```bash
docker compose exec tor cat /var/lib/tor/tip/hostname
```

That prints a line like `abcdefghijklmnopqrstuvwxyz234567abcdefghijklmnopqrst.onion`. Put `http://` plus that name in `.env` as `ONION_HOST` (no path), then `docker compose up -d`. The form then sends `page` as that onion URL. Restarting Tor does not change the address as long as the volume is kept.

Then set the same address in `workers/tips/public.json` (`"onion": "http://….onion"`) and rebuild the website so `/tip/` shows the link and the `Onion-Location` meta tag. Also set the HTTP `Onion-Location` header in Cloudflare, as described in `workers/tips/README.md`. Do not publish a placeholder address.

systemd, if you want the compose project to come up on boot: copy `systemd/nordic-crypto-onion.service` to `/etc/systemd/system/`, then `systemctl enable --now nordic-crypto-onion.service`. The unit's `WorkingDirectory` must be the compose directory.

Without Docker: create a user `nordic-tip`, install `tor` and Python 3, point Tor's `HiddenServicePort` at `127.0.0.1:8080` (edit the port line in `tor/torrc`), put the secrets in `/etc/nordic-crypto-onion.env` (mode 0600), and install `systemd/nordic-crypto-onion-host.service`.

Regenerate `app/copy.json` after changing tip strings:

```bash
python3 onion/build_copy.py
```

Local check (does not start Tor and does not deploy):

```bash
python3 onion/test_forward.py
```

## Hardening

- No inbound port is required for the onion. Firewall the host so the only open management port is SSH from a known address. Prefer SSH keys.
- Compose sets `logging: driver: none` on both containers. The Python server does not log requests. Tor is configured with `Log notice file /dev/null` and `SafeLogging 1`. Do not add a log shipper.
- The queue file holds tip text until the Worker accepts it. Put the VPS disk encryption on, keep the file mode 0600, and do not back the queue up to a public bucket. Delete the volume if you decommission the host.
- Run as the unprivileged user (`DROP_UID` / `debian-tor`). Do not run the app as root after startup.
- The ingest token is a bearer secret. Rotate it by changing the Worker secret and `.env` together.
- **Vanguards.** Tor 0.4.7 and later enables vanguards-lite by default, which is the right baseline. The full `vanguards` add-on is optional. It needs a control port. If you add it, bind the control port to localhost only, use cookie authentication, and do not publish port 9051. Leaving the add-on off is acceptable.
- Do not enable Tor's SOCKS port on a public interface (`SocksPort 0` in `tor/torrc`).
- Do not put the onion host on the same machine as a copy of the tip database if you can avoid it. The Worker holds the inbox. This host should only forward.

## SecureDrop

SecureDrop is the heavier option: a separate application server, a journalist workstation, GPG, and a documented air gap. Use it if you need that full anonymous drop (document decryption on a machine that is not this VPS, multiple journalists, the SecureDrop threat model).

This onion page is not SecureDrop. It is a small form that lands in the same private D1 inbox as the website. It does not add a second newsroom system. If you later move to SecureDrop, retire this service and the ingest token rather than running both without a written choice.

## Onion-Location

Tor Browser looks for an `Onion-Location` HTTP header, and also for `<meta http-equiv="onion-location">`. The meta tag is emitted on the built `/tip/` page when the address is in `workers/tips/public.json`. The header has to be set on `cryptonordic.no` itself (Cloudflare Snippet or Transform Rule). The steps are in `workers/tips/README.md`. Leave both off until `docker compose exec tor cat /var/lib/tor/tip/hostname` has been run and the address is the one you intend to publish.
