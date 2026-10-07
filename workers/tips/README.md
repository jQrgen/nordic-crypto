# Private tip intake

The public tip page (`/tip/` in every site language) is wired to this Worker. Tips are not written to GitHub issues, to the git repository, or to any other public store.

This directory is the Worker and its D1 schema. It is not deployed by this repository. `workers/tips/public.json` has `"enabled": false`, so the built page shows an opening-soon notice and no form until you turn that on after a real deploy. Deploy only when you mean to, with the secrets below set in Cloudflare and not in git.

## What the Worker does

- `POST /api/tip` — from the website form, once the form is enabled, or from the Tor onion app in `onion/`.
  - The onion app sends `Authorization: Bearer` with the `ONION_INGEST_TOKEN` secret and does not use Turnstile. That token must be different from the read token. If they are the same, onion posts are refused.
  - Fields: `tip` (required, at most 8000 characters), `language`, `page`, optional `contact` (at most 500 characters), optional `attachments` (up to 10 `http` or `https` links, one per line or a JSON list).
  - Honeypot field `website`: if it is filled, the Worker answers success and stores nothing.
  - Posts must include a Cloudflare Turnstile token (`cf-turnstile-response`). The secret is `TURNSTILE_SECRET`.
- `GET /api/tips?status=new` — list tips. `status` may be `new` (default), `read`, `handled`, or `all`. `limit` defaults to 50 and stops at 200.
- `POST /api/tips/<id>` — JSON body `{"status":"read"}` or `"handled"` or `"new"`, and optional `editor_notes` (string, or `null` to clear). Notes are for the newsroom. They are not shown to the sender.
- `GET /api/health` — `{"ok":true,"service":"nordic-crypto-tip-intake"}` when D1 answers.

Statuses stored on a tip: `new`, `read`, `handled`.

Columns: `id`, `created_at`, `language`, `page`, `tip`, `contact`, `attachments` (JSON text), `status`, `editor_notes`.

Allowed browser origins: `https://nordiccrypto.no`, `https://www.nordiccrypto.no`, the same names on `http`, the country domains `nordiccrypto.se`, `nordiccrypto.dk`, `nordiccrypto.fi` and `nordiccrypto.is` (and their `www` hosts, `http` and `https`), and `https://jqrgen.github.io`. A request with no `Origin` (the onion app, curl) is accepted. Any other `Origin` is refused.

## Privacy

The IP address is not written into `tips` and is not logged. Workers observability is off in `wrangler.toml`, and the code does not call `console`.

For rate limiting only, the Worker keeps `SHA-256(salt + "|" + key)` in `rate_hits`. The salt lives in `rate_salt` until the 10-minute window ends, then the salt and the hashes are deleted. For a browser, `key` is the connecting IP and the limit is 5 tips per window. For an onion forward, `key` is the fixed label `onion` (not the VPS address) and the limit is 60 per window. A global cap of 200 tips per window also applies. The IP itself is never stored.

Turnstile siteverify is called with the token and the Turnstile secret only. The IP is not sent in that call.

Do not enable Logpush, Tail, or Workers Logs on this Worker.

## Optional webhook

If the secret `TIP_WEBHOOK_URL` is a `https://` URL, each stored tip is also POSTed as:

```json
{"event":"tip.created","tip":{"id":1,"created_at":"...","language":"da","page":"/da/tip/","tip":"...","contact":null,"attachments":[],"status":"new","editor_notes":null}}
```

If `TIP_WEBHOOK_BEARER` is set, the request carries `Authorization: Bearer <that value>`. A webhook failure does not fail the tip. Leave `TIP_WEBHOOK_URL` unset to skip this.

## Reading tips (newsroom assistant)

```bash
curl -sS -H "Authorization: Bearer $READ_TOKEN" \
  "https://tips.nordiccrypto.no/api/tips?status=new"

curl -sS -X POST -H "Authorization: Bearer $READ_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status":"read","editor_notes":"forwarded to the newsroom editor"}' \
  "https://tips.nordiccrypto.no/api/tips/1"
```

The editor that reads the queue includes artificial intelligence. It is not a human. Do not describe it as a person when you write back to a source.

## Tests

```bash
cd workers/tips && node --test test/worker.test.mjs
python3 tests/test_tip_page.py
```

No Cloudflare account is required. These tests do not deploy.

## Go-live steps

Do these in Cloudflare only when you intend to deploy. Do not commit the values. Until then, leave `enabled` false so the site does not show a form that posts nowhere.

1. **API token for deploy.** In the Cloudflare dashboard: My Profile → API Tokens → Create Token. Use a custom token on the account that will own the Worker. Permissions:
   - Account / Workers Scripts / Edit
   - Account / D1 / Edit
   - Account / Account Settings / Read
   Export it only in the shell you deploy from: `export CLOUDFLARE_API_TOKEN=...`
   `wrangler login` (OAuth in a browser) is an alternative. Either way, the token stays out of the repo. `workers/tips/.dev.vars` is gitignored if you use `wrangler dev`.

2. **D1 database.** From `workers/tips/`:
   ```bash
   npx wrangler@4 d1 create nordic-crypto-tip-intake
   ```
   Copy the printed `database_id` into `wrangler.toml` in place of `00000000-0000-0000-0000-000000000000`. The id identifies the database; it is not a tip, but it is account-specific. Then:
   ```bash
   npx wrangler@4 d1 migrations apply nordic-crypto-tip-intake --remote
   ```

3. **Turnstile.** Dashboard → Turnstile → Add widget.
   - Hostnames: `nordiccrypto.no`, `www.nordiccrypto.no`, the country domains if those pages should send tips (`nordiccrypto.se`, `nordiccrypto.dk`, `nordiccrypto.fi`, `nordiccrypto.is`), and `jqrgen.github.io` if that mirror should send tips.
   - Widget mode: managed.
   Put the **site key** (public) in `workers/tips/public.json` as `turnstile_sitekey`. The site key is not a secret.
   Put the **secret key** only in the Worker:
   ```bash
   npx wrangler@4 secret put TURNSTILE_SECRET
   ```

4. **Read token.** A long random string, for example `openssl rand -hex 32`. This is what the assistant sends as `Authorization: Bearer ...`.
   ```bash
   npx wrangler@4 secret put READ_TOKEN
   ```
   Give the same value to the assistant out of band. Do not commit it.

5. **Webhook (optional).**
   ```bash
   npx wrangler@4 secret put TIP_WEBHOOK_URL
   npx wrangler@4 secret put TIP_WEBHOOK_BEARER
   ```
   Skip both if you do not want a webhook. The URL must be `https`.

6. **Deploy the Worker.**
   ```bash
   cd workers/tips
   npx wrangler@4 deploy
   ```
   Then attach the custom domain `tips.nordiccrypto.no` (Workers → Settings → Domains & Routes, DNS proxied). `workers/tips/public.json` already uses that URL as `endpoint`.

7. **Turn the form on and rebuild the site.** Set `"enabled": true` in `public.json` only after the Worker answers and the Turnstile site key is in the same file. Rebuild and publish the site the usual way. While `enabled` is false, or the site key is missing, `/tip/` explains that the inbox is not open and shows no form. Nothing is sent to GitHub.

8. **Onion ingest token**, only if you run the Tor page in `onion/`. Another random string, different from `READ_TOKEN`.
   ```bash
   npx wrangler@4 secret put ONION_INGEST_TOKEN
   ```
   Put the same value in `onion/.env` on the VPS. If it matches `READ_TOKEN`, onion posts are refused. See `onion/README.md`.

9. **Onion-Location header** on `nordiccrypto.no`, once the VPS has printed a hostname. A meta tag is added on `/tip/` when `public.json` `onion` is `http://<56 letters>.onion`. The HTTP header still has to be set in front of the site, because GitHub Pages cannot set it. In Cloudflare, a Snippet or Transform Rule on `nordiccrypto.no`:
   - If the path is `/tip` or `/tip/`, set `Onion-Location` to `http://<address>.onion/en/`.
   - If the path matches `/<lang>/tip`, set `Onion-Location` to `http://<address>.onion/<lang>/`.
   Do not send the header while the address is still unpublished. `/tip/` says the address is not published yet until `onion` is set.

## Public config

`public.json` holds only the on/off flag, the Worker URL, the Turnstile site key, and the onion address. Secrets do not go in that file.
