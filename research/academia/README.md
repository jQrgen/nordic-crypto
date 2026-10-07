# research/academia — Nordic Crypto academic catalogue

Brand: **Nordic Crypto**.

## What lives here
- `works.json` / `works.csv` — curated Nordic crypto/blockchain/bitcoin academic works
  (master's theses, PhD dissertations, journal papers, conference papers).
  Fields: title, authors, year, type (`master`|`phd`|`paper`|`conference`), institution,
  country (`NO`|`SE`|`DK`|`FI`|`IS`), url, doi, relevance, keywords, venue, source_db.
- Every row is sourced (NVA, DiVA, Theseus, Pure, Opinvisindi, OpenAlex, …). No fabricated citations.

## How publish picks it up
1. `tools/import_academia.py` (run automatically by `build.py` → `build_academia()` on the English build)
   reads `/workspace/nordic-crypto-research/academia.md` (courses/groups/research editor list)
   **and** merges `research/academia/works.json` into `data/academia.json` → `publications`.
2. New works land with `status: pending` (awaiting editor). Only `status: approved` rows
   are rendered on `/academia/` (public and preview).
3. Approval key for publications: `doi` when present, otherwise `url`
   (see `queue/approved.json` → `academia.approve`).
4. `./publish.sh` runs the normal build; no extra flag is required once works.json is committed.

## Updating the list
- Prefer regenerating from the researcher workspace (`/workspace/nordic-crypto-academia/`)
  and copying `nordic_crypto_academia.json` → `works.json` here.
- Or append carefully verified rows; never invent metadata.
- Re-run `python tools/import_academia.py` then `./build.sh --preview` to inspect.

## Counts (initial import, 2026-10-06)
See `works.json` summary in the PR description / REPORT.md under `/workspace/nordic-crypto-academia/`.
