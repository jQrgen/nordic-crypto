# tipworker – reader tip intake + newsletter signup on Cloudflare Workers + D1

Public replacement for the box-only `tipserver/` (port 7844/tunnels are blocked on the box). Same fields, validation,
honeypot, limits and responses as `tipserver/server.py` (checked by `test_parity.sh`).

- `POST /api/tip` – JSON or form: `url` (required), `country` (NO/SE/DK/FI/IS/unsure), `note` (≤1000), `name` (≤100,
  never published), `website` (honeypot). 201 JSON / 303 redirect to /tip/ for plain forms. Body ≤ 4 KB.
- `GET /api/health` – `{"ok":true,"service":"nordic-crypto-tips"}` (also checks D1).
- `GET /api/geo` – `{"country":"NO"}` or `{"country":null}`: only the two-letter code Cloudflare already attaches to the
  request (`request.cf.country`; `XX`/`T1` → null). Used once per visit by the site's language picker
  (`tools/langselect.js`). Nothing stored or logged, `Cache-Control: no-store`, CORS only for github.io. No third-party
  geo-IP service. Tests set `--var GEO_TEST:1` so the `X-Test-Country` header can fake a country; production never sets it.
- CORS: only `https://jqrgen.github.io`; other browser origins get 403 and no `Access-Control-Allow-Origin`.
- Rate limit: 5 tips / 10 min per visitor, 200 / 10 min in total. No raw IPs: `SHA-256(daily random salt | IP)` kept
  10 minutes in `rate_hits`; the salt is replaced every UTC day and the old one deleted.
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
- Mail: **nothing is sent** unless `MAIL_PROVIDER` (`resend` | `webhook`) **and** `MAIL_SEND_ENABLED=1` are set (provider not
  chosen yet; settings in `src/mailer.js`). Buttondown/Substack run their own opt-in: use the CSV export instead.
- Export for a Substack import: `.venv/bin/python tipworker/export_subscribers.py --site nordic-crypto|kryptonytt [--lang xx]`
  → `state/newsletter/<site>-confirmed-<date>.csv` (confirmed only, mode 600, addresses never printed).
- Tests: `node --test tests/newsletter.test.mjs`, `./test_subscribe.sh` (wrangler dev, `SUBSCRIBE_TEST=1` = in-memory test
  mailer + token in the response; never set in production), `python3 tests/test_export.py`, and the real-browser form test
  `tests/browser_newsletter.py` (see its docstring). `npm test` runs all of them except the browser test.

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
