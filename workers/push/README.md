# Browser push (Cloudflare Worker + KV)

Standard Web Push (VAPID) for https://cryptonordic.no/ and the GitHub Pages copy. The static site cannot store subscriptions, so this Worker does.

It stores only the push subscription: the endpoint, the two encryption keys, the page language, and the countries the reader picked. No name, no email, no IP address, no user agent. Workers observability is off, and the code does not log requests.

One successful site publish sends **one** notification per matching subscription. Several new stories are collapsed into that single message. A reader who picked Norway does not get a batch that only contains Swedish stories. The push `Topic` is `nordic-crypto`, and the notification tag is `nordic-crypto-latest`, so a newer publish replaces one that is still sitting in the tray.

## HTTP

| Method | Path | Who |
|---|---|---|
| GET | `/api/push/health` | Anyone. `{"ok":true,"service":"nordic-crypto-push"}` |
| GET | `/api/push/config` | The site. Returns `vapid_public_key` (public). |
| POST | `/api/push/subscribe` | The site, from an allowed browser origin. Body: `endpoint`, `keys.p256dh`, `keys.auth`, `lang`, `countries` (`[]` means all five). |
| POST | `/api/push/unsubscribe` | The same button. Body: `endpoint`. Deletes the row. Safe to repeat. |
| POST | `/api/push/publish` | The publish pipeline. `Authorization: Bearer <PUBLISH_TOKEN>`. Body: `{"stories":[{"title","summary","url","country","titles","summaries"}]}`. |
| GET | `/api/push/feed.json` | Anyone, including a future iOS app. The public story batches only. Subscriptions are not in this document. |

Allowed browser origins: `https://cryptonordic.no`, `https://www.cryptonordic.no`, `https://jqrgen.github.io`, and `http://127.0.0.1` / `http://localhost` (any port) for a local build. Subscribe and unsubscribe reject a missing or other origin.

`titles` and `summaries` are objects keyed by site language (`en`, `nn`, `nb`, `sv`, `da`, `fi`, `is`, and the wider UI set). A missing language falls back to English. The notification is in the language stored on the subscription, which is the language of the page where the reader turned notifications on.

### Feed for an iOS app

`GET /api/push/feed.json` returns the batches that were pushed, newest first (up to 30):

```json
{
  "service": "nordic-crypto-push",
  "apns": "not implemented",
  "batches": [
    {
      "id": "…",
      "published_at": "2026-10-06T12:00:00.000Z",
      "stories": [
        {"title": "…", "summary": "…", "url": "https://…", "country": "NO", "titles": {"en": "…"}, "summaries": {"en": "…", "nn": "…"}}
      ]
    }
  ]
}
```

Apple Push Notification service (APNs) is out of scope. Safari on iOS 16.4 or newer can use this site's Web Push after the reader adds the site to the Home Screen (`manifest.json` uses `display: standalone` for that). That path is still Web Push, not APNs. The same JSON is what an app would poll until someone builds APNs separately.

The static data API (`/api/v1/news.json`) remains the full published list. This feed is only the batches from publishes that ran after the Worker was switched on.

## Secrets (do not commit)

Generate once, on a machine you trust. The command prints three lines and writes no file:

```bash
cd workers/push
node keys.mjs
```

Put them in Cloudflare, not in git:

```bash
npx wrangler secret put VAPID_PUBLIC_KEY
npx wrangler secret put VAPID_PRIVATE_KEY
npx wrangler secret put PUBLISH_TOKEN
```

| Name | Where else it goes | What it is |
|---|---|---|
| `VAPID_PUBLIC_KEY` | Worker secret. The site reads it from `GET /api/push/config`. | Uncompressed P-256 public key, base64url. |
| `VAPID_PRIVATE_KEY` | Worker secret only. | The `d` value of the same key, base64url. |
| `PUBLISH_TOKEN` | Worker secret, and the environment variable `PUSH_PUBLISH_TOKEN` on the machine that runs `./publish.sh --yes`. | Bearer token for `POST /api/push/publish`. |

`VAPID_SUBJECT` is not a secret. `wrangler.toml` sets it to `mailto:push@cryptonordic.no`. Change that vars entry if the contact address should be different.

`.dev.vars` (copy from `.dev.vars.example`) is gitignored and is only for `npx wrangler dev --local`.

## Deploy (does not publish the site)

1. Cloudflare account with Workers and Workers KV, and a workers.dev subdomain (Workers & Pages → your subdomain, once).
2. API token with Account › Workers Scripts › Edit, Account › Workers KV Storage › Edit, Account › Account Settings › Read.
3. `export CLOUDFLARE_API_TOKEN=…` (and `CLOUDFLARE_ACCOUNT_ID` if the token can see more than one account).
4. `node keys.mjs`, then the three `wrangler secret put` commands above. The first `secret put` is enough to create the script; then `./deploy.sh` is the repeatable path.
5. `./deploy.sh` creates the KV namespace `nordic-crypto-push` if needed, writes its id into `wrangler.toml` (an id, not a secret), deploys, checks `/api/push/health`, and sets `public_endpoint` in `public.json`.
6. On the publish machine: `export PUSH_PUBLISH_TOKEN` to the same token. Optional override: `PUSH_WORKER_URL` (otherwise `public.json` is used).
7. The next **approved** `./publish.sh --yes` builds the button against that URL and, after gh-pages is pushed, POSTs only the stories that were not in the previous `data/news.json`.

This directory's `./deploy.sh` never pushes gh-pages and never sends a notification by itself.

Optional custom hostname (not required): in the Cloudflare dashboard, attach a route such as `push.cryptonordic.no` to the Worker, then put that origin in `public.json` instead of `*.workers.dev`. Add the hostname to the origin allow list in `src/worker.js` only if the browser will call it cross-origin; same-origin is not needed because the page on `cryptonordic.no` calls the Worker with `fetch` and CORS.

## What the site publish does

`./publish.sh --yes` keeps a copy of `.publish/data/news.json` from before the new tree is copied. After a successful gh-pages push it runs `tools/push_notify.py`. That script diffs story ids. It does not fetch, import, or change status. If the Worker URL or `PUSH_PUBLISH_TOKEN` is unset, it prints a line and exits 0 so a publish still succeeds. If the previous file has no stories, it refuses to send the whole archive unless `--allow-initial` is passed (the publish script does not pass that).

## Tests

```bash
cd workers/push && npm test
python3 -m unittest tests/test_push_notify.py
```

`npm test` does not need Cloudflare. It checks storage shape, the country filter, one push per matching subscription, deletion on HTTP 410, the feed document, and an encrypt/decrypt round trip.
