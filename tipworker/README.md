# tipworker – reader tip intake + newsletter signup on Cloudflare Workers + D1

Public replacement for the box-only `tipserver/` (port 7844/tunnels are blocked on the box). Same fields, validation,
honeypot, limits and responses as `tipserver/server.py` (checked by `test_parity.sh`).

- `POST /api/tip` – JSON or form: `url` (required), `country` (NO/SE/DK/FI/IS/unsure), `note` (≤1000), `name` (≤100,
  never published), `website` (honeypot). 201 JSON / 303 redirect to /tip/ for plain forms. Body ≤ 4 KB.
- `GET /api/health` – `{"ok":true,"service":"nordic-crypto-tips"}` (also checks D1).
- `GET /api/geo` – `{"country":"NO"}` or `{"country":null}`: only the two-letter code Cloudflare already attaches to the
  request (`request.cf.country`; `XX`/`T1` → null). Used once per visit by the site's language picker
  (`tools/langselect.js`). Nothing stored or logged, `Cache-Control: no-store`, CORS for the public site origin (`site_url.json`) and https://jqrgen.github.io. No third-party
  geo-IP service. Tests set `--var GEO_TEST:1` so the `X-Test-Country` header can fake a country; production never sets it.
- CORS: the public site origin (`site_url.json`) and `https://jqrgen.github.io` (Kryptonytt); other browser origins get 403 and no `Access-Control-Allow-Origin`.
- Rate limit: 5 / 10 min per visitor, 200 / 10 min in total, counted separately for each scope (`tip`, `private`,
  `subscribe`), so a flood of one endpoint can't lock the others. Private tips count only after Turnstile passed. No raw
  IPs: `rate_hits.h = '<scope>:' + SHA-256(daily random salt | scope | IP)` kept 10 minutes; the salt is replaced every
  UTC day and the old one deleted.
- No logging: no `console.*`, `[observability] enabled = false`.

Files: `src/worker.js`, `migrations/0001_tips.sql`, `migrations/0002_articles.sql` (append-only article archive, same schema as `archive/schema.sql`; applied by `deploy.sh` with the other migrations, not applied yet), `wrangler.toml`, `deploy.sh`, `pull.py`, `test_local.sh`,
`test_parity.sh`, `tests/browser_cors.py`, `publish_tip_page.sh`, `env.sh` (wrangler 4 needs Node ≥ 22; uses `~/.local/node22` when present).

## Newsletter signup (Nordic Crypto + Kryptonytt) – `src/newsletter.js`, `src/mailer.js`, `src/messages.js`, `migrations/0003_subscribers.sql`
- `POST /api/subscribe` – JSON or form: `email`, `site` (`nordic-crypto` | `kryptonytt`), `lang` (a language of that site),
  `website` (honeypot). Same answer for new / pending / already confirmed addresses (202 `{"ok":true,"pending":true}`, or a
  303 back to the site's newsletter page `?sent=1`), so nobody can test who subscribes. Body ≤ 2 KB, 5 per visitor / 10 min
  (same salted-hash limiter as tips), a pending address gets at most one confirmation email per 10 minutes.
- `GET /api/confirm?token=…&s=<site>&l=<lang>` – token valid 7 days, single use, stored only as SHA-256 → 303 `?confirmed=1`
  (or `?error=invalid_link`). HEAD never confirms. Unconfirmed rows are deleted after 7 days.
- `GET /api/unsubscribe?id=…&sig=…` – small page with a button; `POST` unsubscribes (also RFC 8058 one-click).
  `sig` = HMAC-SHA-256(`UNSUB_SECRET`, `id|email|site`), so no unsubscribe token is stored. `deploy.sh` creates the secret once.
- D1 `subscribers`: email, site, lang, status (pending/confirmed/unsubscribed), token_hash, timestamps. **No IP, no user agent.**
  Unsubscribed rows keep the address with status `unsubscribed` (so it is never exported or mailed again).
- Mail: **nothing is sent** unless `MAIL_PROVIDER` (`resend` | `mailgun` | `webhook`) **and** `MAIL_SEND_ENABLED=1` are set
  (settings in `src/mailer.js`; placeholders only, no keys in git). Issue mail is `newsletter/send_issue.py` (see `newsletter/email-list.md`).
- Operator export of confirmed rows: `.venv/bin/python tipworker/export_subscribers.py --site nordic-crypto|kryptonytt [--lang xx]`
  → `state/newsletter/<site>-confirmed-<date>.csv` (confirmed only, mode 600, addresses never printed, gitignored). Delete the file when done.
- Tests: `node --test tests/newsletter.test.mjs`, `./test_subscribe.sh` (wrangler dev, `SUBSCRIBE_TEST=1` = in-memory test
  mailer + token in the response; never set in production), `python3 tests/test_export.py`, and the real-browser form test
  `tests/browser_newsletter.py` (see its docstring). `npm test` runs all of them except the browser test.

## Private tip inbox (the /tip/ form) – `src/private_tips.js`, `migrations/0005_private_tips.sql`
- `POST /api/private-tip` – JSON or form: `tip` (required, ≤ 8000 characters), `attachments` (http/https links, newline or
  comma separated or an array, ≤ 10), `contact` (optional, ≤ 500, never published), `language`, `page` (a `/tip/` path or a
  site tip-page URL), `website` (honeypot), `cf-turnstile-response`. Body ≤ 32 KB. JSON answers with short error codes
  (`empty_tip`, `tip_long`, `bad_attachment`, `turnstile`, `rate`, `offline`, …). Stored in table `private_tips`, status `new`.
  Separate from `tips`: `pull.py` never reads it and nothing from it is published.
- `GET /api/private-tips?status=new|read|handled|all&limit=50` and `POST /api/private-tips/<id>` `{status, editor_notes}` –
  newsroom only, `Authorization: Bearer $PRIVATE_TIPS_READ_TOKEN`, no CORS headers.
- Secrets (never in git): `TURNSTILE_SECRET` (shared with the shoutbox; without it the route answers 503 and stores nothing),
  `PRIVATE_TIPS_READ_TOKEN`, optional `TIP_WEBHOOK_URL` (https only) + `TIP_WEBHOOK_BEARER` (each stored tip is POSTed as
  `{"event":"tip.created","tip":{…}}`, 5 s timeout, failure does not lose the tip).
- The site opens the form only when `public_endpoint` (tipserver/config.json, set by deploy.sh) and a Turnstile site key are set.

## Shoutbox (one shared room) – `src/shouts.js`, `migrations/0004_shouts.sql`

One room for every language and every reader. `lang` on a post is only a tag for the page it was sent from. `GET /api/shouts` ignores `lang`, `room` and `channel` and returns the same visible rows to everyone. Messages are not translated.

- `GET /api/shouts?limit=50&before=<id>&after=<id>` – up to 50 visible messages, oldest first inside that page. No nickname hash, no IP hash.
- `POST /api/shouts` – JSON: `nickname` (2–24), `message` (1–280, plain text; tags stripped), optional `lang`, `cf-turnstile-response`, honeypot `website`. URLs are stored as text and the page does not turn them into links.
- `POST /api/shouts/report` – `{id}`. The same daily hash can report a message once. After 3 distinct hashes the message is hidden for review.
- `GET /api/shouts/admin` and `POST /api/shouts/admin` – `Authorization: Bearer <SHOUT_ADMIN_TOKEN>`. Actions: `hide`, `delete`, `restore`, `ban`, `unban`. Ban takes `id` (that row’s hash) or `hash` (64 hex). No CORS on these responses. A ban also hides that hash’s visible rows.
- Rate limit: 5 posts / 10 min per hash, 100 posts / 10 min in total, 30 reports / 10 min per hash. `shout_hits` keeps only the hash.
- Turnstile: posts are refused unless `SHOUT_TEST=1` (tests only; never set in production) or `TURNSTILE_SECRET` is set. The siteverify call does not send the IP. A missing secret is HTTP 503, not an open post.
- Privacy: raw IPs are not stored. `ip_hash` is SHA-256 of the UTC day’s random salt and the IP. The salt is deleted when the day changes, so a ban lasts until the next UTC day and the old hash cannot be linked to an IP. No logging (`console` is not used; observability stays off).

The public site stays dark until `chat/config.json` has `"enabled": true` and an `endpoint`. While it is false, the build omits the widget and the `/chat/` pages.

### Deploy (do this by hand; this repo does not run it)

1. In the Cloudflare dashboard, add a Turnstile widget (managed) for `nordiccrypto.no`, `www.nordiccrypto.no`, and the country domains `nordiccrypto.se`, `.fi`, `.dk`, `.is` (apex and www). Copy the **site key** (public) and the **secret key**.
2. From `tipworker/`, set the two secrets. Wrangler prompts for the value. Do not commit them and do not pass them on the command line if your shell history is shared. `deploy.sh` does **not** set these.
   ```
   openssl rand -hex 32
   npx wrangler secret put TURNSTILE_SECRET
   npx wrangler secret put SHOUT_ADMIN_TOKEN
   ```
   `SHOUT_ADMIN_TOKEN` is the hex from `openssl`. Needs `CLOUDFLARE_API_TOKEN`.
3. Apply the D1 migration (also done by `./deploy.sh`):
   ```
   npx wrangler d1 migrations apply nordic-crypto-tips --remote
   ```
   That applies `migrations/0004_shouts.sql` on the existing database `nordic-crypto-tips`.
4. Deploy the worker, still without publishing the site:
   ```
   ./deploy.sh
   ```
   Check `https://nordic-crypto-tips.nordiccrypto.workers.dev/api/health`. Posts stay closed until step 2 has been done.
5. Turn the static site on by editing `chat/config.json` (the site key is public; the secret stays in step 2):
   ```json
   {
     "enabled": true,
     "endpoint": "https://nordic-crypto-tips.nordiccrypto.workers.dev",
     "turnstile_site_key": "<Turnstile site key>"
   }
   ```
6. Publish the HTML only after jQrgen’s explicit approval: `./publish.sh --yes` from the repo root.

Moderation after deploy:

```
curl -sS -H "Authorization: Bearer $SHOUT_ADMIN_TOKEN" \
  https://nordic-crypto-tips.nordiccrypto.workers.dev/api/shouts/admin
curl -sS -X POST -H "Authorization: Bearer $SHOUT_ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"action":"hide","id":123}' \
  https://nordic-crypto-tips.nordiccrypto.workers.dev/api/shouts/admin
```

`action` is `hide`, `delete`, `restore`, `ban` or `unban`.

Local preview against the mock (not the live worker): `python3 tipworker/shout_mock.py`, then `NC_CHAT=1 CHAT_ENDPOINT=http://127.0.0.1:8791 NC_SITE_DIR=/tmp/nc-chat .venv/bin/python build.py`.

## Deploy (needs `CLOUDFLARE_API_TOKEN`)
    tipworker/deploy.sh          # D1 create-if-missing, migrations --remote, wrangler deploy, health check, sets tipserver/config.json public_endpoint
    tipworker/publish_tip_page.sh        # dry run: scratch public build, privacy gate, diff of tip/index.html vs gh-pages
    tipworker/publish_tip_page.sh --yes  # (with jQrgen's approval) pushes ONLY tip/index.html + tip-endpoint.json, checks live page
Token permissions: Account › Workers Scripts: Edit, Account › D1: Edit, Account › Account Settings: Read (plus a
workers.dev subdomain registered on the account).

## Nightly import
`routines/nightly-fetch.sh` runs `tipworker/pull.py`: pending D1 rows → `tools/reader_tips.py` (`import_rows`, dedupe,
`queue/review.json`, origin `reader tip #<id>`) → rows marked imported/duplicate/invalid in D1. Name is never read.
Skips silently without `CLOUDFLARE_API_TOKEN` or before the first deploy. `--local` uses wrangler dev's local D1.

## Tests (local only)
    cd tipworker && npm test                     # test_local.sh (wrangler dev: health, CORS, validation, honeypot, rate limit, no IPs/logs) + parity
    TIP_ENDPOINT=http://127.0.0.1:8788 python3 build.py  # into a scratch copy, then: python3 tipworker/tests/browser_cors.py <site>
