# Calendar events in D1

Schema: `workers/content/migrations/0001_content.sql` (events table) plus `0002_events.sql`.

- `events`: one row per event. `payload` is the full JSON row. Query columns: `url`, `title`, `country`, `start_at`, `end_at`, `city`, `item_status` (pending/published/rejected/merged), `review_status` (pending/approved/rejected, the editor's approval), `merged_into`, `origin` (fetch/import/submission), `submitted_by` (reserved for #138). Rows are never deleted.
- `event_translations(event_id, field, lang, source_text, text, updated_at)`: replaces `data/event_description_i18n.json`. A translation applies only while `source_text` equals the stored description.
- `event_redirects(old_id, new_id, reason, created_at)`: replaces `data/event_redirects.json`. The merged row gets `item_status='merged'`. If the kept row is still pending, it takes the removed row's approval, plus any editor fields it lacks (note, note_i18n, editor_title_en, paid, sponsored).
- Later (#138), not created yet: `event_submissions` (a proposed event from a user, the submitter's contact details, its moderation state and `accepted_event_id`) and `event_registrations` (event_id, attendee, status, created_at). Neither is ever exported or backed up to git.

Data flow:
- The fetch (`events.py`) writes JSON. Next, `tools/d1_sync.py push` upserts events, translations and redirects. That runs after the privacy gate in nightly-fetch. Marking merged rows and carrying approvals over happen in that step.
- When `NC_DATA_SOURCE=d1`, the build calls `materialize()`, which writes `data/events.json`, `data/event_description_i18n.json` and `data/event_redirects.json` from D1. Merged rows are left out. The committed JSON stays the offline snapshot. `NC_D1_FALLBACK=json` builds from it when D1 cannot be read.
- The public `/api/v1` is generated from the same files, so it is unchanged.

Apply and import (from the repo root, with `CLOUDFLARE_API_TOKEN`, `CF_ACCOUNT_ID`, `CLOUDFLARE_ACCOUNT_ID` and `CF_D1_DATABASE_ID` exported):

    python3 tools/d1_import.py --sqlite /tmp/nc-dryrun.sqlite      # dry run, local
    (cd workers/content && npx wrangler d1 migrations list nordic-crypto-content --remote)
    (cd workers/content && npx wrangler d1 migrations apply nordic-crypto-content --remote)
    python3 tools/d1_import.py                                      # idempotent; run again: no changes
