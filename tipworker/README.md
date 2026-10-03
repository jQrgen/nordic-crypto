# tipworker – reader tip intake on Cloudflare Workers + D1

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
