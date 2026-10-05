# Nordic Crypto

Bitcoin, blockchain and crypto news, events, a who's who (industry + regulators), regulation by country and academia for
**Norway, Sweden, Denmark, Finland and Iceland**. Static site. Cloudflare Web Analytics counts aggregate visits (no cookies, data not sold) when a token is set in `analytics.json`. No advertising trackers.
Languages: English at `/`, and one directory per other site language. The list, native names and the IP-country guess are under [Site languages](#site-languages). External headlines and quotes stay in the original language; our own summaries are written first in English, then translated for the Nordic site languages (AI-assisted, editor-approved).
Planned URL: https://jqrgen.github.io/nordic-crypto/ (all links are relative). Run by jQrgen (Jørgen S. Notland), MIT licence.

**Status:** live at https://jqrgen.github.io/nordic-crypto/ (gh-pages). Code on `main`. Every publish needs jQrgen's explicit approval.

## Site languages
Site interface and page presentation. News outlets stay as listed in `sources.json`. UI strings live in `i18n/<code>.py`. A missing key falls back to English, which is how the languages beyond the Nordic set are shipped until a real translation is written. Article bodies are not machine-translated for those languages. English is the site root. Every other code is `/<code>/`.

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

`zh` is one site language for Mandarin (simplified and traditional readers share `/zh/`). `pt` covers Portugal and Brazil. `nn` stays the Norwegian default; bokmål is the quick link beside the switcher.

**How a first visit picks a language** (`tools/langselect.js`, only on the English home page). A direct link to `/sv/`, `/de/` or any other page is never redirected.

1. `nc_lang` cookie, set only when the reader picks a language in the switcher (one year, this site only). The same choice is copied to `localStorage` under `nc_lang`. The cookie wins when both are set. If the cookie is missing, the stored value is the same override.
2. Our tipworker `GET /api/geo`, which returns Cloudflare's `request.cf.country` (two letters, or null). Nothing is stored or logged, and no third-party geo-IP service is used. The Worker URL is injected at build time when `tipserver/config.json` has a `workers.dev` `public_endpoint`, or when `GEO_ENDPOINT` is set. The country is a default guess: Norway → nynorsk, Sweden → Swedish, Denmark → Danish, Finland → Finnish, Iceland → Icelandic, Åland → Swedish, Faroe and Greenland → Danish, and the major countries for the languages above (China, Taiwan and Singapore → Chinese, India → Hindi, Spain, Mexico and Argentina → Spanish, France → French, Saudi Arabia, Egypt and the UAE → Arabic, Bangladesh → Bengali, Brazil and Portugal → Portuguese, Russia → Russian, Pakistan → Urdu, Indonesia → Indonesian, Germany, Austria and Switzerland → German, Japan → Japanese, Kenya and Tanzania → Swahili). A country with no row, including the United States and the United Kingdom, stays English. India is Hindi; Marathi has no country row. Mauritania (`MR`) is Arabic; the language code `mr` is Marathi.
3. If the Worker is not deployed or does not answer within 1.5 seconds: `navigator.languages`. Norwegian tags (`no`, `nb`, `nn`) still default to nynorsk.
4. English.

After one automatic choice, `sessionStorage` `nc_auto` stops a second redirect in that tab. The full country map is in `tools/langselect.js` (`BY_COUNTRY`) and in `/api/v1/geo-language.json`.

## Data API
Public JSON for apps and other tools, written into `site/` by `./build.sh` (`tools/api_feed.py`). No account. News, newsletters, events, sources, academia, the who's who, profiles, the rules map, the changelog and the article archive.

- Human docs: https://jqrgen.github.io/nordic-crypto/api/ and https://cryptonordic.no/api/ (same page; the custom domain serves the site root)
- Discovery: `/api/v1/index.json`
- OpenAPI: `/api/v1/openapi.json` and `/api/v1/openapi.yaml`
- Languages: `/api/v1/languages.json` (code, native name, English name, rtl, html lang, home URL). The same fields are on each entry in `/api/v1/meta.json` `languages`.
- Geo language: `/api/v1/geo-language.json` (country → default language). The note there says the `nc_lang` cookie wins and the IP country is a guess from tipworker `/api/geo` (Cloudflare `request.cf.country`).
- `llms.txt` at the site root, and `/.well-known/api-catalog`

News: `/api/v1/news.json` and `/api/v1/news/{id}.json`. Newsletters: `/api/v1/newsletters.json` and `/api/v1/newsletters/001.json`. GitHub Pages sends `Access-Control-Allow-Origin: *` on the files. `python3 tools/api_feed.py` writes the same JSON from the committed public data without building the rest of the HTML. That command also fetches live exchange prices (see below).

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
- Same paths on the custom domain, at the site root (`https://cryptonordic.no/api/v1/markets.json`)
- Page: `/markets/` (linked from the nav and the homepage)

Aggregation is one row per base-quote pair. BTC-NOK is not averaged with BTC-EUR. `last` is the arithmetic mean of published last prices (decimal arithmetic, not a float). `mid` is the mean of `(bid+ask)/2` where both exist, and is not mixed into `last`. `price` equals `last` when any last exists, otherwise `mid`. `min` and `max` use that same series. `exchange_count` is how many exchanges quoted the pair. `updated_at` is the newest `fetched_at`. There is no VWAP: the volume windows are not the same, so volume is not a weight. Volume sums add only the same field inside the same pair. `logo_url` is an SVG from [cryptocurrency-icons](https://github.com/spothq/cryptocurrency-icons) 0.18.1 (CC0-1.0) when that set includes the asset, and null otherwise. Nordic Crypto does not draw substitutes (POL has none; the MATIC icon is not reused).

Refresh: `./build.sh` and `./publish.sh` fetch the exchanges while building `site/`. `.github/workflows/markets-refresh.yml` rewrites the markets JSON on `gh-pages` about hourly (minute 17), including `aggregated.json`, the per-asset files and `api/v1/markets/logos/`, and leaves the previous files in place if every exchange fails. The markets page reloads `/api/v1/markets.json` about every 15 minutes and recomputes the aggregate from the tickers on the page. Firi and Coinmotion send `Access-Control-Allow-Origin: *`, so the page also requests those APIs from the browser about every 5 minutes. `api.nbx.com` does not send that header, so NBX rows follow the file.

`python3 tools/markets.py` prints a short summary. `python3 tools/markets.py --write DIR` writes the JSON tree. `--keep-if-empty` is what the hourly job uses.

### iOS app
Public TestFlight invite, linked from the footer, the homepage, `/markets/` and About: https://testflight.apple.com/join/nQ2fpjZn. There is no App Store listing.

## Pipeline
| Step | Command | What it does |
|---|---|---|
| Fetch | `./fetch.sh [--days N]` | Reads RSS feeds / list pages / news search per country (robots.txt respected, own UA, ≥2 s per host), filters on multilingual crypto keywords, adds new stories to `data/news.json` as `pending`, new events to `data/events.json` as `pending`, candidate entities to `queue/review.json`. |
| Add a story by hand | `./fetch.sh --add URL --country XX [--date YYYY-MM-DD]` | Metadata only (title/description/date), never article text. |
| Add an event by hand | `.venv/bin/python events.py --add-event URL --country XX [--title --start --place --organiser --paid --online]` | Event lands as `pending`. |
| Local preview | `./build.sh --preview` | Builds `site/` incl. pending items, clearly marked, `noindex`, robots disallow, writes `site/.preview`. Then the privacy gate. |
| Public build | `./build.sh` | Only approved content. |
| Publish (later) | `./publish.sh --yes` | ONLY after jQrgen approves. Refuses a preview build; on first run creates the git repo and `jQrgen/nordic-crypto`, pushes `site/` to `gh-pages`, code to `main`, stamps the launch date in `changelog.json`. Without `--yes` it only builds and checks. |
| QA screenshots | `.venv/bin/python tools/screens.py` | Serves `site/` on a free local port, screenshots every page into `shots/`, reports JS errors, 4xx and horizontal overflow. |

Other tools: `tools/probe.py` (feed checks), `tools/import_orgchart.py` (merges the Norwegian Kryptonytt industry map, translated via `data/no_en.json`, with `data/orgchart_nordic.json`), `tools/import_academia.py` (reads the researcher's `academia.md` and its editor status column), `tools/seed_academia.py` (DOI-checked publication candidates), `tools/privacy_gate.py`, `tools/commons_photo.py` (Wikimedia Commons photos with licence + credit only), `tools/fetch_logos.py` (one logo per org and per news outlet from Wikidata/Commons or the outlet's own site → `assets/img/logos/logos.json`, review pending), `tools/rules_page.py` (rules page from `rules.json`), `tools/regulation_videos.py` (country explainer slots at `/regulation-videos/`), `tools/article_archive.py` (append-only article archive).

## Outlet logos on news

Whenever a story is shown (the news list, the screen, our own story pages, and the HTML newsletter digest) the outlet logo sits beside the source name when a checked image is on file. The name is text only when there is no logo. Nothing is drawn or invented. The site brand stays Nordic Crypto. Kaupr is a news source, and its logo appears only next to Kaupr stories.

`assets/img/logos/logos.json` is the map. `tools/source_logos.py` resolves a story's `source` field like this:

1. The id is the source id in `sources.json` (the same id stored on the news item).
2. If that source has `outlet`, the parent id is used (for example `kaupr-no` → `kaupr`, `nrk-siste` → `nrk`).
3. `_source_alias` sends a source id to a different logo key when the who's-who id is not the source id: `fi-se` → `se-fi`, `riksbank` → `se-riksbank`, `suomenpankki` → `fi-suomen-pankki`, `finanssivalvonta` → `fi-fiva`, `stortinget` → `stortinget-finanskomiteen` (the Storting coat of arms), `nbx-ir` → `nbx`, `digi-krypto` → `digi`.
4. That key's `file` is the image path, relative to the repo root (`assets/img/logos/<id>.svg` or `.webp`).

The public site shows a logo only when `review` is `ok` (a missing review counts as ok). `./build.sh --preview` also shows `pending`. `rejected`, a missing file, or no entry: text only. `python3 tools/fetch_logos.py` fills gaps for enabled outlets and for any source that already has a published or pending story. New files stay `pending` until an editor checks that the image belongs to that outlet.

## Regulation explainer videos
`/regulation-videos/` has one slot each for Norway, Sweden, Denmark, Finland and Iceland, linked from `/rules/` and About. Scripts, storyboards, posters and sources are in `regulation-videos/`. Institution names and source URLs are read from the editor-approved `rules.json` at build time. Iceland is in the EEA, not the EU, and Seðlabanki Íslands houses Fjármálaeftirlit. Drop `video-XX.mp4` in `regulation-videos/media/` (gitignored) and the slot plays it with the HTML5 player. Until then the slot shows the title, the narrator notes and the sources. The films are not rendered yet. Substack drafts in `regulation-videos/substack/` are for human review only; the build does not send them. Sign-off: The Nordic Crypto team. Kaupr is a news source only and is not a sponsor of these films.

## Approval model (`queue/approved.json`)
- `items`: `{url, summary (1–2 sentences, English, own words), summary_i18n {nn, nb, sv, da, fi, is}, summary_i18n_source (the English text the translations were made from – if the summary changes, the translations are dropped until redone), title_en, topics, approved_by, approved_at}`; `rejected`: `{url | title_contains, reason}`.
- `events`: `approve`, `reject`, `ready_for_owner` (editor-approved, waiting for jQrgen: preview only), `notes`, `notes_i18n {id: {lang: text}}`, `sponsor {id: name}`, `paid`, `title_en`.
- `stories`: own articles in markdown (`files {slug: path}`), `ready_for_owner`, `approve`; the "Editor notes" part is never rendered.
- `org`: `approve`, `approve_countries`, `reject`. Rows, people, logos, photos and profile links added by research carry `"review": "pending"` and are NOT covered by `approve_countries`: list their ids in `org.approve` (logos/photos: set `review` to `ok` in `assets/img/logos/logos.json` / `assets/img/people/photos.json`; profile links: `status: published` in `data/profiles.json`). The preview build shows all pending items, marked.
- `rules.json`: the rules page (`/rules/`) stays a placeholder until its `review` is set to `approved`.
- Changelog entries with `"review": "pending"` are only shown in the preview.
- Academia: status column (`APPROVED` / pending / unverified / OUT) in `/workspace/nordic-crypto-research/academia.md`; only APPROVED rows reach the page.
- `changelog.json`: site changes only (not news), newest first.

## Bots
**Researcher (6031f46c)**: run `./fetch.sh --days 2` (daily), check `state/source_status.json` for failing sources, add missed stories/events with `--add` / `--add-event`, research org-chart candidates in `queue/review.json` and academia rows in `/workspace/nordic-crypto-research/academia.md` (every row: source, check date, status). Never invent; never circumvent blocks (vb.is returns 403 and stays disabled).

**Editor (0b7181d5)**: review `queue/review.json`; for each story write a 1–2 sentence English summary in your own words (plus `title_en` for Nordic-language headlines) into `queue/approved.json`, or reject. Approve/reject events (date, place, organiser must be on the organiser's page; label paid/sponsored; reject online webinars without a Nordic link). Approve org rows only when every row and link has a source. Then `./build.sh --preview` and look at it. Things involving jQrgen himself (e.g. events where he speaks, own stories) go to `ready_for_owner`, never straight to `approve`. After the English summary: write `summary_i18n` for nn, nb, sv, da, fi, is (own words, same facts, no new claims) and set `summary_i18n_source` to the English text; check new org rows, people, logos (does the image belong to the org?), photos (licence, right person) and profile links before approving them; check the rules page against `research/rules-claims-*.md`.

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
**Own tip server (primary, not public yet).** `tipserver/server.py` (Python stdlib + SQLite) listens on `127.0.0.1:8787`:
`POST /api/tip` (JSON or form: `url` required http/https, `country` NO/SE/DK/FI/IS/unsure, `note` ≤ 1000 chars, optional `name` ≤ 100, honeypot `website` must be empty) and `GET /api/health`.
Body capped at 4 KB, in-memory per-IP rate limit (5 per 10 min; IPs are hashed in memory only, using `CF-Connecting-IP` behind the tunnel), CORS only for `https://jqrgen.github.io`, other browser origins get 403.
Tips go to `tipserver/tips.db` (gitignored, mode 600) with a UTC timestamp and status `pending`. **No IP address, user agent or request body is stored or logged**; `tipserver/server.log` has only time, method, path and status.
- Keep it running: `tipserver/run.sh start|stop|restart|status`. `run.sh start` launches `tipserver/supervise.sh` detached (setsid + nohup), which restarts the server whenever it exits (back-off 1–30 s). The box has no systemd or cron, so `routines/nightly-fetch.sh` calls `tipserver/run.sh ensure` to bring it back after a box restart.
- Test: `curl -s http://127.0.0.1:8787/api/health` and `curl -s -H 'Content-Type: application/json' -d '{"url":"https://example.no/a","country":"NO"}' http://127.0.0.1:8787/api/tip`.
- Public access (decided 4 Oct 2026: box tip server + Cloudflare quick tunnel instead of Workers/D1; **not live yet**). `tipserver/config.json`:
  `quick_tunnel: true` – `run.sh start|ensure` also starts the watchdog `tipserver/tunnel.sh` (no login, random `*.trycloudflare.com` URL). It first checks outbound port 7844 to Cloudflare's edge; if blocked it re-checks every 10 min and starts cloudflared as soon as the port opens. A URL is used only after it answers `/api/health`; it is written to `tipserver/tunnel-url.txt` (deleted whenever the tunnel is down, so a stale URL is never served) and `tipserver/tunnel.state` (`blocked-7844` / `starting` / `up <url>` / `down`). The tunnel is restarted when cloudflared exits or the public health check fails 3× in a row.
  Every URL change runs `tipserver/publish_endpoint.sh`: it always rewrites `site/tip-endpoint.json` (and `site-tip-preview/tip-endpoint.json`) locally, and pushes ONLY `tip-endpoint.json` to gh-pages only if `auto_publish_endpoint: true`.
  `tip_page_uses_server` (default false) switches the built /tip/ page from the GitHub issue form to the server form (reads `/tip-endpoint.json` at runtime, no cache; if missing/unreachable it shows “temporarily offline” + the GitHub form). `public_endpoint` (fixed URL) still takes precedence.
  Local screenshot build (never published): `TIP_PAGE_SERVER=1 NC_SITE_DIR=$PWD/site-tip-preview .venv/bin/python build.py` -> `site-tip-preview/tip/index.html`.
  **To go live (only with jQrgen's approval):** set `tip_page_uses_server: true` and `auto_publish_endpoint: true`, then `tipworker/publish_tip_page.sh` (dry run) and `tipworker/publish_tip_page.sh --yes` (pushes only the /tip/ pages + tip-endpoint.json).
- **Port 7844 is blocked from this box (re-checked 4 Oct 2026, TCP and QUIC, also with `--protocol http2`)** – every Cloudflare tunnel (quick or named) needs it, so the tunnel watchdog sits in `blocked-7844`. Public access needs a network that allows outbound 7844, or another way to expose the server.
- No systemd/cron on the box: after a box restart nothing runs until `routines/nightly-fetch.sh` calls `tipserver/run.sh ensure` (or someone runs it by hand). While the box is off or the tunnel is down, the /tip/ page (once in server mode) shows the GitHub issue form as fallback.

**GitHub issues (fallback).** The [Send a tip](https://jqrgen.github.io/nordic-crypto/tip/) page currently opens the issue form `.github/ISSUE_TEMPLATE/tip.yml` (label `tip`; tips are public on GitHub). Issues are never commented on or closed automatically.

**Nightly import.** `routines/nightly-fetch.sh` runs `tools/reader_tips.py`: pending rows in `tipserver/tips.db` -> `data/news.json` + `queue/review.json` as `pending` with origin `reader tip #<id>`, and the row is marked `imported` / `duplicate` / `invalid` (with `imported_at`, `queue_item_id`). Open `tip` issues are imported the same way with origin `reader tip (GitHub #N)`. Dedup: normalised-URL check from `tools/crosssite_handoff.py` against all stories (incl. rejected) and `approved.json`. Page metadata only where robots.txt allows. **The tipster's name is never read or copied**; the note stays in the local queue only (`tip_note_local_only`). Nothing is auto-published. Editor: treat tips like any other story. Dry run: `--dry-run`.

## Article archive
`archive/articles.db` (SQLite, gitignored) + `archive/articles.json` (committed export). Schema `archive/schema.sql`, shared with Kryptonytt (plus the additive `country` column); D1 mirror `tipworker/migrations/0002_articles.sql`. Rows are never deleted (triggers); a story that disappears gets `removed = 1` and `removed_at`. `routines/morning-publish.sh` runs `tools/article_archive.py record` after each successful publish; `backfill` reads the gh-pages history.

## Newsletter (Substack live 2026-10-05; own form OFF)
`newsletter/substack-setup.md` (publication name, subdomain, texts, branding in `newsletter/assets/`, welcome email, digest
template, Kaupr disclosure, checklist for jQrgen). `newsletter/digest.py` builds the weekly digest from the **public** build
only (approved stories). Signup form (footer + `/newsletter/`, 7 languages, privacy note) is behind `newsletter/config.json`
`enabled: false`; it posts to the tipworker (`/api/subscribe`, double opt-in, see `tipworker/README.md`).
Substack publication: https://cryptonordic.substack.com (created by jQrgen 2026-10-05). `substack_url` in `newsletter/config.json`
makes the footer and `/newsletter/` (7 languages) link to its `/subscribe` page on its own, independent of `enabled`.

## Privacy
No health or private financial data about anyone, no org numbers, LEIs, addresses of private persons, emails or tokens. `state/private_terms.json` (never printed, never committed) feeds the privacy gate, which blocks the build if it finds them. The gate also blocks organisation numbers in visible text, including source titles (NO 9-digit, SE NNNNNN-NNNN, DK CVR, «org.nr …»); register links are fine, the number itself must not be written out.

`data/` (stories, events, org chart, translations of the industry map, profile links, academia) is committed to the repo so the content is not stored only on the box; it is public content and passes the privacy gate (`tools/privacy_gate.py data`). `queue/`, `state/`, `logs/`, `site/` and `tipserver/tips.db` stay box-only (`queue/` can hold local-only reader-tip notes).

**Language rule (text gate).** Our own Norwegian text (nn, nb) never says «AI» or «KI»; write «kunstig intelligens» in full. `tools/text_gate.py` checks the nn/nb interface strings, templates, summaries, event notes, changelog and rules-page strings, and runs in `build.sh` and `publish.sh`. External headlines are left as published.
