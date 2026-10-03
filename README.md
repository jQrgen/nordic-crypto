# Nordic Crypto

Bitcoin, blockchain and crypto news, events, a who's who (industry + regulators), regulation by country and academia for
**Norway, Sweden, Denmark, Finland and Iceland**. Everything on the site is in English. Static site, no tracking.
Planned URL: https://jqrgen.github.io/nordic-crypto/ (all links are relative). Run by jQrgen (Jørgen S. Notland), MIT licence.

**Status: local only.** No git repo, nothing committed or published. Publishing needs jQrgen's explicit approval.

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

Other tools: `tools/probe.py` (feed checks), `tools/import_orgchart.py` (merges the Norwegian Kryptonytt industry map, translated via `data/no_en.json`, with `data/orgchart_nordic.json`), `tools/import_academia.py` (reads the researcher's `academia.md` and its editor status column), `tools/seed_academia.py` (DOI-checked publication candidates), `tools/privacy_gate.py`, `tools/commons_photo.py` (Wikimedia Commons photos with licence + credit only).

## Approval model (`queue/approved.json`)
- `items`: `{url, summary (1–2 sentences, English, own words), title_en, topics, approved_by, approved_at}`; `rejected`: `{url | title_contains, reason}`.
- `events`: `approve`, `reject`, `ready_for_owner` (editor-approved, waiting for jQrgen: preview only), `notes`, `sponsor {id: name}`, `paid`, `title_en`.
- `stories`: own articles in markdown (`files {slug: path}`), `ready_for_owner`, `approve`; the "Editor notes" part is never rendered.
- `org`: `approve`, `approve_countries`, `reject`.
- Academia: status column (`APPROVED` / pending / unverified / OUT) in `/workspace/nordic-crypto-research/academia.md`; only APPROVED rows reach the page.
- `changelog.json`: site changes only (not news), newest first.

## Bots
**Researcher (6031f46c)**: run `./fetch.sh --days 2` (daily), check `state/source_status.json` for failing sources, add missed stories/events with `--add` / `--add-event`, research org-chart candidates in `queue/review.json` and academia rows in `/workspace/nordic-crypto-research/academia.md` (every row: source, check date, status). Never invent; never circumvent blocks (vb.is returns 403 and stays disabled).

**Editor (0b7181d5)**: review `queue/review.json`; for each story write a 1–2 sentence English summary in your own words (plus `title_en` for Nordic-language headlines) into `queue/approved.json`, or reject. Approve/reject events (date, place, organiser must be on the organiser's page; label paid/sponsored; reject online webinars without a Nordic link). Approve org rows only when every row and link has a source. Then `./build.sh --preview` and look at it. Things involving jQrgen himself (e.g. events where he speaks, own stories) go to `ready_for_owner`, never straight to `approve`.

## Denmark (added 3 Oct 2026)
Denmark (DK) is in the country set, the fetch config and the event detection. No Danish content goes live without the editor's approval: Danish stories and events land as `pending`, and DK is deliberately **not** in `org.approve_countries`, so Danish org-chart rows need explicit approval (`org.approve` or adding DK to `approve_countries` once the editor has reviewed them). Researcher: Danish stories, events, org chart (Finanstilsynet, Danmarks Nationalbank, Erhvervsministeriet, Skatteministeriet/Skattestyrelsen, the FIU (Hvidvasksekretariatet), MiCA CASPs authorised in Denmark per the ESMA register) and academia rows.

## Privacy
No health or private financial data about anyone, no org numbers, LEIs, addresses of private persons, emails or tokens. `state/private_terms.json` (never printed, never committed) feeds the privacy gate, which blocks the build if it finds them.
