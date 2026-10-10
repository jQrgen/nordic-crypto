# Nordic Crypto

[![deploy](https://img.shields.io/github/actions/workflow/status/jQrgen/nordic-crypto/deploy.yml?branch=main&label=deploy&logo=githubactions&logoColor=white)](https://github.com/jQrgen/nordic-crypto/actions/workflows/deploy.yml) [![pages](https://img.shields.io/github/deployments/jQrgen/nordic-crypto/github-pages?label=gh-pages&logo=github)](https://github.com/jQrgen/nordic-crypto/deployments) [![license](https://img.shields.io/github/license/jQrgen/nordic-crypto)](https://github.com/jQrgen/nordic-crypto/blob/main/LICENSE) [![last commit](https://img.shields.io/github/last-commit/jQrgen/nordic-crypto?logo=github)](https://github.com/jQrgen/nordic-crypto/commits/main) [![commit activity](https://img.shields.io/github/commit-activity/m/jQrgen/nordic-crypto)](https://github.com/jQrgen/nordic-crypto/pulse) [![open issues](https://img.shields.io/github/issues/jQrgen/nordic-crypto)](https://github.com/jQrgen/nordic-crypto/issues) [![open pull requests](https://img.shields.io/github/issues-pr/jQrgen/nordic-crypto)](https://github.com/jQrgen/nordic-crypto/pulls) [![top language](https://img.shields.io/github/languages/top/jQrgen/nordic-crypto?logo=python&logoColor=white)](https://github.com/jQrgen/nordic-crypto) [![repo size](https://img.shields.io/github/repo-size/jQrgen/nordic-crypto)](https://github.com/jQrgen/nordic-crypto) [![website](https://img.shields.io/website?url=https%3A%2F%2Fnordiccrypto.no&label=nordiccrypto.no)](https://nordiccrypto.no) [![Electrum Nexa](https://img.shields.io/badge/Electrum%20Nexa-electrum--nexa.nordiccrypto.no-ff9900)](https://github.com/jQrgen/nordic-crypto/blob/main/docs/electrum-server.md) [![Electrum BCH](https://img.shields.io/badge/Electrum%20BCH-electrum--bch.nordiccrypto.no-0ac18e?logo=bitcoincash&logoColor=white)](https://github.com/jQrgen/nordic-crypto/blob/main/docs/electrum-server.md)

Bitcoin, blockchain and crypto news, events, a who's who (industry + regulators), regulation by country and academia for
**Norway, Sweden, Denmark, Finland and Iceland**. Static site. Cloudflare Web Analytics counts aggregate visits (no cookies, data not sold) when a token is set in `analytics.json`. No advertising trackers.
Languages: English at `/`, and one directory per other site language. The list, native names and the IP-country guess are under [Site languages](#site-languages). A story card shows the headline in the language of the page. When the source headline is in another language, that headline is shown underneath, smaller. Our own summaries and those headlines are written first in English, then for the Nordic site languages (AI-assisted, editor-approved). Quotes stay as the source wrote them.
Public URL: https://nordiccrypto.no/ (`site_url.json`; all in-site links are relative). Run by jQrgen (Jørgen S. Notland), MIT licence.

**Status:** live at https://nordiccrypto.no/ (gh-pages, CNAME). Code on `main`. Every publish needs jQrgen's explicit approval: merging to `main` is that approval ([Automatic deploy](#automatic-deploy)).

**Domains:** the old address https://cryptonordic.no/ (and www) answers with a 301 to the same path on https://nordiccrypto.no/ (Cloudflare page rules on the cryptonordic.no zone). nordiccrypto.se, .fi, .dk and .is (apex and www) serve the site under their own address, with the front page in the country's language (Swedish, Finnish, Danish, Icelandic), through the Cloudflare Worker in [`workers/country-domains/`](workers/country-domains/). Canonical URLs stay on nordiccrypto.no. nordiccrypto.eu forwards to https://nordiccrypto.no/ (Domeneshop HTTP forwarding). nordiccrypto.no DNS is at Domeneshop (GitHub Pages A/AAAA, www CNAME jqrgen.github.io).

## Site languages
Site interface and page presentation. News outlets stay as listed in `sources.json`. UI strings live in `i18n/<code>.py`. A missing key falls back to English. Since 8 Oct 2026 every UI string is translated for all 21 languages (AI-assisted for the languages beyond the Nordic set); new keys fall back to English until they are translated. Article bodies are not machine-translated for those languages. English is the site root. Every other code is `/<code>/`.

| Code | Native name | English name | Direction |
|---|---|---|---|
| en | English | English | ltr |
| nn | Nynorsk | Norwegian Nynorsk | ltr |
| nb | Bokmål | Norwegian Bokmål | ltr |
| sv | Svenska | Swedish | ltr |
| da | Dansk | Danish | ltr |
| fi | Suomi | Finnish | ltr |
| is | Íslenska | Icelandic | ltr |
| zh | 中文 | Chinese (Mandarin) | ltr |
| hi | हिन्दी | Hindi | ltr |
| es | Español | Spanish | ltr |
| fr | Français | French | ltr |
| ar | العربية | Arabic | rtl |
| bn | বাংলা | Bengali | ltr |
| pt | Português | Portuguese | ltr |
| ru | Русский | Russian | ltr |
| ur | اردو | Urdu | rtl |
| id | Bahasa Indonesia | Indonesian | ltr |
| de | Deutsch | German | ltr |
| ja | 日本語 | Japanese | ltr |
| sw | Kiswahili | Swahili | ltr |
| mr | मराठी | Marathi | ltr |
| fa | فارسی | Persian | rtl |
| uk | Українська | Ukrainian | ltr |

`zh` is one site language for Mandarin (simplified and traditional readers share `/zh/`). `pt` covers Portugal and Brazil. `nn` stays the Norwegian default; bokmål is the quick link beside the switcher.

**How a first visit picks a language** (`tools/langselect.js`, only on the English home page). A direct link to `/sv/`, `/de/` or any other page is never redirected.

1. `nc_lang` cookie, set only when the reader picks a language in the switcher (one year, this site only). The same choice is copied to `localStorage` under `nc_lang`. The cookie wins when both are set. If the cookie is missing, the stored value is the same override.
2. Our tipworker `GET /api/geo`, which returns Cloudflare's `request.cf.country` (two letters, or null). Nothing is stored or logged, and no third-party geo-IP service is used. The Worker URL is injected at build time when `tipserver/config.json` has a `workers.dev` `public_endpoint`, or when `GEO_ENDPOINT` is set. The country is a default guess: Norway → nynorsk, Sweden → Swedish, Denmark → Danish, Finland → Finnish, Iceland → Icelandic, Åland → Swedish, Faroe and Greenland → Danish, and the major countries for the languages above (China, Taiwan and Singapore → Chinese, India → Hindi, Spain, Mexico and Argentina → Spanish, France → French, Saudi Arabia, Egypt and the UAE → Arabic, Bangladesh → Bengali, Brazil and Portugal → Portuguese, Russia → Russian, Pakistan → Urdu, Indonesia → Indonesian, Germany, Austria and Switzerland → German, Japan → Japanese, Kenya and Tanzania → Swahili, Iran and Afghanistan → Persian, Ukraine → Ukrainian). A country with no row, including the United States and the United Kingdom, stays English. India is Hindi; Marathi has no country row. Mauritania (`MR`) is Arabic; the language code `mr` is Marathi.
3. If the Worker is not deployed or does not answer within 1.5 seconds: `navigator.languages`. Norwegian tags (`no`, `nb`, `nn`) still default to nynorsk.
4. English.

After one automatic choice, `sessionStorage` `nc_auto` stops a second redirect in that tab. The full country map is in `tools/langselect.js` (`BY_COUNTRY`) and in `/api/v1/geo-language.json`.

## Data API
Public JSON for apps and other tools, written into `site/` by `./build.sh` (`tools/api_feed.py`). No account. News, newsletters, events, talks, sources, academia, books, open-source developers, the who's who, profiles, the rules map, the changelog and the article archive.

- Human docs: https://nordiccrypto.no/api/
- Discovery: `/api/v1/index.json`
- OpenAPI: `/api/v1/openapi.json` and `/api/v1/openapi.yaml`
- Languages: `/api/v1/languages.json` (code, native name, English name, rtl, html lang, home URL). The same fields are on each entry in `/api/v1/meta.json` `languages`.
- Geo language: `/api/v1/geo-language.json` (country → default language). The note there says the `nc_lang` cookie wins and the IP country is a guess from tipworker `/api/geo` (Cloudflare `request.cf.country`).
- `llms.txt` at the site root, and `/.well-known/api-catalog`

News: `/api/v1/news.json` and `/api/v1/news/{id}.json`. Newsletters: `/api/v1/newsletters.json` and `/api/v1/newsletters/001.json`. GitHub Pages sends `Access-Control-Allow-Origin: *` on the files. `python3 tools/api_feed.py` writes the same JSON from the committed public data without building the rest of the HTML. That command also fetches live exchange prices (see below).

### Talks
Public recordings of talks on bitcoin, cryptocurrencies and blockchain held in Norway, Sweden, Denmark, Finland, Iceland, the Faroe Islands, Greenland and Åland, from the Bitcoin white paper (31 October 2008) onward. The page is `/talks/`, linked from the nav, the footer and the calendar's previous-events section. The data file is `data/talks.json`. The API is `/api/v1/talks.json`, `/api/v1/talks/{id}.json` and `/api/v1/talks/by-country/{country}.json` (`NO`, `SE`, `DK`, `FI`, `IS`, `FO`, `GL`, `AX`).

`title`, speakers, dates, duration, channel and `embed` come from the platform at `source_url` (YouTube oEmbed, the watch page, and the length shown on YouTube's own search result when the watch-page player omits it). `description` is ours, a short note, not the platform text. A field the platform did not state is null. `embed` is true only when that platform's oEmbed response includes a player. The HTML page does not load the player until a click: YouTube via `youtube-nocookie.com`, Vimeo via `player.vimeo.com`. Thumbnails are not stored in the repo.

`data/talks-backfill-state.json` records which years, countries, queries, channels, universities and events have been searched, and for each run how many candidates were checked and how many talks were added. A first results page is marked sampled, not exhausted, unless the query returned nothing relevant.

### Source logos
So apps can show the outlet's logo next to its stories. Fields (v1, added; nothing removed):

- `/api/v1/sources.json`, each row in `sources`: `logo_url` (absolute URL on the GitHub Pages base of a raster image, PNG or WebP, never SVG, so SwiftUI `AsyncImage` can draw it; or `null`) and `logo` (`{kind: "logo", file_url, source_url, author, license, license_url, credit, raster_url}` or `null`). `file_url` is the original file (SVG or WebP); `raster_url` is the same as `logo_url`: the PNG rendering of an SVG (256 px on the long side, transparent background) or the WebP itself. The document also has `logo_note`.
- `/api/v1/news.json`, `/api/v1/news/{id}.json` and the by-country / by-topic slices, each item: `source_logo` (same object as `logo`, see [Outlet logos on news](#outlet-logos-on-news)) and `source_logo_url` (same as `source_logo.raster_url`, or `null`). Own stories have `null`. Each outlet in `sources` / `also_covered_by` has `logo` with `raster_url` too.

The logo is resolved by `tools/source_logos.py` (see [Outlet logos on news](#outlet-logos-on-news)): the `fetch_logos.py` key first, then the `source:<id>` entries from `fetch_source_logos.py`. `logo_url` is `null` unless that logo's `review` is `ok` in `assets/img/logos/logos.json` (a missing review counts as ok). A preview build (`./build.sh --preview`, `python3 tools/api_feed.py --preview`) also lists `pending` logos. `rejected` is never listed. Search feeds (`bing-*`) and podcasts on hosting platforms have no logo.

Fetch: `python3 tools/fetch_source_logos.py [--force] [--dry-run] [id ...]`. It tries the Wikidata item whose official website is the outlet's host (logo P154 on Wikimedia Commons, licence and author recorded), then the outlet's own site (apple-touch-icon, a large icon, an `<img>` marked logo, `og:logo`), recorded with `source_url` and `license` "Publisher's own logo, used only to identify the source of a headline". robots.txt is respected on publisher sites, own user agent, ≥2 s per host. An SVG also gets a PNG next to it (`<id>.png`, `raster` in `logos.json`; rendered with `rsvg-convert`, or `cairosvg` when that is missing). `--raster-only` re-renders the PNGs without any network request. Files land in `assets/img/logos/sources/`, metadata in `assets/img/logos/logos.json` under `source:<id>` with `"review": "pending"`. The logos are the publishers' trademarks, shown only to identify the source of a headline.

### Market prices
Public tickers from Nordic exchanges, as market data, not investment advice. Each row has `symbol`, `base`, `quote`, `last`, `bid` and `ask` when the exchange publishes them, plus `exchange` (`id`, `name`, `country`), `fetched_at` (ISO 8601) and `source_url`. Volume is included only when the exchange published it: `volume_base` is the base asset with no named window (Firi's `volume`), and `volume_base_24h` / `volume_quote_24h` are the last 24 hours in the base asset and in the quote currency (NBX). A missing volume is null, not zero. Quotes are NOK, SEK, DKK and EUR only. Nothing is converted between currencies. A failed exchange is an `error` with a timestamp and no price.

Included (official public REST, no key):

| Exchange | Country | Source |
|---|---|---|
| Firi | Norway (also DKK pairs) | `https://api.firi.com/v2/markets` and `/v2/markets/tickers` |
| Norwegian Block Exchange (NBX) | Norway (also SEK, DKK and EUR pairs) | `https://api.nbx.com/tickers` |
| Coinmotion | Finland (EUR and SEK) | `https://api.coinmotion.com/v2/rates` |

Skipped because no unauthenticated public ticker was found: Safello (OAuth `market` scope), Goobit/BTCX, Trijo, Northcrypto, Kvarn X, and no Danish- or Icelandic-registered venue. DKK and SEK pairs that Firi, NBX or Coinmotion do publish are included. Kaupr is a news source only and is not an exchange in this feed.

- All prices: `/api/v1/markets.json` (includes an `aggregated` array)
- One pair, all assets: `/api/v1/markets/aggregated.json`
- One exchange: `/api/v1/markets/firi.json`, `/api/v1/markets/nbx.json`, `/api/v1/markets/coinmotion.json`
- One asset: `/api/v1/markets/by-asset/BTC.json` (the base symbol, with `aggregated` and `logo_url`)
- Coin icon, when the CC0 set includes it: `/api/v1/markets/logos/btc.svg`
- Durable URL: `https://raw.githubusercontent.com/jQrgen/nordic-crypto/gh-pages/api/v1/markets.json`
- Same paths on the custom domain, at the site root (`https://nordiccrypto.no/api/v1/markets.json`)
- Page: `/markets/` (linked from the nav and the homepage)

Aggregation is one row per base-quote pair. BTC-NOK is not averaged with BTC-EUR. `last` is the arithmetic mean of published last prices (decimal arithmetic, not a float). `mid` is the mean of `(bid+ask)/2` where both exist, and is not mixed into `last`. `price` equals `last` when any last exists, otherwise `mid`. `min` and `max` use that same series. `exchange_count` is how many exchanges quoted the pair. `updated_at` is the newest `fetched_at`. There is no VWAP: the volume windows are not the same, so volume is not a weight. Volume sums add only the same field inside the same pair. `logo_url` is an SVG from [cryptocurrency-icons](https://github.com/spothq/cryptocurrency-icons) 0.18.1 (CC0-1.0) when that set includes the asset, and null otherwise. Nordic Crypto does not draw substitutes (POL has none; the MATIC icon is not reused).

Refresh: `./build.sh` and `./publish.sh` fetch the exchanges while building `site/`. `.github/workflows/markets-refresh.yml` rewrites the markets JSON on `gh-pages` about hourly (minute 17), including `aggregated.json`, the per-asset files and `api/v1/markets/logos/`, and leaves the previous files in place if every exchange fails. That job and the [automatic deploy](#automatic-deploy) share the `gh-pages-deploy` concurrency group, so a refresh waits instead of pushing while a publish is running or already queued. The markets page reloads `/api/v1/markets.json` about every 15 minutes and recomputes the aggregate from the tickers on the page. Firi and Coinmotion send `Access-Control-Allow-Origin: *`, so the page also requests those APIs from the browser about every 5 minutes. `api.nbx.com` does not send that header, so NBX rows follow the file.

`python3 tools/markets.py` prints a short summary. `python3 tools/markets.py --write DIR` writes the JSON tree. `--keep-if-empty` is what the hourly job uses.

### Visitor stats

`/stats/` (every site language) shows visits and page views per day (last 30 days), per ISO week (last 26 weeks) and per calendar month, with a "last updated" time. `/api/v1/stats.json` is the same data. The numbers come from Cloudflare Web Analytics: aggregate counts per UTC day only, no IP addresses, user agents, paths, referrers or countries. Until there is data, the page says the stats are being set up.

`tools/fetch_stats.py` reads `rumPageloadEventsAdaptiveGroups` from the Cloudflare GraphQL Analytics API (sum of `visits` and `count` of page views, grouped by `date`, filtered by the site tag). It goes back as far as Cloudflare keeps data (about six months) and merges the result into the rows already saved, so months stay on the page after Cloudflare has expired the days. Configuration: `CF_ANALYTICS_TOKEN` (API token with Account → Account Analytics → Read only), `CF_ACCOUNT_ID` and `CF_WA_SITE_TAG` (the Web Analytics site tag, not the public beacon token). Without all three it prints "not configured" and writes nothing. `--check` prints totals only.

Refresh: `.github/workflows/stats-refresh.yml` runs once a day and rewrites `api/v1/stats.json` on `gh-pages` (secret `CF_ANALYTICS_TOKEN`, repository variables `CF_ACCOUNT_ID` and `CF_WA_SITE_TAG`; it skips when they are missing). It uses the `gh-pages-deploy` concurrency group like the other two jobs. The page reloads that file in the browser, so new numbers show without a new build. A build uses the newer of `data/stats.json` and the published file, so a deploy does not roll the numbers back. `NC_STATS_LIVE=0` keeps the build offline.

The beacon itself is `analytics.json` (or `CF_WEB_ANALYTICS_TOKEN`): the public site token of a Web Analytics site for `nordiccrypto.no`. Without it the site loads no analytics script and the stats stay empty.

### iOS app
Public TestFlight invite, linked from the footer, the homepage, `/markets/` and About: https://testflight.apple.com/join/nQ2fpjZn. There is no App Store listing. The Nordic Crypto TestFlight version especially supports Apple TV.

### Community
Nordic Crypto brand accounts, linked from the footer, About and the newsletter, in every site language (English until a translation is written):

- Telegram: https://t.me/nordiccryptochat
- X: https://x.com/xcryptonordic

The iOS app reads them from `social` on `/api/v1/meta.json` (`social.telegram`, `social.x`). `name` is English. `name_i18n` has nn, nb, sv, da, fi and is. The source-code link on each page stays.

### Browser notifications
Opt-in Web Push. Until `workers/push/public.json` has a `public_endpoint`, every page says the notification service is not switched on yet and does not show a button. Once that URL is set, the button is at the bottom of every page (left-aligned, start-aligned in Arabic and Urdu). One publish sends one notification; several new stories are collapsed into that message. The reader can limit it to Norway, Sweden, Denmark, Finland and/or Iceland. The message uses the language of the page where they turned notifications on. Turning them off is the same button, and that deletes the subscription.

The static site cannot store subscriptions. `workers/push/` is a Cloudflare Worker with KV. It stores only the push subscription (endpoint, two encryption keys), the language and the chosen countries. No name, no email, no IP address. Deploy steps and the three secrets (`VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `PUBLISH_TOKEN`) are in `workers/push/README.md`. Those values are not in the repo. `./publish.sh --yes` calls `tools/push_notify.py` only after gh-pages is pushed, with the stories that were not in the previous public `data/news.json`. If the Worker URL or `PUSH_PUBLISH_TOKEN` is unset, that step prints a line and does not fail the publish. It does not fetch or change story status.

`GET /api/push/feed.json` on the Worker is the same batches, for a later iOS app. Apple Push Notification service (APNs) is not implemented. On iPhone and iPad, iOS 16.4 or newer can use these browser notifications after the site is added to the Home Screen.

## Pipeline
| Step | Command | What it does |
|---|---|---|
| Fetch | `./fetch.sh [--days N]` | Reads RSS feeds / list pages / news search per country (robots.txt respected, own UA, ≥2 s per host, several hosts at once). Local newspapers and justice pages are keyword-filtered. A source with no RSS is read from sitemap.xml or its public index page (title, date, link and summary only; robots.txt and the same per-host delay). One dead feed is logged and skipped. Adds new stories to `data/news.json` as `pending`, new events to `data/events.json` as `pending`, candidate entities to `queue/review.json`. The [nightly fetch on Actions](#nightly-fetch-on-actions) does the same run and leaves the new pending rows on `fetch-queue` until an editor approves them onto `main`. |
| Add a story by hand | `./fetch.sh --add URL --country XX [--date YYYY-MM-DD]` | Metadata only (title/description/date), never article text. |
| Add an event by hand | `.venv/bin/python events.py --add-event URL --country XX [--title --start --place --organiser --paid --online]` | Event lands as `pending`. |
| Refresh events only | `.venv/bin/python events.py` or `.venv/bin/python events.py --only id,id` | Same event search as `./fetch.sh`, without the news feeds. |
| Local preview | `./build.sh --preview` | Builds `site/` incl. pending items, clearly marked, `noindex`, robots disallow, writes `site/.preview`. Then the privacy gate. |
| Public build | `./build.sh` | Only approved content. |
| Publish | `./publish.sh --yes` | Manual fallback from the box. The normal path is the [automatic deploy](#automatic-deploy) when `main` is updated. `./publish.sh --yes` still refuses a preview build; on first run creates the git repo and `jQrgen/nordic-crypto`, pushes `site/` to `gh-pages` while keeping `CNAME`, `kiosk/` and every top-level name in `publish-keep.txt`, sets the Pages custom domain to nordiccrypto.no, pushes code to `main`, stamps the launch date in `changelog.json`. After a successful gh-pages push, notifies the push Worker about stories that were not in the previous public news list (one batch; skipped when the Worker is not configured). Without `--yes` it only builds and checks. Aborts if the staged gh-pages tree has no `CNAME`. |
| QA screenshots | `.venv/bin/python tools/screens.py` | Serves `site/` on a free local port, screenshots every page into `shots/`, reports JS errors, 4xx and horizontal overflow. |

## Automatic deploy

A push to `main`, including a merge, publishes the site. That is what "every publish needs jQrgen's explicit approval" means: merging to `main` is the approval. `.github/workflows/deploy.yml` checks out that commit, installs `requirements.txt` on Python 3.13, builds the public site (never `--preview`), and refuses to continue if `site/.preview` exists. It then runs `tools/privacy_gate.py` and `tools/text_gate.py`. Either gate failing, or a `CNAME` that is not nordiccrypto.no, fails the job and pushes nothing. `workflow_dispatch` runs the same job. Paths that do not change the site (tests, research notes, the tip worker, issue templates, this README) do not start a run.

The privacy gate reads `state/private_terms.json`. In Actions that file is the secret `NC_PRIVATE_TERMS_JSON`, written for the gate and deleted before the text gate and before any push. The log prints the rule count only. The file is not committed and is not uploaded as an artifact. An empty secret fails the job. One-time setup, from the box, from the repo root: `gh secret set NC_PRIVATE_TERMS_JSON < state/private_terms.json`.

gh-pages is updated only when the repository variable `NC_CI_DEPLOY` is `true` (`gh variable set NC_CI_DEPLOY --body true`). Until then the workflow still builds, runs both gates, and writes a summary (file counts and changed top-level paths against the current gh-pages). It does not push. Use that mode for the first runs.

`.github/workflows/markets-refresh.yml` uses the same concurrency group, `gh-pages-deploy`, with `cancel-in-progress: false` and `queue: max`. A price refresh waits behind a publish. It does not cancel a publish that is running or already queued. `./publish.sh` on the box is outside that group, so a rejected push is fetched, staged again with `stage_gh_pages`, and retried. The workflow does not force-push. The gh-pages checkout is depth 1 (that branch's history is large). The commit is `github-actions[bot]`, message `Publish <date> from main@<sha> [skip ci]`.

Pushes made with `GITHUB_TOKEN` do not start a new workflow run. The job also skips a push whose actor is `github-actions[bot]`, and a head commit whose message contains `[skip ci]` or `[ci skip]`. CI does not commit back to `main`. The build can rewrite tracked files such as `archive/events.json`; the job prints `git status --short` and a diff stat and leaves them uncommitted. The box, which has the approvals, remains the place that updates `data/` and `archive/events.json`.

CI does not have `queue/approved.json`, `state/source_status.json`, or `/workspace/nordic-crypto-research/academia.md`. For the published site to match a box publish, those decisions have to already be in the committed public files: `data/news.json`, `data/orgchart.json`, `data/academia.json`, `data/frontpage_blurbs.json`, `data/title_i18n.json`, and approved events in `archive/events.json`. Without `approved.json`, own stories (`stories.approve`) are left out, rows in `data/events.json` are not promoted, and the news file, the org chart and the academia file are left as committed. Without `source_status.json`, every enabled source counts as ok on the sources page. A later step, not this workflow, can commit a public snapshot the box writes — source id and ok/not-ok only, for example `data/source_status.json`, with no error text and none of the rest of `state/` or `queue/`. CI does not call `tools/push_notify.py`. Browser notifications for new stories are still sent only by `./publish.sh --yes` on the box, and that command remains the manual fallback when Actions is off or `NC_CI_DEPLOY` is not `true`.

### Nightly fetch on Actions

`.github/workflows/nightly-fetch.yml` runs the daily fetch at 01:41 UTC (03:41 in Oslo while Norway is on summer time) and from `workflow_dispatch`. The repository variable `NC_CI_FETCH` must be `true` (`gh variable set NC_CI_FETCH --body true`). Until then the schedule writes a summary and does not read any feed. The term list is the secret `NC_PRIVATE_TERMS_JSON` already used by the deploy workflow. The job writes it for the privacy gate, deletes it before the push, and never commits `state/private_terms.json` or prints it. If that file is ever committed on `fetch-queue`, the job refuses to push. `state/http_cache.json` is kept in the Actions cache (`actions/cache`), not in git.

The job checks out `main`, runs `routines/nightly-fetch.sh` with `NIGHTLY_CI=1` (`python3 fetch.py --days 3` and the source-health check), and pushes the editor queue to the branch `fetch-queue`. It opens or updates a pull request into `main` and does not merge that request. The job timeout is 4 hours. One run at a time: concurrency group `nightly-fetch`, `cancel-in-progress: false`, `queue: max`. It does not use `gh-pages-deploy`. A four-hour fetch must not block a site publish or the hourly price refresh, and this job never pushes `main` or `gh-pages`.

What lands on `fetch-queue` is awaiting the editor, not approved and not published:

- `queue/review.json` — `items_needing_summary` and `events_pending`
- `queue/pending/news.json` and `queue/pending/events.json` — `pending` rows that are not already in `data/news.json` or `data/events.json` on `main`
- `queue/fetch_report.json` — new stories, new events, how many are waiting, and source health
- `state/teasers.json`, `state/html_seen.json`, `state/html_lists.json`, `state/source_status.json` — so the next run can continue

`data/news.json` and `data/events.json` on that branch stay equal to `main`. The public build does not read `queue/pending/`. The box script, without `NIGHTLY_CI`, still builds a local preview and still looks after the tip server. Actions does not.

The job summary lists the new-story count, the new-event count, how many are awaiting the editor, and the source-health line. Test: `python3 -m unittest tests.test_ci_fetch`.

**Editor.** Read `fetch-queue` (or the pull request). Do not merge it, and do not commit on that branch. Branch from `main`. Copy only the rows you are approving or rejecting into `data/news.json` and `data/events.json`. Write the decision in `queue/approved.json` (gitignored) and run `python3 tools/apply_approvals.py`. For an event, add its id to `events.approve` or `events.reject` and let the build archive it. Before opening the pull request into `main`, run `python3 tools/ci_fetch_queue.py lint-promotion news BEFORE.json AFTER.json` (and `events` for the events file). It refuses a new row that is still `pending`. Commit the public files only. Merging that pull request is the approval. Deploy then publishes from `main`. The next fetch sees the URL on `main` and drops it from the queue.

### New events in the Telegram chat
`.github/workflows/telegram-events.yml` posts each new upcoming event to the Nordic Crypto Telegram chat once: after every successful `Deploy site` run and at :17 and :47 every hour (which also catches publishes from the box). `tools/telegram_events.py` reads the live `/api/v1/events.json`, skips events that have ended, posts the earliest first (at most 5 per run) with title, date and time, place, organiser and a link to `/calendar/<id>/`, and records each posted id in a ledger kept in the Actions cache. With no ledger (first run, or the cache expired) it records the current events and posts nothing, so the chat is never flooded with old events. Setup: repo secret `TELEGRAM_BOT_TOKEN` (the existing bot, allowed to post in the chat) and repo variable `TELEGRAM_CHAT_ID` (`@nordiccryptochat` or the numeric `-100…` id). Without both the workflow is a dry run. `workflow_dispatch` has a dry-run switch. Test: `python3 -m unittest tests.test_telegram_events`.

### Event listings
The front page and the office screen show the next six events that have not started, in start order. That list changes when an event starts: the event leaves the list and stays in the “happening now” card until it ends. Finished events stay in the data and on `/events/previous/` (newest first). The calendar list is the same events as before, with a link to the previous-events page.

Every event has its own page at `/calendar/<id>/` (and `/<language>/calendar/<id>/`). The id is the stable 12-hex event id. The calendar, the front-page list, the happening-now card and the previous-events archive link to that page. The page shows the stored date, place, organiser and official link. Under the date it shows the organiser's description when a source page stated one, in the language of the site, with the original underneath when they differ. A participant count, topics or talk videos appear only when those are already in the data with a source. An event with no sourced description has no description section. The page includes schema.org Event data, a canonical URL and hreflang links. `/api/v1/events/<id>.json` points at the same page.

Earlier public events in the Nordic countries, from 31 October 2008, are kept in `data/events_backfill.json` with `source` set to `backfill`. Each fact has a source URL and a retrieval time. They appear on `/events/previous/` and in `/api/v1/events/previous.json` only, not on the calendar and not in the upcoming list. `data/events_backfill_state.json` records the countries, queries and counts for each run so the archive can keep growing and then taper off.

A talk in `data/talks.json` is linked to one of those events, or to a calendar event, when the series, the day (the same day, or a day inside the event's span), the city, the country and the organiser agree. The talk stores `event_id` (and the same value in `calendar_event_id`). The event stores `talk_ids`. `python3 tools/event_backfill.py` does this after a talk or event backfill: it looks up an existing event first, then creates a previous event when the video page states the name, the day, the city, the country, the type and the organiser. A venue and an official URL are stored only when that page states them. Predatory conference listings are refused. A talk that cannot be dated or placed stays unlinked, with `unlink_reason`. The event page lists the linked talks (title, speakers, video). Each talk on `/talks/` links to its event page.

Every speaker named on a talk is in the who's who. `python3 tools/talk_speakers.py` matches an existing person by name or public handle and does not create a duplicate. A new person has no photo. An affiliation is stored on that talk only when the video page states it (`Name (Organisation)`, `Name (role at Organisation)` or `Name, role at Organisation`), with the talk date when the page gave one, the page URL and the retrieval time. A title stays in `role`. A trailing "speaking at …" is not an employer. The talk stores `speaker_ids`. The person stores `talk_ids`, `event_ids` and `affiliations`. Speakers without a known country are listed under Speakers, not assigned to a country. `/api/v1/orgchart/{id}.json` includes those links. An affiliation without a source is omitted.

`events.py` reads `event_sources` in `sources.json`. A `listing-jsonld` source is a page of event links (`link_pattern`, crypto keywords unless the source is `trusted`, soonest first, at most `max_links`), then schema.org `Event` JSON-LD on each page: title, start, end, place, organiser, URL and description. A street address under a Venue label is used when it is more specific than the city. Dates published as `00:00:00Z` are stored as that calendar day in the event country's time zone, and the calendar shows the dates without a clock time. No photos are copied. New rows land as `pending`. The public calendar shows an event only when its id is in `events.approve` in `queue/approved.json`. A `published` status stored on the row is not approval. When that file is absent, the committed archive stays on the calendar and rows in `data/events.json` are not promoted.

Predatory conference listings are not sources. `event_block.py` refuses International Conference Alerts, Conference Alerts, All Conference Alert, Conference Next, WASET (`waset.org` and `conferenceindex.org`) and the organisers WASET, IRAJ, IIER, ISER, ISSER, KSAA, GASR, IIRD, Research Plus, Scholars Forum, Academics World and World Academics. A matching URL, source or organiser is not imported (`events.py` and `fetch.py`), is dropped from `data/events.json` and the editor queue, and is not shown on the calendar. `--add-event` refuses them too.

Other tools: `tools/probe.py` (feed checks), `tools/import_orgchart.py` (merges the Norwegian Kryptonytt industry map, translated via `data/no_en.json`, with `data/orgchart_nordic.json`), `tools/import_academia.py` (merges `research/academia/works.json` and the researcher's `academia.md` status column into `data/academia.json`), `tools/seed_academia.py` (DOI-checked publication candidates), `tools/privacy_gate.py`, `tools/commons_photo.py` (Wikimedia Commons photos with licence + credit only), `tools/fetch_logos.py` (one logo per org and per news outlet from Wikidata/Commons or the outlet's own site → `assets/img/logos/logos.json`, review pending), `tools/fetch_source_logos.py` (a second, robots.txt-checked pass for news outlets → `assets/img/logos/sources/`, keys `source:<id>` in `logos.json`, review pending, plus PNG renderings of SVG logos; see [Source logos](#source-logos)), `tools/rules_page.py` (rules page from `rules.json`), `tools/regulation_videos.py` (country explainer slots at `/regulation-videos/`), `tools/article_archive.py` (append-only article archive).

## Calendar intake (Luma and Eventbrite)

`python3 events.py` reads `event_sources` in `sources.json` (`.venv/bin/python events.py` when that virtualenv exists). New events land in `data/events.json` as `pending`. A finished event that is already stored is kept. The site build files published past events in `archive/events.json` and does not delete them. One source that fails is recorded under `state/source_status.json` and the run continues. The same title, calendar date and venue is one event even when the URL differs. Sources with `"trusted": false` are kept only when the title, description or place matches the crypto keyword list (English and the Nordic languages). The source name is not part of that text, so a mixed calendar keeps only the matching events. Country and city come from the venue text or `addressCountry`. A physical event that cannot be placed in Norway, Sweden, Denmark, Finland or Iceland is dropped. An online event with no Nordic city and no Nordic country is dropped. Kaupr is never stored as a sponsor. The description on a new event is the organiser's text from JSON-LD, the iCal feed, the Eventbrite record or the Meetup event object, kept with the page URL and the language of that text. A title, a bare URL or a sponsor line is not stored as a description. Predatory conference sites are not a source for it.

### Luma — public iCal, not city or category discovery

The intake is the public calendar Subscribe feed, with no account:

`https://api.lu.ma/ics/get?entity=calendar&id=cal-…`

An individual event page (`"type": "luma-event"`) is schema.org Event JSON-LD.

General discovery is not connected. [Luma's terms of use](https://luma.com/terms) say, under Acceptable Use, that you must not access the Service by any means other than their publicly supported interfaces, and that site content may not be reproduced except through those interfaces. The [official API](https://docs.luma.com) needs Luma Plus, a per-calendar API key, and only covers calendars you administer. City pages such as `luma.com/oslo` do embed a short schema.org ItemList and `__NEXT_DATA__` (`discover-place`, about twenty popular events). `luma.com/crypto` and `luma.com/ai` are worldwide category pages. `luma.com/web3` is a 2021 event slug, not a category. No `api.lu.ma` discover URL is a documented public interface, and bulk-copying the city JSON is not one either. `robots.txt` allows most of those HTML pages; that does not override the terms. City slugs are also unreliable: `luma.com/bergen` describes the New York metro, and several Nordic slugs are empty or missing. On 6 Oct 2026 the Oslo, Stockholm, Copenhagen and Helsinki city pages had no crypto keyword hits in the events they embed.

Calendars in use, each with its Subscribe iCal URL on the source:

| Country | Calendar | Page |
|---|---|---|
| Norway | K33 Markets | https://luma.com/k33 |
| Sweden | Nordic Blockchain Association | https://luma.com/nordicblockchain |
| Sweden | KTH Software Meetup (keyword filter; mixed software calendar) | https://luma.com/kth-assert |
| Finland | BTCHEL Fridays | https://luma.com/btchel |

Denmark and Iceland have no verified public Luma calendar in this list. Personal calendars and global calendars (Solana Foundation, DFNS) are not subscribed.

### Eventbrite — v3 organizers and venues, not search

The public search API was removed in 2020. URLs under `/d/` are not fetched. When `EVENTBRITE_TOKEN` is set in the environment (see `.env.example`; the value is not committed and is not written into the public API), `events.py` calls:

`GET https://www.eventbriteapi.com/v3/organizers/{id}/events/?status=live&time_filter=current_future&expand=venue,organizer`

and the same path for `venues/{id}`. The token is sent as `Authorization: Bearer` and is never put in the URL or the log. Without a token, or when that call errors, the `event_pages` listed on the source are read as JSON-LD. One dead event page is skipped. A successful API response, including an empty list, does not also scrape old pages.

| Country | Organizer | Id |
|---|---|---|
| Sweden | Blockchain Smart Solutions | 46541998283 |
| Sweden | Virtune AB (publ) | 67900216533 |
| Finland | Web3 Community | 49444554943 |

No verified organizer was found for Denmark or Iceland. `"type": "eventbrite-venue"` and `venue_id` are implemented. No physical Nordic venue is subscribed: the venue ids published on the Blockchain Smart Solutions collection are online classrooms.

## Outlet logos on news

Whenever a story is shown (the news list, the screen, our own story pages, and the HTML newsletter digest) the outlet logo sits beside the source name when a checked image is on file. The name is text only when there is no logo. Nothing is drawn or invented. The site brand stays Nordic Crypto. Kaupr is a news source, and its logo appears only next to Kaupr stories.

`assets/img/logos/logos.json` is the map. `tools/source_logos.py` resolves a story's `source` field like this:

1. The id is the source id in `sources.json` (the same id stored on the news item).
2. If that source has `outlet`, the parent id is used (for example `kaupr-no` → `kaupr`, `nrk-siste` → `nrk`).
3. `_source_alias` sends a source id to a different logo key when the who's-who id is not the source id: `fi-se` → `se-fi`, `riksbank` → `se-riksbank`, `suomenpankki` → `fi-suomen-pankki`, `finanssivalvonta` → `fi-fiva`, `stortinget` → `stortinget-finanskomiteen` (the Storting coat of arms), `nbx-ir` → `nbx`, `digi-krypto` → `digi`.
4. That key's `file` is the image path, relative to the repo root (`assets/img/logos/<id>.svg` or `.webp`).

The public site shows a logo only when `review` is `ok` (a missing review counts as ok). `./build.sh --preview` also shows `pending`. `rejected`, a missing file, or no entry: text only. The image sits in a link to the outlet. It is nominative use: the outlet's own mark, small, unaltered except a raster scale to about 64px, with no implication of endorsement.

`python3 tools/fetch_logos.py --sources` fetches one mark for every source in `sources.json` (not only the enabled feeds). It prefers the outlet's own apple-touch icon, favicon or logo file. When that file is the outlet's own mark, `review` is set to `ok` and `logo_source` on the source record stores the URL it came from. Outlets whose terms explicitly forbid logo use are skipped (`logo_skipped`) and stay text-only. `python3 tools/fetch_logos.py` without `--sources` still fills organisation logos as `pending`.

If the key from steps 1–4 has no usable logo (no entry, no file, `rejected`, or `pending` on the public site), `tools/source_logos.py` tries `source:<key>`, `source:<source id>` and `source:<outlet>` next: entries written by `tools/fetch_source_logos.py`, with the same review rule. A one-off domain id on a search hit (for example `itavisen.no`) also tries the keys of the source whose `url` is on that host. Every SVG a news source can resolve to has a PNG rendering (`raster` in `logos.json`), which the API serves as `logo_url` / `source_logo_url`. `python3 tools/fetch_logos.py` fills gaps for enabled outlets and for any source that already has a published or pending story. New files stay `pending` until an editor checks that the image belongs to that outlet.

## Same event, several outlets

One story keeps a primary outlet (`source`, `source_name`, `url`, `title`, `published`, `language`). Other outlets that covered the same event are `also_covered_by`: `{outlet, outlet_name, url, title, published, lang, country, source_type}`. `outlet` is the source id. `lang` uses the same names as `language` (Norwegian, Swedish, …). Stories written before this field still have one outlet.

`source_type` is `national`, `regional` (regional and local papers), `official` (justice and official: police, prosecutors, courts, regulators, central banks, ministries) or `international`. It is taken from the outlet record when set, otherwise from `kind` in `sources.json`. Set `"reach": "regional"` on a local paper. The story page and `/api/v1/news.json` show counts and shares by country and by those four types, including a zero when a type has no outlet.

The front page shows up to six logos (the name, when no checked logo is on file) and a count such as `2 sources` or `+4 sources`. The count opens our story page. That page keeps **Read at** the primary outlet, then **Also covered by** with a link to each other outlet, then the bars, then every outlet with logo, country, original headline, time and link. The list is grouped by country, and can be sorted by time. Everything on these blocks is left-aligned.

The public news objects add `primary_source`, `also_covered_by`, `sources` (primary first) and `coverage`. `html_url` is our page. `url` stays the primary outlet. Kaupr is a news source only and is never a sponsor.

**Import.** `fetch.py`, reader tips and the cross-site handoff attach a new article to an existing story instead of creating another one when the headline matches (within 14 days), the title is close (within 3 days), or two known organisations appear in both texts (within 3 days). The note lands in `queue/review.json` → `coverage_attached`. A different event stays its own story.

**Editor.** On a row in `queue/review.json` → `items_needing_summary`, or on the `queue/approved.json` item, set `duplicate_of` to the existing story id or URL. No summary is required. The next `./build.sh` adds the article to `also_covered_by` and does not publish it on its own (`status` becomes `merged`). If `queue/approved.json` is missing, the build leaves `data/news.json` and `data/orgchart.json` as they are and does not withdraw published stories.

## Story pictures

Story cards and story pages do not show the assigned picture. The same few files repeated across stories. `tools/illustrations.py` still assigns one at build and API time from `data/illustrations.json`, using the story's topics and country, and the news item keeps that record. An optional `illustration_id` (a catalogue id, never a URL) overrides the assignment. Existing rows stay valid without the field. Outlet logos stay next to the source name.

Allowed pictures, each with `source`, `author`, `license` and `url`:

- Our own illustrations in `assets/img/illustrations/original-*.webp` (CC0, redrawn by `tools/make_illustrations.py`). Abstract shapes only: no real person, no copied logo.
- Wikimedia Commons files under CC0, public domain, CC BY or CC BY-SA, with the author named. A crop is stated on the record.
- Official pictures a public body released for free use, terms checked per agency and written on the record. In use: the Riksbank building (free use with credit) and the Norges Bank daytime facade (credit, no alteration, not for advertising).

Assignment, first match: crime → Oslo tinghus; mining → mining machines; bitcoin → a physical bitcoin token; Swedish AML → the Riksbank building; Norwegian banking or funds → the Norges Bank facade; Swedish banking or funds → the Riksbank building; business, payments, stablecoins and the other market topics → our bar chart; policy and tax → our columns; regulation and the remaining topics → the parliament building for that country.

`/api/v1/news.json` and each news item include `illustration` with those credit fields and `file_url`. The catalogue is also at `/api/v1/illustrations.json`.

Newspaper photographs are not copied, stored, proxied or hotlinked. Åndsverkloven § 23 protects a news photo. `fetch.py` drops `og:image`, RSS `media:content` / `media:thumbnail` and image enclosures, and `tools/press_images.py` strips those fields before a news file is saved and again when the API is written. Outlet logos stay, only to name the source. The full audit and the terms checks are in `docs/image-policy.md`. The same rule is stated on the ethics page and, briefly, on About.

## Press and justice registry

`sources.json` lists national, regional and local newspapers and justice-system press pages for Norway, Sweden, Denmark, Finland, Iceland, the Faroe Islands, Greenland and Åland. `type` is how a source is read (`rss`, `rss-all`, `html`, `sitemap`, `bing`, `search`). A source with no RSS is read from `sitemap.xml` or its public index page; only the title, date, link and summary are kept. `coverage` is `national`, `regional`, `local` or `justice`. A source with no working feed stays in the file with `feed` null so it can be monitored by hand or via news search. Local papers and justice pages use `rss`, so only keyword hits reach the review queue. `fetch_workers` reads several hosts at once; each host still waits `min_delay_seconds`. One dead feed is logged and skipped. Faroe Islands, Greenland and Åland appear on the sources page. They are not chips on the front-page country filter. The list was checked against Medietilsynet's newspaper register, Amedia, Polaris Media, Uutismedian liitto, Gota Media (including the Bonnier News Local titles on that page), Stampen and a Danish local-press list, plus the justice, police, prosecution, court, customs, tax and FIU pages that publish news. Kaupr is a news source only and is never a sponsor.

## Regulation explainer videos
`/regulation-videos/` has one slot each for Norway, Sweden, Denmark, Finland and Iceland, linked from `/rules/` and About. Scripts, storyboards, posters and sources are in `regulation-videos/`. Institution names and source URLs are read from the editor-approved `rules.json` at build time. Iceland is in the EEA, not the EU, and Seðlabanki Íslands houses Fjármálaeftirlit. Drop `video-XX.mp4` in `regulation-videos/media/` (gitignored) and the slot plays it with the HTML5 player. Until then the slot shows the title, the narrator notes and the sources. The films are not rendered yet. Draft notes in `regulation-videos/substack/` are for human review only; the build does not send them. Sign-off: The Nordic Crypto team. Kaupr is a news source only and is not a sponsor of these films.

## Approval model (`queue/approved.json`)
- `items`: `{url, summary (2–4 sentences, English, own words, what the story says), summary_i18n {nn, nb, sv, da, fi, is}, summary_i18n_source (the English text the translations were made from – if the summary changes, the translations are dropped until redone), blurb and blurb_i18n (optional; stored in data/frontpage_blurbs.json when the summary is still a one-line intro), title_en, title_i18n {nn, nb, sv, da, fi, is} (our headline; omit the source language), title_i18n_source (the source headline those translations were made from), topics, approved_by, approved_at}`; `duplicate_of` (story id or URL) attaches that article to an existing story instead of publishing it; `rejected`: `{url | title_contains, reason}`. Same field on a `queue/review.json` row. Published stories that do not yet have `title_i18n` on the item use `data/title_i18n.json`.
- `events`: `approve`, `reject`, `ready_for_owner` (editor-approved, waiting for jQrgen: preview only), `notes`, `notes_i18n {id: {lang: text}}`, `sponsor {id: name}`, `paid`, `title_en`.
- `stories`: own articles in markdown (`files {slug: path}`), `ready_for_owner`, `approve`; the "Editor notes" part is never rendered.
- `org`: `approve`, `approve_countries`, `reject`. Rows, people, logos, photos and profile links added by research carry `"review": "pending"` and are NOT covered by `approve_countries`: list their ids in `org.approve` (logos/photos: set `review` to `ok` in `assets/img/logos/logos.json` / `assets/img/people/photos.json`; news-source logos (`source:<id>` keys): set `review` to `ok` there too, nothing else, and they appear as `logo_url` / `source_logo_url` in the public API; profile links: `status: published` in `data/profiles.json`). The preview build shows all pending items, marked.
- `rules.json`: the rules page (`/rules/`) stays a placeholder until its `review` is set to `approved`.
- Changelog entries with `"review": "pending"` are only shown in the preview.
- Open-source developers (`data/developers.json`, `/developers/`): technical people in Nordic crypto with public crypto-related code (an own non-fork crypto repo, or merged commits or pull requests in a public crypto project; other open source does not count on its own). Every row added by research is `"status": "pending"`; the editor sets `published` after checking the profile, the Nordic-link source and the listed repos. Rows with `"review": "ready_for_owner"` (jQrgen's own) wait for jQrgen. The public build shows only published rows, the preview shows pending ones marked. GitHub links shown on Who's who for the same people are profile links in `data/profiles.json` (`kind: github`, `status: pending` until published). `tools/check_dev_profiles.py` re-checks the profiles and repos against the public GitHub and GitLab APIs (no token needed for a few rows; `GITHUB_TOKEN` for a full run; `--write` updates stars and the check date).
- Academia: status column (`APPROVED` / pending / unverified / OUT) in `/workspace/nordic-crypto-research/academia.md`; only APPROVED rows reach the page.
- `changelog.json`: site changes only (not news), newest first.

## Bots
**Researcher (6031f46c)**: run `./fetch.sh --days 2` (daily), check `state/source_status.json` for failing sources, add missed stories/events with `--add` / `--add-event`, research org-chart candidates in `queue/review.json` and academia rows in `/workspace/nordic-crypto-research/academia.md` (every row: source, check date, status). Never invent; never circumvent blocks (vb.is returns 403 and stays disabled).

**Editor (0b7181d5)**: review `queue/review.json` on the box, or the same file on the [`fetch-queue` branch](#nightly-fetch-on-actions) when the nightly fetch runs in Actions. For each story write a 2–4 sentence English summary of what the story says, in your own words (plus `title_en` for Nordic-language headlines, and `title_i18n` for nn, nb, sv, da, fi, is, omitting the source language) into `queue/approved.json`, or reject. Approved rows reach `main` on their own pull request. The fetch pull request is not the approval, and it is not merged. A one-sentence intro is not enough for the front page. Stories already published with a one-sentence summary keep a longer blurb in `data/frontpage_blurbs.json` (en, nn, nb, sv, da, fi, is) until the summary itself is two or more sentences; other site languages show the English blurb. Approve/reject events (date, place, organiser must be on the organiser's page; label paid/sponsored; reject online webinars without a Nordic link). Approve org rows only when every row and link has a source. Then `./build.sh --preview` and look at it. Things involving jQrgen himself (e.g. events where he speaks, own stories) go to `ready_for_owner`, never straight to `approve`. After the English summary: write `summary_i18n` for nn, nb, sv, da, fi, is (own words, same facts, no new claims) and set `summary_i18n_source` to the English text; check new org rows, people, logos (does the image belong to the org?), photos (licence, right person) and profile links before approving them; check the rules page against `research/rules-claims-*.md`.

## Denmark (added 3 Oct 2026)
Denmark (DK) is in the country set, the fetch config and the event detection. No Danish content goes live without the editor's approval: Danish stories and events land as `pending`. Org-chart rows: the editor reviewed the 14 Danish rows and added DK to `org.approve_countries` on 3 Oct 2026, so Danish org rows are now approved per country like NO/SE/FI/IS (new Danish rows must still have a source for every row and link before they are added to `data/orgchart_nordic.json`). Researcher: Danish stories, events, org chart (Finanstilsynet, Danmarks Nationalbank, Erhvervsministeriet, Skatteministeriet/Skattestyrelsen, the FIU (Hvidvasksekretariatet), MiCA CASPs authorised in Denmark per the ESMA register) and academia rows.

## Kryptonytt gets its Norwegian news from here (4 Oct 2026)
Kryptonytt (/workspace/kryptonytt) no longer fetches or researches news itself: its nightly intake (`routines/nightly-intake.sh` there)
runs `tools/import_nordic_crypto.py`, which reads our `data/news.json` items with `country: "NO"` plus `queue/approved.json`
(status, approved_by/at, reject reason, English summary, nn/nb translation when `summary_i18n_source` matches, `title_en`,
`seen_via`, licensed images only) into Kryptonytt's queue. Read-only on our side; Kryptonytt's editor still approves every story.
So: keep `country` correct on every Norwegian story (`--add URL --country NO`), and the Kryptonytt intake must run after
`routines/nightly-fetch.sh` has finished (it waits for the `awaiting editor:` line in `logs/nightly-YYYYMMDD.txt`).
All Kryptonytt news sources not already here were merged into `sources.json` as `country: NO` with `merged_from: "kryptonytt 2026-10-04"`
(Norwegian RSS feeds, podcasts, `search`-type outlets, and `bing-no-kn`: Kryptonytt's per-site news search, `sites` × `site_terms`,
now supported by `fetch.py`). Keywords `Bitmynt` and `H100` were added. This adds ~215 requests (≈ 8 min at 2 s/host) to the nightly run.
`tools/crosssite_handoff.py` still runs; its Nordic Crypto -> Kryptonytt direction is now redundant (the import enriches those rows).

## Reader tips (added 3 Oct 2026; own tip server 3 Oct 2026)
**Since 8 Oct 2026 the public site takes no tips:** `/tip/` only says that private tips are on the way. The public GitHub issue form is no longer offered on the page; the private intake (`tipworker/`) replaces it when it goes live.

**Private tip inbox (the /tip/ form, not live yet).** Every language version of `/tip/` posts a free-text tip to the Cloudflare Worker in `tipworker/` (`POST /api/private-tip`, D1 table `private_tips`, `migrations/0005_private_tips.sql`). Fields: `tip` (required, ≤ 8000 characters), `attachments` (up to 10 http/https links), `contact` (optional, never published), plus the page language and path. Cloudflare Turnstile is required (`TURNSTILE_SECRET`, shared with the shoutbox; without it the route answers 503 and stores nothing). The IP is not stored; rate limiting reuses the salted daily hash. The newsroom reads tips with `GET /api/private-tips` and marks them with `POST /api/private-tips/<id>` (`Authorization: Bearer $PRIVATE_TIPS_READ_TOKEN`, no CORS). An optional https webhook (`TIP_WEBHOOK_URL`, `TIP_WEBHOOK_BEARER`) gets each stored tip. The page stays closed (the "private tips are coming" notice, no form) until **both** the Worker's fixed endpoint (`public_endpoint`, written by `tipworker/deploy.sh`, or env `TIP_ENDPOINT`) and a Turnstile site key (env `TIP_TURNSTILE_SITE_KEY`, `turnstile_site_key` in `tipserver/config.json`, else the shoutbox key in `chat/config.json`) are set. It never posts to the box server or a quick tunnel and never falls back to a GitHub issue. Article-URL tips (`POST /api/tip`, table `tips`, `tipworker/pull.py`) are unchanged. Tests: `tests/test_tip_page.py`, `tipworker/tests/private_tips.test.mjs`.

**Older box tip server (not the /tip/ form).** `tipserver/server.py` (Python stdlib + SQLite) listens on `127.0.0.1:8787`:
`POST /api/tip` (JSON or form: `url` required http/https, `country` NO/SE/DK/FI/IS/unsure, `note` ≤ 1000 chars, optional `name` ≤ 100, honeypot `website` must be empty) and `GET /api/health`.
Body capped at 4 KB, in-memory per-IP rate limit (5 per 10 min; IPs are hashed in memory only, using `CF-Connecting-IP` behind the tunnel), CORS for the public site origin and `https://jqrgen.github.io` (Kryptonytt), other browser origins get 403.
Tips go to `tipserver/tips.db` (gitignored, mode 600) with a UTC timestamp and status `pending`. **No IP address, user agent or request body is stored or logged**; `tipserver/server.log` has only time, method, path and status.
- Keep it running: `tipserver/run.sh start|stop|restart|status`. `run.sh start` launches `tipserver/supervise.sh` detached (setsid + nohup), which restarts the server whenever it exits (back-off 1–30 s). The box has no systemd or cron, so `routines/nightly-fetch.sh` calls `tipserver/run.sh ensure` to bring it back after a box restart.
- Test: `curl -s http://127.0.0.1:8787/api/health` and `curl -s -H 'Content-Type: application/json' -d '{"url":"https://example.no/a","country":"NO"}' http://127.0.0.1:8787/api/tip`.
- Public access (decided 4 Oct 2026: box tip server + Cloudflare quick tunnel instead of Workers/D1; **not live yet**). `tipserver/config.json`:
  `quick_tunnel: true` – `run.sh start|ensure` also starts the watchdog `tipserver/tunnel.sh` (no login, random `*.trycloudflare.com` URL). It first checks outbound port 7844 to Cloudflare's edge; if blocked it re-checks every 10 min and starts cloudflared as soon as the port opens. A URL is used only after it answers `/api/health`; it is written to `tipserver/tunnel-url.txt` (deleted whenever the tunnel is down, so a stale URL is never served) and `tipserver/tunnel.state` (`blocked-7844` / `starting` / `up <url>` / `down`). The tunnel is restarted when cloudflared exits or the public health check fails 3× in a row.
  Every URL change runs `tipserver/publish_endpoint.sh`: it always rewrites `site/tip-endpoint.json` (and `site-tip-preview/tip-endpoint.json`) locally, and pushes ONLY `tip-endpoint.json` to gh-pages only if `auto_publish_endpoint: true`.
  `tip_page_uses_server` no longer changes `/tip/`: the page only opens for the private inbox on the Worker (above). It still decides what `tip-endpoint.json` holds.
  Local screenshot build (never published): `TIP_PAGE_SERVER=1 NC_SITE_DIR=$PWD/site-tip-preview .venv/bin/python build.py` -> `site-tip-preview/tip/index.html`.
  **To go live (only with jQrgen's approval):** set `tip_page_uses_server: true` and `auto_publish_endpoint: true`, then `tipworker/publish_tip_page.sh` (dry run) and `tipworker/publish_tip_page.sh --yes` (pushes only the /tip/ pages + tip-endpoint.json).
- **Port 7844 is blocked from this box (re-checked 4 Oct 2026, TCP and QUIC, also with `--protocol http2`)** – every Cloudflare tunnel (quick or named) needs it, so the tunnel watchdog sits in `blocked-7844`. Public access needs a network that allows outbound 7844, or another way to expose the server.
- No systemd/cron on the box: after a box restart nothing runs until `routines/nightly-fetch.sh` calls `tipserver/run.sh ensure` (or someone runs it by hand). The public `/tip/` page does not depend on this box and never falls back to a GitHub issue.

**GitHub issues (retired for new tips).** The [Send a tip](https://nordiccrypto.no/tip/) page no longer opens `.github/ISSUE_TEMPLATE/tip.yml`; the template tells people not to send a tip there. `tools/reader_tips.py` can still import an old open `tip` issue. Issues are never commented on or closed automatically.

**Nightly import.** `routines/nightly-fetch.sh` runs `tools/reader_tips.py`: pending rows in `tipserver/tips.db` -> `data/news.json` + `queue/review.json` as `pending` with origin `reader tip #<id>`, and the row is marked `imported` / `duplicate` / `invalid` (with `imported_at`, `queue_item_id`). Open `tip` issues are imported the same way with origin `reader tip (GitHub #N)`. Dedup: normalised-URL check from `tools/crosssite_handoff.py` against all stories (incl. rejected) and `approved.json`. Page metadata only where robots.txt allows. **The tipster's name is never read or copied**; the note stays in the local queue only (`tip_note_local_only`). Nothing is auto-published. Editor: treat tips like any other story. Dry run: `--dry-run`.

## Article archive
`archive/articles.db` (SQLite, gitignored) + `archive/articles.json` (committed export). Schema `archive/schema.sql`, shared with Kryptonytt (plus the additive `country` column); D1 mirror `tipworker/migrations/0002_articles.sql`. Rows are never deleted (triggers); a story that disappears gets `removed = 1` and `removed_at`. `routines/morning-publish.sh` runs `tools/article_archive.py record` after each successful publish; `backfill` reads the gh-pages history.

## Newsletter (own list)
`newsletter/email-list.md` is the setup for jQrgen: D1 table `subscribers`, DNS for Resend or Mailgun, Worker secrets, and how to send an issue. Cloudflare Email Routing can receive replies; it does not send the list. The site form (footer, front page, `/newsletter/#signup`, 7 languages, consent checkbox, privacy note) stays behind `newsletter/config.json` `enabled: false` until the Worker is deployed and that flag is set. While it is off, those places do not show an email field. They say signup opens soon and link to each language's `rss.xml`, Telegram and X. It posts to the tipworker (`/api/subscribe`, double opt-in, private D1, see `tipworker/README.md`). `newsletter/digest.py` builds a weekly digest from the **public** build only. `newsletter/send_issue.py` mails a published issue, or that digest, to confirmed addresses. Nothing is sent unless `MAIL_SEND_ENABLED=1`. Sign-off: The Nordic Crypto team. Kaupr is a news source only.

## Event NFT prototype (off)
A switched-off prototype for a generated event card on Nexa and Bitcoin Cash. The public build does not mint and shows nothing of it. `NC_EVENT_NFT=1` (or `features.event_nft` in `queue/approved.json`) turns it on for a local build: a mint panel on each upcoming or ongoing event page (`/calendar/<id>/`), `/treasury/` with both hot-wallet addresses, the caps, a public refill and mint history and a balance chart (`/faucet/` redirects there), and `/api/v1/treasury.json` and `/api/v1/treasury/history.json`. Code: `tools/event_nft.py`, styles `assets/css/nft.css` (page-only), strings `i18n/event_nft_strings.py` (all languages, merged by `i18n.strings`), sample data `data/event_nft_fixture.json`, design notes `docs/event-nft-design.md`. Card images and QR codes need Pillow and `segno`.

The mint Worker is `mintworker/` (`nordic-crypto-mint`, D1 `nordic-crypto-mint`, testnet only): it signs Nexa and chipnet transactions with pure-JS signers when `NC_EVENT_NFT=1` and `MINT_NETWORK=testnet`, refuses mainnet, rate-limits `/api/mint`, records the treasury history hourly, and has an admin-token route `POST /api/admin/setup-tokens?chain=nexa|bch` that creates the Nexa group or the CashTokens category once. The hot keys stay in the Worker secrets `NEXA_HOT_KEY` and `BCH_HOT_KEY`. Tests: `cd mintworker && npm test`. Operator steps are in [mintworker/README.md](mintworker/README.md). This repo does not deploy it.

## Electrum server (added 9 Oct 2026)
Our own Electrum server for Bitcoin Cash and Nexa, so wallets and apps do not depend on public servers. It runs on a Hetzner Cloud server (`electrum-1`): Bitcoin Cash Node and Nexa, each with Rostrum on top. It is reachable on the standard Electrum ports: Nexa at `wss://electrum-nexa.nordiccrypto.no:20004` (TLS `:20002`) and BCH at `wss://electrum-bch.nordiccrypto.no:50004` (TLS `:50002`). This repo does not deploy it. Setup, services and upgrade steps are in [docs/electrum-server.md](docs/electrum-server.md).

## Shoutbox
One shared reader chat for every language. The front page can show a compact box (a sidebar on a wide screen, a collapsible block on a phone) and each language has `/chat/` (or `/sv/chat/` and so on). Every one of those pages reads and writes the same message list. Only the buttons and the house rules are translated. A small language tag can show which page a message was sent from. The messages themselves are not translated.

It is off. `chat/config.json` is `"enabled": false` and `"endpoint": null`. While that is false, the build does not include the widget or the chat pages. Nothing on the live site calls a missing backend.

The worker is the existing `nordic-crypto-tips` Worker (`tipworker/`, D1 `nordic-crypto-tips`). Posts need Cloudflare Turnstile. A daily-rotated hash of the IP is stored for rate limits, reports and bans. The raw IP is not stored, and the chat does not set a cookie. The nickname is kept in the browser’s local storage. House rules sit on the box and link to [Editorial ethics](https://nordiccrypto.no/ethics/) (Vær Varsom): no harassment, no doxxing, no financial-advice shilling, no scams or referral links. Moderators may remove posts. Three reports from different daily hashes hide a message until it is reviewed. Reader messages are not editorial content.

This change does not deploy the worker and does not set secrets. The steps (migration `tipworker/migrations/0004_shouts.sql`, Turnstile site key, `TURNSTILE_SECRET`, `SHOUT_ADMIN_TOKEN`) are in [tipworker/README.md](tipworker/README.md#shoutbox-one-shared-room--srcshoutsjs-migrations0004_shoutssql). Short form, run by hand from `tipworker/` after `CLOUDFLARE_API_TOKEN` is set:

1. Create a Turnstile widget for nordiccrypto.no (and www, plus nordiccrypto.se / .fi / .dk / .is, apex and www). Keep the secret key out of git.
2. `npx wrangler secret put TURNSTILE_SECRET` and `npx wrangler secret put SHOUT_ADMIN_TOKEN` (`openssl rand -hex 32` for the admin token). `deploy.sh` does not set these.
3. `npx wrangler d1 migrations apply nordic-crypto-tips --remote` (or `./deploy.sh`, which applies migrations and deploys the worker, and still does not publish the site).
4. Set `chat/config.json` to `"enabled": true`, `"endpoint": "https://nordic-crypto-tips.nordiccrypto.workers.dev"` and `"turnstile_site_key": "<site key>"`.
5. `./publish.sh --yes` only with jQrgen’s approval.

Hide, delete, restore, ban and unban: `POST /api/shouts/admin` with `Authorization: Bearer <SHOUT_ADMIN_TOKEN>`. A ban matches today’s hash only, because yesterday’s salt is deleted.

## Page themes (added 8 Oct 2026)
Each section has its own look, figures and animations, layered on the Våpen tokens: [`themes.py`](themes.py) maps the `nav` key of `page()` to a theme, and the CSS and scripts are in [`assets/themes/`](assets/themes/) (`_base.*` is shared). News and stories: the serious Våpen look with a moving aurora. Calendar and event pages: green code rain. Markets: 8-bit monster battle with HP bars from the 24h change. Who's who: pirate sea chart with wanted-poster cards. API: crashed space station hackerspace (c-base Berlin style). Newsletter: printing press. Talks: synthwave VHS. Academia: classical Athens (marble, Greek-key borders, Doric columns, an owl and laurel). About: northern lights and a longship. Send a tip: film noir. Sources: tekst-TV. Pages not listed keep the plain look. All figures are our own drawings; no third-party characters, logos or fonts. Decoration is one `aria-hidden` layer behind the content, and `prefers-reduced-motion` stops every animation.

## Look and stylesheet
**Logo and media kit (`/media/`).** The kit is the key shield from the front page. `tools/make_mark.py` draws the shield, favicon and icons; `tools/make_brand.py` adds the one-colour shield, the lockups with the name (Cormorant Garamond Bold as outlines) and the large PNGs. Themed pages keep their own look; only `/media/` was rebuilt. The older crest files stay in the repo but are no longer offered there.

The look is the Våpen design from the logo sheet (option E) in the Langskip colours (option A): a North Sea (`#1E3A45`) band for the header, the front-page title, the lead story and the footer, a Sailcloth (`#F0F1EC`) page, Pine Tar (`#1D1C1A`) text, Shield Gold (`#D9A034`) for primary actions, the active section, country codes and date badges, and Sea Foam (`#BFD3D3`) for the rule under the band. Headings are Cormorant Garamond (bold), text is Schibsted Grotesk, and small labels (section labels, dates, table headers) are IBM Plex Mono. Lists are rows divided by hairlines; cards only group interactive data. Everything stays start-aligned (right-aligned on the Arabic and Urdu pages), and text in a left-to-right language inside those pages reads left to right.

Light is the default. The button in the header switches to dark; the choice is stored in this browser's localStorage as `nc-theme` (the office screen mode uses the same key) and read by an inline script in `<head>`, so there is no flash. Dark mode does not follow the system setting.

Layout: the header has seven sections (News, Calendar, Markets, Who's who, Academia, Books, Talks), the newsletter button (Subscribe while signup is open, Follow until then), Telegram and X, the light/dark switch and the language; on phones the brand, the switch and a menu button. Open-source developers (`/developers/`) is linked from Who's who and the footer, not the header. Newsletter, Sources, About, Send a tip and the API are in the footer columns and the phone menu (`NAV`, `NAV_MAIN` in `build.py`). The front page is a short title band, the lead story with the next events beside it, then the latest stories in one column (20 shown, the rest behind one button), then the newsletter and tools. Long pages start with what readers come for, have a short "On this page" list, and collapse secondary detail.

The CSS is one file per part of the site in `assets/css/`. `site_css.SITE` lists the modules inlined into every page (`build.CSS`): `fonts` (the `@font-face` rules; font URLs are root-relative, `__ROOT__` is replaced at build time), `tokens` (colours for both themes, radii, the market chart's series colours `--mk-1` to `--mk-8`), `base`, `header`, `footer`, `components`, `news`, `events`, `home`, `newsletter`, `push` and `shoutbox`. Every other module is inlined only by its page with `site_css.style(name)`: `orgchart`, `markets`, `talks`, `sources`, `academia`, `filterbar`, `calendar`, `evpage`, `story`, `textpage`, `brand`, `rules`, `regulation-videos` and `api-docs`. Colours come from the custom properties in `tokens.css`; inside the band (`header.top`, `.hero`, `.leadstory`, `footer`) the same names point to light-on-dark values. Primary buttons use `--btn` (North Sea; gold in dark mode and on the band). Flags are one shared `<symbol>` per page (`flag()` emits `<use>`, `page()` adds the symbols it finds); `flag(c, deco=True)` hides a flag from screen readers where the country is named beside it. Fonts are self-hosted in `assets/fonts/` (SIL Open Font License): Schibsted Grotesk is one variable woff2 (400–900), and two fonts are preloaded. `assets/brand/nordic-crypto.css` is the brand stylesheet for others; site pages do not load it. The office screen mode (`templates/screen.html`) keeps its own styles.

## Privacy
No health or private financial data about anyone, no org numbers, LEIs, addresses of private persons, emails or tokens. `state/private_terms.json` (never printed, never committed) feeds the privacy gate, which blocks the build if it finds them. The [automatic deploy](#automatic-deploy) writes that file from the Actions secret `NC_PRIVATE_TERMS_JSON` for the gate and deletes it before anything is pushed. The gate also blocks organisation numbers in visible text, including source titles (NO 9-digit, SE NNNNNN-NNNN, DK CVR, «org.nr …»); register links are fine, the number itself must not be written out.

`data/` (stories, events, org chart, translations of the industry map, profile links, academia) is committed to the repo so the content is not stored only on the box; it is public content and passes the privacy gate (`tools/privacy_gate.py data`). `queue/`, `state/`, `logs/`, `site/` and `tipserver/tips.db` stay box-only (`queue/` can hold local-only reader-tip notes).

**Language rule (text gate).** Our own Norwegian text (nn, nb) never says «AI» or «KI»; write «kunstig intelligens» in full. `tools/text_gate.py` checks the nn/nb interface strings, templates, summaries, event notes, changelog and rules-page strings, and runs in `build.sh` and `publish.sh`. External headlines are left as published.

**Browser notifications.** Off until the reader turns them on. The Worker stores only the push subscription, the page language and the countries they picked. Unsubscribe is the same button. Cloudflare Web Analytics still counts visits in aggregate, without cookies, and that data is not sold. See [Browser notifications](#browser-notifications).

**Privacy and data policy (`/privacy/`, every language).** One page for everything the site does with data: GitHub Pages and Cloudflare hosting (country domains, cryptonordic.no redirect), the browser storage keys (`nc_lang` cookie and local storage, `nc_auto`, `nc-theme`, `nc_push_countries`, `nc_shout_nick`), the IP-country language guess via tipworker `/api/geo`, Cloudflare Web Analytics (details stay at `/stats/#data-policy`), the markets page calling Firi and Coinmotion from the browser, click-to-load YouTube (nocookie) and Vimeo players, the newsletter (D1 + Resend or Mailgun), Web Push, private tips, the shoutbox, Turnstile and GitHub issues. Each part gives what, purpose, legal basis, retention, processor and transfers outside the EEA. Optional services show “On” or “Not switched on yet” from the same switches the build uses (`analytics_token()`, `geo_endpoint()`, `newsletter_endpoint()`, `push_endpoint()`, `tip_intake()`, `chat_endpoint()`). Text: `templates/privacy.html` (English), `privacy.nb.html`, `privacy.nn.html`; other languages show the English text with a short note in their language (`pp_note`). Strings `pp_*` in `i18n/`. Linked from the footer, the stats page and About. When a new third-party script, embed, storage key or data store is added, update this page in the same change; `tests/test_privacy_page.py` fails when the build injects a script or iframe host the page does not name.

**Visitor stats (GDPR).** `/stats/#data-policy` is the data policy for the published Cloudflare Web Analytics numbers: who is responsible (jQrgen), what the beacon collects, that only daily, weekly and monthly totals are published, the legal basis (GDPR Art. 6(1)(f), legitimate interest), retention (Cloudflare about six months; the site keeps only daily totals), Cloudflare, Inc. as processor, and questions through GitHub issues or a complaint to Datatilsynet. While `analytics.json` has no token, the section says the script is not switched on yet. The footer and About link to it. Strings: `vdp_*` in `i18n/`.

**Shoutbox.** Off until `chat/config.json` is enabled. When it is on, the worker stores the nickname, the message and a daily-rotated IP hash. It does not store the raw IP and it does not set a cookie. The nickname stays in local storage. Cloudflare Web Analytics is unchanged: aggregate visits, no cookies, data not sold. The About page says the same.
