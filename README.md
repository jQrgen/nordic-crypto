# Nordic Crypto

Bitcoin, blockchain and crypto news, events, a who's who (industry + regulators), regulation by country and academia for
**Norway, Sweden, Denmark, Finland and Iceland**. Static site, no tracking.
Languages: English (root `/`), Nynorsk `/nn/`, Bokmål `/nb/`, Swedish `/sv/`, Danish `/da/`, Finnish `/fi/`, Icelandic `/is/` (UI strings in `i18n/<lang>.py`, about pages in `templates/about.<lang>.html`). External headlines and quotes stay in the original language; our own summaries are written first in English, then translated (AI-assisted, editor-approved). Language choice (`tools/langselect.js`): `nc_lang` cookie (set only when the reader picks a language) → `/api/geo` on our own Worker (country only, nothing stored) → `navigator.languages` → English; only a first visit to the root is redirected, never a direct language link.
Planned URL: https://jqrgen.github.io/nordic-crypto/ (all links are relative). Run by jQrgen (Jørgen S. Notland), MIT licence.

**Status:** live at https://jqrgen.github.io/nordic-crypto/ (gh-pages). Code on `main`. Every publish needs jQrgen's explicit approval.

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

Other tools: `tools/probe.py` (feed checks), `tools/import_orgchart.py` (merges the Norwegian Kryptonytt industry map, translated via `data/no_en.json`, with `data/orgchart_nordic.json`), `tools/import_academia.py` (reads the researcher's `academia.md` and its editor status column), `tools/seed_academia.py` (DOI-checked publication candidates), `tools/privacy_gate.py`, `tools/commons_photo.py` (Wikimedia Commons photos with licence + credit only), `tools/fetch_logos.py` (one logo per org from Wikidata/Commons or the org's own site → `assets/img/logos/logos.json`, review pending), `tools/rules_page.py` (rules page from `rules.json`), `tools/article_archive.py` (append-only article archive).

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

## Reader tips (added 3 Oct 2026; own tip server 3 Oct 2026)
**Own tip server (primary, not public yet).** `tipserver/server.py` (Python stdlib + SQLite) listens on `127.0.0.1:8787`:
`POST /api/tip` (JSON or form: `url` required http/https, `country` NO/SE/DK/FI/IS/unsure, `note` ≤ 1000 chars, optional `name` ≤ 100, honeypot `website` must be empty) and `GET /api/health`.
Body capped at 4 KB, in-memory per-IP rate limit (5 per 10 min; IPs are hashed in memory only, using `CF-Connecting-IP` behind the tunnel), CORS only for `https://jqrgen.github.io`, other browser origins get 403.
Tips go to `tipserver/tips.db` (gitignored, mode 600) with a UTC timestamp and status `pending`. **No IP address, user agent or request body is stored or logged**; `tipserver/server.log` has only time, method, path and status.
- Keep it running: `tipserver/run.sh start|stop|restart|status`. `run.sh start` launches `tipserver/supervise.sh` detached (setsid + nohup), which restarts the server whenever it exits (back-off 1–30 s). The box has no systemd or cron, so `routines/nightly-fetch.sh` calls `tipserver/run.sh ensure` to bring it back after a box restart.
- Test: `curl -s http://127.0.0.1:8787/api/health` and `curl -s -H 'Content-Type: application/json' -d '{"url":"https://example.no/a","country":"NO"}' http://127.0.0.1:8787/api/tip`.
- Public access (not live yet). `tipserver/config.json`: `public_endpoint` (fixed https URL, e.g. a named tunnel at `tips.<domain>`; takes precedence and is baked into /tip/) or `quick_tunnel: true` (Cloudflare quick tunnel; `run.sh` then also starts `tipserver/tunnel.sh`, which publishes the random `*.trycloudflare.com` URL – only after it answers `/api/health` – by pushing ONLY `tip-endpoint.json` to gh-pages via `tipserver/publish_endpoint.sh`; /tip/ reads that file at runtime with no cache). While both are unset, /tip/ uses the GitHub issue form. When either is set, /tip/ posts to the server (inline JS only, no third-party scripts), shows “The tip service is temporarily offline, try again later” with the GitHub form as fallback if the server can't be reached. `publish.sh` and `publish_endpoint.sh` share a lock (`/tmp/nordic-crypto-publish.lock`); `build.py` writes `site/tip-endpoint.json` so a full publish keeps it.
- **3 Oct 2026: the quick tunnel cannot connect from this box** – its outbound network blocks port 7844 (TCP and UDP), which every Cloudflare tunnel (quick or named) needs to reach Cloudflare's edge. `quick_tunnel` is therefore `false`. Public access needs a host that allows outbound 7844, or another way to expose the server.

**GitHub issues (fallback).** The [Send a tip](https://jqrgen.github.io/nordic-crypto/tip/) page currently opens the issue form `.github/ISSUE_TEMPLATE/tip.yml` (label `tip`; tips are public on GitHub). Issues are never commented on or closed automatically.

**Nightly import.** `routines/nightly-fetch.sh` runs `tools/reader_tips.py`: pending rows in `tipserver/tips.db` -> `data/news.json` + `queue/review.json` as `pending` with origin `reader tip #<id>`, and the row is marked `imported` / `duplicate` / `invalid` (with `imported_at`, `queue_item_id`). Open `tip` issues are imported the same way with origin `reader tip (GitHub #N)`. Dedup: normalised-URL check from `tools/crosssite_handoff.py` against all stories (incl. rejected) and `approved.json`. Page metadata only where robots.txt allows. **The tipster's name is never read or copied**; the note stays in the local queue only (`tip_note_local_only`). Nothing is auto-published. Editor: treat tips like any other story. Dry run: `--dry-run`.

## Article archive
`archive/articles.db` (SQLite, gitignored) + `archive/articles.json` (committed export). Schema `archive/schema.sql`, shared with Kryptonytt (plus the additive `country` column); D1 mirror `tipworker/migrations/0002_articles.sql`. Rows are never deleted (triggers); a story that disappears gets `removed = 1` and `removed_at`. `routines/morning-publish.sh` runs `tools/article_archive.py record` after each successful publish; `backfill` reads the gh-pages history.

## Newsletter (Substack + email) – prepared, OFF
`newsletter/substack-setup.md` (publication name, subdomain, texts, branding in `newsletter/assets/`, welcome email, digest
template, Kaupr disclosure, checklist for jQrgen). `newsletter/digest.py` builds the weekly digest from the **public** build
only (approved stories). Signup form (footer + `/newsletter/`, 7 languages, privacy note) is behind `newsletter/config.json`
`enabled: false`; it posts to the tipworker (`/api/subscribe`, double opt-in, see `tipworker/README.md`). Nothing is sent and
no Substack account exists until jQrgen sets it up.

## Privacy
No health or private financial data about anyone, no org numbers, LEIs, addresses of private persons, emails or tokens. `state/private_terms.json` (never printed, never committed) feeds the privacy gate, which blocks the build if it finds them. The gate also blocks organisation numbers in visible text, including source titles (NO 9-digit, SE NNNNNN-NNNN, DK CVR, «org.nr …»); register links are fine, the number itself must not be written out.

`data/` (stories, events, org chart, translations of the industry map, profile links, academia) is committed to the repo so the content is not stored only on the box; it is public content and passes the privacy gate (`tools/privacy_gate.py data`). `queue/`, `state/`, `logs/`, `site/` and `tipserver/tips.db` stay box-only (`queue/` can hold local-only reader-tip notes).

**Language rule (text gate).** Our own Norwegian text (nn, nb) never says «AI» or «KI»; write «kunstig intelligens» in full. `tools/text_gate.py` checks the nn/nb interface strings, templates, summaries, event notes, changelog and rules-page strings, and runs in `build.sh` and `publish.sh`. External headlines are left as published.
