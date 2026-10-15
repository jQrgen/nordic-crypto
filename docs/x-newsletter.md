# Newsletter → X thread (@nordiccryptobot)

`tools/x_newsletter.py` posts each new weekly Nordic Crypto issue to X once, as **one long post** (X Premium, up to 25,000 characters)
with the full issue text and the newsreel video attached. If X rejects the length (no long-post entitlement), the
run falls back to the thread below, reusing the uploaded video. `--thread` forces thread mode.

Long post: `Nordic Crypto #N: <headline>`, every paragraph, section heading (upper case) and story (headline, link,
summary, source line) from `issue.html`, then `Read it on Nordic Crypto: <issue link>`.

Thread fallback:

- **Post 1:** `Nordic Crypto #N: <headline>`, the issue subtitle, the issue link, and the newsreel video attached natively
  (X API v2 chunked upload `/2/media/upload` initialize / append / finalize / status; the v1.1 endpoint returns 401 for pay-per-use apps).
- **Posts 2…n:** one reply per story: `i/n <headline>`, a 1–2 sentence summary, the source link.
- **Last post:** link to the newsletter archive.
- Posts are created with X API v2 `POST /2/tweets` and OAuth 1.0a user context. Each post fits 280 characters with
  URLs counted as 23; summaries are cut at a sentence, else at a word with `…`.

Data comes from `newsletter/published/issues.json` and `newsletter/published/<id>/issue.html`. The video is the local
`video.mp4` or `video.url` (sha256-checked). A real run first checks that `https://nordiccrypto.no/newsletter/<id>/`
answers 200, so nothing goes out before the issue is live.

## State
`data/x_posted.json` records the post ids per issue (`mode`: `long` or `thread`). A completed issue is never posted again. If a thread breaks
midway, the next run continues as replies to the last saved post (the video is not re-uploaded).

## Run
```sh
python3 tools/x_newsletter.py --dry-run              # newest issue, print only
python3 tools/x_newsletter.py --issue 002 --dry-run
python3 tools/x_newsletter.py --issue 002            # post (needs the secrets below)
python3 -m pytest tests/test_x_newsletter.py
```

## Secrets
`X_API_KEY`, `X_API_SECRET` (app consumer keys) and `X_ACCESS_TOKEN`, `X_ACCESS_SECRET` (user tokens for
@nordiccryptobot). The X app must have **Read and Write** permission, and the access token must be generated *after*
setting that. If any is missing, the script logs `skipping: missing …` and exits 0.

## CI
`.github/workflows/x-newsletter.yml` runs after every successful "Deploy site" run, on Monday mornings after the
~08:23 Oslo publish, and on manual dispatch (`issue`, `dry_run`). It commits `data/x_posted.json` back to `main`.
