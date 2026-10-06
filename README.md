# Nordic Crypto

Bitcoin, blockchain and crypto news, events, a who's who (industry + regulators), regulation by country and academia for
**Norway, Sweden, Denmark, Finland and Iceland**. Static site. Cloudflare Web Analytics counts aggregate visits (no cookies, data not sold) when a token is set in `analytics.json`. No advertising trackers.
Languages: English at `/`, and one directory per other site language. The list, native names and the IP-country guess are under [Site languages](#site-languages). External headlines and quotes stay in the original language; our own summaries are written first in English, then translated for the Nordic site languages (AI-assisted, editor-approved).
Public URL: https://nordiccrypto.no/ (`site_url.json`; all in-site links are relative). Run by jQrgen (Jørgen S. Notland), MIT licence.

**Status:** live at https://nordiccrypto.no/ (gh-pages, CNAME). Code on `main`. Every publish needs jQrgen's explicit approval.

**Domains:** the old address https://cryptonordic.no/ (and www) answers with a 301 to the same path on https://nordiccrypto.no/ (Cloudflare page rules on the cryptonordic.no zone). nordiccrypto.se, .fi, .dk and .is (apex and www) serve the site under their own address, with the front page in the country's language (Swedish, Finnish, Danish, Icelandic), through the Cloudflare Worker in [`workers/country-domains/`](workers/country-domains/). Canonical URLs stay on nordiccrypto.no. nordiccrypto.eu forwards to https://nordiccrypto.no/ (Domeneshop HTTP forwarding). nordiccrypto.no DNS is at Domeneshop (GitHub Pages A/AAAA, www CNAME jqrgen.github.io).

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

- Human docs: https://nordiccrypto.no/api/
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
- Same paths on the custom domain, at the site root (`https://nordiccrypto.no/api/v1/markets.json`)
- Page: `/markets/` (linked from the nav and the homepage)

Aggregation is one row per base-quote pair. BTC-NOK is not averaged with BTC-EUR. `last` is the arithmetic mean of published last prices (decimal arithmetic, not a float). `mid` is the mean of `(bid+ask)/2` where both exist, and is not mixed into `last`. `price` equals `last` when any last exists, otherwise `mid`. `min` and `max` use that same series. `exchange_count` is how many exchanges quoted the pair. `updated_at` is the newest `fetched_at`. There is no VWAP: the volume windows are not the same, so volume is not a weight. Volume sums add only the same field inside the same pair. `logo_url` is an SVG from [cryptocurrency-icons](https://github.com/spothq/cryptocurrency-icons) 0.18.1 (CC0-1.0) when that set includes the asset, and null otherwise. Nordic Crypto does not draw substitutes (POL has none; the MATIC icon is not reused).

Refresh: `./build.sh` and `./publish.sh` fetch the exchanges while building `site/`. `.github/workflows/markets-refresh.yml` rewrites the markets JSON on `gh-pages` about hourly (minute 17), including `aggregated.json`, the per-asset files and `api/v1/markets/logos/`, and leaves the previous files in place if every exchange fails. The markets page reloads `/api/v1/markets.json` about every 15 minutes and recomputes the aggregate from the tickers on the page. Firi and Coinmotion send `Access-Control-Allow-Origin: *`, so the page also requests those APIs from the browser about every 5 minutes. `api.nbx.com` does not send that header, so NBX rows follow the file.

`python3 tools/markets.py` prints a short summary. `python3 tools/markets.py --write DIR` writes the JSON tree. `--keep-if-empty` is what the hourly job uses.

### iOS app
Public TestFlight invite, linked from the footer, the homepage, `/markets/` and About: https://testflight.apple.com/join/nQ2fpjZn. There is no App Store listing.

### Community
Nordic Crypto brand accounts, linked from the footer, About and the newsletter, in every site language (English until a translation is written):

- Telegram: https://t.me/nordiccryptochat
- X: https://x.com/xcryptonordic

The iOS app reads them from `social` on `/api/v1/meta.json` (`social.telegram`, `social.x`). `name` is English. `name_i18n` has nn, nb, sv, da, fi and is. The source-code link on each page stays.

## Pipeline
| Step | Command | What it does |
|---|---|---|
| Fetch | `./fetch.sh [--days N]` | Reads RSS feeds / list pages / news search per country (robots.txt respected, own UA, ≥2 s per host), filters on multilingual crypto keywords, adds new stories to `data/news.json` as `pending`, new events to `data/events.json` as `pending`, candidate entities to `queue/review.json`. |
| Add a story by hand | `./fetch.sh --add URL --country XX [--date YYYY-MM-DD]` | Metadata only (title/description/date), never article text. |
| Add an event by hand | `.venv/bin/python events.py --add-event URL --country XX [--title --start --place --organiser --paid --online]` | Event lands as `pending`. |
| Refresh events only | `.venv/bin/python events.py` or `.venv/bin/python events.py --only id,id` | Same event search as `./fetch.sh`, without the news feeds. |
| Local preview | `./build.sh --preview` | Builds `site/` incl. pending items, clearly marked, `noindex`, robots disallow, writes `site/.preview`. Then the privacy gate. |
| Public build | `./build.sh` | Only approved content. |
| Publish (later) | `./publish.sh --yes` | ONLY after jQrgen approves. Refuses a preview build; on first run creates the git repo and `jQrgen/nordic-crypto`, pushes `site/` to `gh-pages` while keeping `CNAME`, `kiosk/` and every top-level name in `publish-keep.txt`, sets the Pages custom domain to nordiccrypto.no, pushes code to `main`, stamps the launch date in `changelog.json`. Without `--yes` it only builds and checks. Aborts if the staged gh-pages tree has no `CNAME`. |
| QA screenshots | `.venv/bin/python tools/screens.py` | Serves `site/` on a free local port, screenshots every page into `shots/`, reports JS errors, 4xx and horizontal overflow. |

### Blockchain conference listings
`event_sources` in `sources.json` includes International Conference Alerts country pages, `type: listing-jsonld`. Checked 6 Oct 2026; each URL returned a list of blockchain conferences:

- Norway: https://internationalconferencealerts.com/blockchain/norway
- Sweden: https://internationalconferencealerts.com/blockchain/sweden
- Denmark: https://internationalconferencealerts.com/blockchain/denmark
- Finland: https://internationalconferencealerts.com/blockchain/finland
- Iceland: https://internationalconferencealerts.com/blockchain/iceland

`events.py` reads the listing, keeps event links (`link_pattern`, crypto keywords unless the source is `trusted`, soonest first, at most `max_links`), and reads schema.org `Event` JSON-LD on each event page: title, start, end, place, organiser and URL. A street address under a Venue label is used when it is more specific than the city. Dates published as `00:00:00Z` are stored as that calendar day in the event country's time zone, and the calendar shows the dates without a clock time. No photos are copied. The calendar links to the event page.

These pages list academic conferences that put blockchain in the title. They are not auto-published. New rows land as `pending` in `data/events.json`. `./build.sh --preview` shows them, marked as waiting for the editor. The public calendar shows one after its id is added to `events.approve` in `queue/approved.json` (date, place and organiser must be on the listing or the organiser's page).

Refresh: `./fetch.sh` or `.venv/bin/python events.py`. One country: `.venv/bin/python events.py --only ica-blockchain-norway`. robots.txt is respected (the site allows `/`; `/*_rsc=` is disallowed and is not requested). The usual per-host delay applies. If Cloudflare returns a challenge instead of the HTML, that source is recorded as failed in `state/source_status.json` and events already stored are kept. On 6 Oct 2026 a direct fetch with this site's user agent got HTTP 403 ("Just a moment"). The conferences then on the five listings were parsed from the public HTML with this same code and stored as pending, so a later run that receives HTML adds new ones and does not duplicate these.

Other tools: `tools/probe.py` (feed checks), `tools/import_orgchart.py` (merges the Norwegian Kryptonytt industry map, translated via `data/no_en.json`, with `data/orgchart_nordic.json`), `tools/import_academia.py` (reads the researcher's `academia.md` and its editor status column), `tools/seed_academia.py` (DOI-checked publication candidates), `tools/privacy_gate.py`, `tools/commons_photo.py` (Wikimedia Commons photos with licence + credit only), `tools/fetch_logos.py` (one logo per org and per news outlet from Wikidata/Commons or the outlet's own site → `assets/img/logos/logos.json`, review pending), `tools/rules_page.py` (rules page from `rules.json`), `tools/regulation_videos.py` (country explainer slots at `/regulation-videos/`), `tools/article_archive.py` (append-only article archive).

## Outlet logos on news

Whenever a story is shown (the news list, the screen, our own story pages, and the HTML newsletter digest) the outlet logo sits beside the source name when a checked image is on file. The name is text only when there is no logo. Nothing is drawn or invented. The site brand stays Nordic Crypto. Kaupr is a news source, and its logo appears only next to Kaupr stories.

`assets/img/logos/logos.json` is the map. `tools/source_logos.py` resolves a story's `source` field like this:

1. The id is the source id in `sources.json` (the same id stored on the news item).
2. If that source has `outlet`, the parent id is used (for example `kaupr-no` → `kaupr`, `nrk-siste` → `nrk`).
3. `_source_alias` sends a source id to a different logo key when the who's-who id is not the source id: `fi-se` → `se-fi`, `riksbank` → `se-riksbank`, `suomenpankki` → `fi-suomen-pankki`, `finanssivalvonta` → `fi-fiva`, `stortinget` → `stortinget-finanskomiteen` (the Storting coat of arms), `nbx-ir` → `nbx`, `digi-krypto` → `digi`.
4. That key's `file` is the image path, relative to the repo root (`assets/img/logos/<id>.svg` or `.webp`).

The public site shows a logo only when `review` is `ok` (a missing review counts as ok). `./build.sh --preview` also shows `pending`. `rejected`, a missing file, or no entry: text only. `python3 tools/fetch_logos.py` fills gaps for enabled outlets and for any source that already has a published or pending story. New files stay `pending` until an editor checks that the image belongs to that outlet.

## Same event, several outlets

One story keeps a primary outlet (`source`, `source_name`, `url`, `title`, `published`, `language`). Other outlets that covered the same event are `also_covered_by`: `{outlet, outlet_name, url, title, published, lang, country, source_type}`. `outlet` is the source id. `lang` uses the same names as `language` (Norwegian, Swedish, …). Stories written before this field still have one outlet.

`source_type` is `national`, `regional` (regional and local papers), `official` (justice and official: police, prosecutors, courts, regulators, central banks, ministries) or `international`. It is taken from the outlet record when set, otherwise from `kind` in `sources.json`. Set `"reach": "regional"` on a local paper. The story page and `/api/v1/news.json` show counts and shares by country and by those four types, including a zero when a type has no outlet.

The front page shows up to six logos (the name, when no checked logo is on file) and a count such as `2 sources` or `+4 sources`. The count opens our story page. That page keeps **Read at** the primary outlet, then **Also covered by** with a link to each other outlet, then the bars, then every outlet with logo, country, original headline, time and link. The list is grouped by country, and can be sorted by time. Everything on these blocks is left-aligned.

The public news objects add `primary_source`, `also_covered_by`, `sources` (primary first) and `coverage`. `html_url` is our page. `url` stays the primary outlet. Kaupr is a news source only and is never a sponsor.

**Import.** `fetch.py`, reader tips and the cross-site handoff attach a new article to an existing story instead of creating another one when the headline matches (within 14 days), the title is close (within 3 days), or two known organisations appear in both texts (within 3 days). The note lands in `queue/review.json` → `coverage_attached`. A different event stays its own story.

**Editor.** On a row in `queue/review.json` → `items_needing_summary`, or on the `queue/approved.json` item, set `duplicate_of` to the existing story id or URL. No summary is required. The next `./build.sh` adds the article to `also_covered_by` and does not publish it on its own (`status` becomes `merged`). If `queue/approved.json` is missing, the build leaves `data/news.json` and `data/orgchart.json` as they are and does not withdraw published stories.

## Regulation explainer videos
`/regulation-videos/` has one slot each for Norway, Sweden, Denmark, Finland and Iceland, linked from `/rules/` and About. Scripts, storyboards, posters and sources are in `regulation-videos/`. Institution names and source URLs are read from the editor-approved `rules.json` at build time. Iceland is in the EEA, not the EU, and Seðlabanki Íslands houses Fjármálaeftirlit. Drop `video-XX.mp4` in `regulation-videos/media/` (gitignored) and the slot plays it with the HTML5 player. Until then the slot shows the title, the narrator notes and the sources. The films are not rendered yet. Draft notes in `regulation-videos/substack/` are for human review only; the build does not send them. Sign-off: The Nordic Crypto team. Kaupr is a news source only and is not a sponsor of these films.

## Approval model (`queue/approved.json`)
- `items`: `{url, summary (2–4 sentences, English, own words, what the story says), summary_i18n {nn, nb, sv, da, fi, is}, summary_i18n_source (the English text the translations were made from – if the summary changes, the translations are dropped until redone), blurb and blurb_i18n (optional; stored in data/frontpage_blurbs.json when the summary is still a one-line intro), title_en, topics, approved_by, approved_at}`; `duplicate_of` (story id or URL) attaches that article to an existing story instead of publishing it; `rejected`: `{url | title_contains, reason}`. Same field on a `queue/review.json` row.
- `events`: `approve`, `reject`, `ready_for_owner` (editor-approved, waiting for jQrgen: preview only), `notes`, `notes_i18n {id: {lang: text}}`, `sponsor {id: name}`, `paid`, `title_en`.
- `stories`: own articles in markdown (`files {slug: path}`), `ready_for_owner`, `approve`; the "Editor notes" part is never rendered.
- `org`: `approve`, `approve_countries`, `reject`. Rows, people, logos, photos and profile links added by research carry `"review": "pending"` and are NOT covered by `approve_countries`: list their ids in `org.approve` (logos/photos: set `review` to `ok` in `assets/img/logos/logos.json` / `assets/img/people/photos.json`; profile links: `status: published` in `data/profiles.json`). The preview build shows all pending items, marked.
- `rules.json`: the rules page (`/rules/`) stays a placeholder until its `review` is set to `approved`.
- Changelog entries with `"review": "pending"` are only shown in the preview.
- Academia: status column (`APPROVED` / pending / unverified / OUT) in `/workspace/nordic-crypto-research/academia.md`; only APPROVED rows reach the page.
- `changelog.json`: site changes only (not news), newest first.

## Bots
**Researcher (6031f46c)**: run `./fetch.sh --days 2` (daily), check `state/source_status.json` for failing sources, add missed stories/events with `--add` / `--add-event`, research org-chart candidates in `queue/review.json` and academia rows in `/workspace/nordic-crypto-research/academia.md` (every row: source, check date, status). Never invent; never circumvent blocks (vb.is returns 403 and stays disabled).

**Editor (0b7181d5)**: review `queue/review.json`; for each story write a 2–4 sentence English summary of what the story says, in your own words (plus `title_en` for Nordic-language headlines) into `queue/approved.json`, or reject. A one-sentence intro is not enough for the front page. Stories already published with a one-sentence summary keep a longer blurb in `data/frontpage_blurbs.json` (en, nn, nb, sv, da, fi, is) until the summary itself is two or more sentences; other site languages show the English blurb. Approve/reject events (date, place, organiser must be on the organiser's page; label paid/sponsored; reject online webinars without a Nordic link). Approve org rows only when every row and link has a source. Then `./build.sh --preview` and look at it. Things involving jQrgen himself (e.g. events where he speaks, own stories) go to `ready_for_owner`, never straight to `approve`. After the English summary: write `summary_i18n` for nn, nb, sv, da, fi, is (own words, same facts, no new claims) and set `summary_i18n_source` to the English text; check new org rows, people, logos (does the image belong to the org?), photos (licence, right person) and profile links before approving them; check the rules page against `research/rules-claims-*.md`.

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
Body capped at 4 KB, in-memory per-IP rate limit (5 per 10 min; IPs are hashed in memory only, using `CF-Connecting-IP` behind the tunnel), CORS for the public site origin and `https://jqrgen.github.io` (Kryptonytt), other browser origins get 403.
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

**GitHub issues (fallback).** The [Send a tip](https://nordiccrypto.no/tip/) page currently opens the issue form `.github/ISSUE_TEMPLATE/tip.yml` (label `tip`; tips are public on GitHub). Issues are never commented on or closed automatically.

**Nightly import.** `routines/nightly-fetch.sh` runs `tools/reader_tips.py`: pending rows in `tipserver/tips.db` -> `data/news.json` + `queue/review.json` as `pending` with origin `reader tip #<id>`, and the row is marked `imported` / `duplicate` / `invalid` (with `imported_at`, `queue_item_id`). Open `tip` issues are imported the same way with origin `reader tip (GitHub #N)`. Dedup: normalised-URL check from `tools/crosssite_handoff.py` against all stories (incl. rejected) and `approved.json`. Page metadata only where robots.txt allows. **The tipster's name is never read or copied**; the note stays in the local queue only (`tip_note_local_only`). Nothing is auto-published. Editor: treat tips like any other story. Dry run: `--dry-run`.

## Article archive
`archive/articles.db` (SQLite, gitignored) + `archive/articles.json` (committed export). Schema `archive/schema.sql`, shared with Kryptonytt (plus the additive `country` column); D1 mirror `tipworker/migrations/0002_articles.sql`. Rows are never deleted (triggers); a story that disappears gets `removed = 1` and `removed_at`. `routines/morning-publish.sh` runs `tools/article_archive.py record` after each successful publish; `backfill` reads the gh-pages history.

## Newsletter (own list)
`newsletter/email-list.md` is the setup for jQrgen: D1 table `subscribers`, DNS for Resend or Mailgun, Worker secrets, and how to send an issue. Cloudflare Email Routing can receive replies; it does not send the list. The site form (footer, front page, `/newsletter/#signup`, 7 languages, consent checkbox, privacy note) stays behind `newsletter/config.json` `enabled: false` until the Worker is deployed and that flag is set. It posts to the tipworker (`/api/subscribe`, double opt-in, private D1, see `tipworker/README.md`). `newsletter/digest.py` builds a weekly digest from the **public** build only. `newsletter/send_issue.py` mails a published issue, or that digest, to confirmed addresses. Nothing is sent unless `MAIL_SEND_ENABLED=1`. Sign-off: The Nordic Crypto team. Kaupr is a news source only.

## Privacy
No health or private financial data about anyone, no org numbers, LEIs, addresses of private persons, emails or tokens. `state/private_terms.json` (never printed, never committed) feeds the privacy gate, which blocks the build if it finds them. The gate also blocks organisation numbers in visible text, including source titles (NO 9-digit, SE NNNNNN-NNNN, DK CVR, «org.nr …»); register links are fine, the number itself must not be written out.

`data/` (stories, events, org chart, translations of the industry map, profile links, academia) is committed to the repo so the content is not stored only on the box; it is public content and passes the privacy gate (`tools/privacy_gate.py data`). `queue/`, `state/`, `logs/`, `site/` and `tipserver/tips.db` stay box-only (`queue/` can hold local-only reader-tip notes).

**Language rule (text gate).** Our own Norwegian text (nn, nb) never says «AI» or «KI»; write «kunstig intelligens» in full. `tools/text_gate.py` checks the nn/nb interface strings, templates, summaries, event notes, changelog and rules-page strings, and runs in `build.sh` and `publish.sh`. External headlines are left as published.
