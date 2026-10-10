#!/usr/bin/env python3
"""Cloudflare D1 storage for Nordic Crypto stories, events and sources.

The public site keeps reading data/news.json and data/events.json until the
repository variable NC_DATA_SOURCE is d1. This module is the switch.

Private terms are never written. Teasers and the editor's working queue can
sit in the documents table so the next fetch can continue; the git backup and
the public Worker do not read those documents.
"""
import hashlib
import json
import os
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIGRATION = os.path.join(ROOT, "workers", "content", "migrations", "0001_content.sql")
DATABASE_NAME = "nordic-crypto-content"
MAX_DOCUMENT_BYTES = 1_500_000

# Stored for the fetch. Never part of the git backup or the public API.
PRIVATE_DOCUMENTS = frozenset({
    "teasers",
    "review_queue",
    "html_seen",
    "html_lists",
    "http_cache",
    "dropped_gambling",
})
# The term list itself. Refused even as a document name.
FORBIDDEN_DOCUMENTS = frozenset({"private_terms", "private_terms.json"})

DOC_FILES = {
    "teasers": ("state", "teasers.json"),
    "review_queue": ("queue", "review.json"),
    "source_status": ("state", "source_status.json"),
    "html_seen": ("state", "html_seen.json"),
    "html_lists": ("state", "html_lists.json"),
}

# What a fetch may add to a reviewed story (_coverage_merge). It only adds, never replaces.
FETCH_FIELDS = ("seen_via", "also_covered_by", "matched", "fetched")
DEFAULT_ACTOR = "Nordic Crypto redaktør"

SETUP_COMMANDS = """\
Cloudflare is not configured, so nothing was created.

1. Create an API token (My Profile → API Tokens → Create Custom Token):
     Account / D1 / Edit
     Account / Workers Scripts / Edit
     Account / Workers R2 Storage / Edit   (only if you also want the R2 backup)
   Do not grant Account Analytics. That is a different token (CF_ANALYTICS_TOKEN).

2. Export it in the shell you use for the one-time import. Do not commit it.
     export CLOUDFLARE_API_TOKEN='…'
     export CLOUDFLARE_ACCOUNT_ID='…'     # dashboard overview, account id
     export CF_ACCOUNT_ID=\"$CLOUDFLARE_ACCOUNT_ID\"

3. Create the database and apply the schema (from the repo root):
     cd workers/content
     npx wrangler d1 create nordic-crypto-content
     # copy database_id into workers/content/wrangler.toml (replace the zeros)
     npx wrangler d1 migrations apply nordic-crypto-content --remote
     cd ../..
     export CF_D1_DATABASE_ID='…'         # the database_id from the create command

4. Import the JSON already in git. Safe to run again; a second run changes nothing
   when the files and the reviews are unchanged.
     python3 tools/d1_import.py

5. Editor secret for the Worker (random, not the Cloudflare token):
     cd workers/content
     npx wrangler secret put EDITOR_TOKEN
     npx wrangler deploy
     cd ../..

6. Tell GitHub the names. The site keeps reading JSON until the last line.
     gh secret set CLOUDFLARE_API_TOKEN
     gh variable set CF_ACCOUNT_ID --body \"$CF_ACCOUNT_ID\"
     gh variable set CF_D1_DATABASE_ID --body \"$CF_D1_DATABASE_ID\"
     gh variable set NC_DATA_SOURCE --body d1

7. Optional: redeploy as soon as an editor approves, instead of waiting for the schedule.
     # fine-grained PAT, repository jQrgen/nordic-crypto, Actions: Read and write
     cd workers/content && npx wrangler secret put GITHUB_DISPATCH_TOKEN

8. Private R2 bucket for the nightly backup (the only target; no branch is pushed):
     npx wrangler r2 bucket create nordic-crypto-content-backup
     gh variable set CF_R2_BUCKET --body nordic-crypto-content-backup

Review without a commit, from the repo root (wrangler d1, remote):
     python3 tools/d1_review.py pending
     python3 tools/d1_review.py approve --id STORY_ID --summary \"…\" --by \"Nordic Crypto redaktør\"
     python3 tools/d1_review.py reject --id STORY_ID --reason \"…\"
     python3 tools/d1_review.py approve-event --id EVENT_ID --by \"Nordic Crypto redaktør\"
     python3 tools/d1_review.py reject-event --id EVENT_ID --reason \"…\"
"""


class D1Error(Exception):
    """A problem we can report without quoting a token or a private term."""


def enabled():
    """True only when the site should read and write D1."""
    return os.environ.get("NC_DATA_SOURCE", "").strip().lower() == "d1"


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_time(value):
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def d1_is_newer(existing_at, incoming_at):
    """True when D1 has an editor time and it is strictly after the JSON time."""
    existing = parse_time(existing_at)
    if existing is None:
        return False
    incoming = parse_time(incoming_at)
    if incoming is None:
        return True
    return existing > incoming


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(obj):
    raw = obj if isinstance(obj, str) else dumps(obj)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def canon(url):
    """Same URL key as tools/apply_approvals.py."""
    if not url:
        return ""
    parsed = urllib.parse.urlparse(str(url).strip())
    query = urllib.parse.urlencode([
        (key, value)
        for key, value in urllib.parse.parse_qsl(parsed.query)
        if not key.lower().startswith(("utm_", "fbclid", "gclid"))
    ])
    parsed = parsed._replace(query=query)
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path.rstrip("/") or "/"
    return host + path + ("?" + parsed.query if parsed.query else "")


def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return default


def save_json(path, data):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, path)


def sql_quote(value):
    """Quote a value for a wrangler d1 file. Bound parameters are preferred on the HTTP API."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def split_sql(sql):
    lines = []
    for line in sql.splitlines():
        if line.strip().startswith("--"):
            continue
        lines.append(line)
    return [part.strip() for part in "\n".join(lines).split(";") if part.strip()]


def migration_sql():
    with open(MIGRATION, encoding="utf-8") as fh:
        return fh.read()


def assert_document_name(name):
    plain = (name or "").strip().replace("\\", "/").split("/")[-1]
    if plain in FORBIDDEN_DOCUMENTS or "private_terms" in plain:
        raise D1Error("refusing to store private terms")
    return plain


def missing_remote():
    """Names that must be set before a remote call. Empty when the HTTP API can run."""
    missing = []
    if not (os.environ.get("CLOUDFLARE_API_TOKEN") or "").strip():
        missing.append("CLOUDFLARE_API_TOKEN")
    if not (os.environ.get("CF_ACCOUNT_ID") or os.environ.get("CLOUDFLARE_ACCOUNT_ID") or "").strip():
        missing.append("CF_ACCOUNT_ID")
    if not (os.environ.get("CF_D1_DATABASE_ID") or "").strip():
        missing.append("CF_D1_DATABASE_ID")
    return missing


class SqliteStore:
    """Local SQLite with the same SQL as D1. Used by tests and --sqlite."""

    def __init__(self, path):
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def query(self, sql, params=()):
        cur = self.conn.execute(sql, tuple(params))
        rows = [dict(row) for row in cur.fetchall()] if cur.description else []
        self.conn.commit()
        return rows

    def execute(self, sql, params=()):
        self.conn.execute(sql, tuple(params))
        self.conn.commit()

    def executescript(self, sql):
        self.conn.executescript(sql)
        self.conn.commit()


class HttpStore:
    """Cloudflare D1 HTTP query API. The same endpoint wrangler d1 execute uses."""

    def __init__(self, account_id, database_id, token, base="https://api.cloudflare.com/client/v4"):
        self.account_id = account_id
        self.database_id = database_id
        self.token = token
        self.base = base.rstrip("/")

    def _post(self, sql, params):
        url = f"{self.base}/accounts/{self.account_id}/d1/database/{self.database_id}/query"
        body = json.dumps({"sql": sql, "params": list(params)}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Authorization": "Bearer " + self.token,
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as ex:
            detail = ex.read().decode("utf-8", errors="replace")[:500]
            if self.token and self.token in detail:
                detail = detail.replace(self.token, "[token]")
            raise D1Error(f"D1 HTTP {ex.code}: {detail}") from None
        if not payload.get("success"):
            raise D1Error("D1 query failed: " + json.dumps(payload.get("errors") or [])[:500])
        result = payload.get("result") or []
        if isinstance(result, dict):
            return result.get("results") or []
        if result and isinstance(result, list):
            first = result[0] or {}
            if isinstance(first, dict):
                return first.get("results") or []
        return []

    def query(self, sql, params=()):
        return self._post(sql, params)

    def execute(self, sql, params=()):
        self._post(sql, params)


def apply_schema(store):
    sql = migration_sql()
    if isinstance(store, SqliteStore):
        store.executescript(sql)
        return
    for statement in split_sql(sql):
        store.execute(statement)


def open_sqlite(path):
    store = SqliteStore(path)
    apply_schema(store)
    return store


def open_remote():
    missing = missing_remote()
    if missing:
        raise D1Error(
            "missing " + ", ".join(missing) + ".\n" + SETUP_COMMANDS
        )
    account = (os.environ.get("CF_ACCOUNT_ID") or os.environ.get("CLOUDFLARE_ACCOUNT_ID")).strip()
    return HttpStore(account, os.environ["CF_D1_DATABASE_ID"].strip(), os.environ["CLOUDFLARE_API_TOKEN"].strip())


def one(store, sql, params=()):
    rows = store.query(sql, params)
    return rows[0] if rows else None


def audit(store, kind, item_id, action, actor, at, detail=None):
    store.execute(
        "INSERT INTO review_audit (kind, item_id, action, actor, at, detail) VALUES (?, ?, ?, ?, ?, ?)",
        (kind, item_id, action, actor, at, detail),
    )


def review_from_story(item):
    status = item.get("status") or "pending"
    if status == "published":
        return {
            "review_status": "approved",
            "item_status": "published",
            "reviewed_by": item.get("approved_by"),
            "reviewed_at": item.get("approved_at"),
            "review_note": None,
            "summary": item.get("summary"),
        }
    if status == "rejected":
        return {
            "review_status": "rejected",
            "item_status": "rejected",
            "reviewed_by": item.get("approved_by"),
            "reviewed_at": item.get("approved_at"),
            "review_note": item.get("reject_reason"),
            "summary": None,
        }
    if status == "merged":
        return {
            "review_status": "pending",
            "item_status": "merged",
            "reviewed_by": None,
            "reviewed_at": None,
            "review_note": item.get("merged_into"),
            "summary": None,
        }
    return {
        "review_status": "pending",
        "item_status": "pending",
        "reviewed_by": None,
        "reviewed_at": None,
        "review_note": None,
        "summary": None,
    }


def _story_row(item, mapped, at, created_at):
    payload = dumps(item)
    return {
        "id": item["id"],
        "url": item.get("url") or "",
        "canonical_url": canon(item.get("url")),
        "title": item.get("title"),
        "source_id": item.get("source"),
        "source_name": item.get("source_name"),
        "country": item.get("country"),
        "language": item.get("language"),
        "published_at": item.get("published"),
        "item_status": mapped["item_status"],
        "review_status": mapped["review_status"],
        "summary": mapped["summary"],
        "reviewed_by": mapped["reviewed_by"],
        "reviewed_at": mapped["reviewed_at"],
        "review_note": mapped["review_note"],
        "payload": payload,
        "content_hash": digest(payload),
        "created_at": created_at,
        "updated_at": at,
    }


_STORY_UPDATE = """
UPDATE stories SET
  url = ?, canonical_url = ?, title = ?, source_id = ?, source_name = ?, country = ?, language = ?,
  published_at = ?, item_status = ?, review_status = ?, summary = ?, reviewed_by = ?, reviewed_at = ?,
  review_note = ?, payload = ?, content_hash = ?, updated_at = ?
WHERE id = ?
"""


def _bind_story_update(row):
    return (
        row["url"], row["canonical_url"], row["title"], row["source_id"], row["source_name"],
        row["country"], row["language"], row["published_at"], row["item_status"], row["review_status"],
        row["summary"], row["reviewed_by"], row["reviewed_at"], row["review_note"], row["payload"],
        row["content_hash"], row["updated_at"], row["id"],
    )


def _insert_story(store, row):
    store.execute(
        """
        INSERT INTO stories (
          id, url, canonical_url, title, source_id, source_name, country, language, published_at,
          item_status, review_status, summary, reviewed_by, reviewed_at, review_note, payload,
          content_hash, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["id"], row["url"], row["canonical_url"], row["title"], row["source_id"], row["source_name"],
            row["country"], row["language"], row["published_at"], row["item_status"], row["review_status"],
            row["summary"], row["reviewed_by"], row["reviewed_at"], row["review_note"], row["payload"],
            row["content_hash"], row["created_at"], row["updated_at"],
        ),
    )


def import_stories(store, items, at, actor="import"):
    """Insert or update stories. A second run with the same JSON writes nothing.
    A newer approval already stored in D1 is left as it is."""
    stats = {"inserted": 0, "updated": 0, "skipped": 0, "kept": 0}
    for item in items or []:
        if not isinstance(item, dict) or not item.get("id") or not item.get("url"):
            raise D1Error("a story is missing id or url")
        mapped = review_from_story(item)
        row = _story_row(item, mapped, at, at)
        existing = one(store, "SELECT * FROM stories WHERE id = ?", (item["id"],))
        if existing and existing["content_hash"] == row["content_hash"] and existing["review_status"] == row["review_status"] and existing["item_status"] == row["item_status"]:
            stats["skipped"] += 1
            continue
        if existing and existing["review_status"] in ("approved", "rejected") and d1_is_newer(existing.get("reviewed_at"), mapped.get("reviewed_at")):
            stats["kept"] += 1
            continue
        if existing:
            row["created_at"] = existing["created_at"]
            store.execute(_STORY_UPDATE, _bind_story_update(row))
            audit(store, "story", item["id"], "import", actor, at, "updated")
            stats["updated"] += 1
        else:
            _insert_story(store, row)
            audit(store, "story", item["id"], "import", actor, at, "inserted")
            stats["inserted"] += 1
    return stats


def _event_item_status(review_status):
    if review_status == "approved":
        return "published"
    if review_status == "rejected":
        return "rejected"
    return "pending"


def merge_event(data_row, archive_row):
    """One payload. Archive fields fill in editor notes and the English title.
    The fetch status on the data row is kept. Approval is the review column."""
    merged = dict(data_row or {})
    for key, value in (archive_row or {}).items():
        if key == "status":
            continue
        # A null in the archive must not wipe a value the fetch already stored.
        # A null for a key the fetch row does not have is kept, so the key is not dropped.
        if value is None and key in merged:
            continue
        merged[key] = value
    if data_row and data_row.get("status"):
        merged["status"] = data_row["status"]
    else:
        merged["status"] = "pending"
    if not merged.get("id"):
        raise D1Error("an event is missing id")
    return merged


def load_event_records(root):
    """Events from data/events.json and archive/events.json, plus decisions in
    queue/approved.json when that file is on the box."""
    data = load_json(os.path.join(root, "data", "events.json"), {"events": []}) or {}
    archive = load_json(os.path.join(root, "archive", "events.json"), {"events": []}) or {}
    approved_path = os.path.join(root, "queue", "approved.json")
    approved = load_json(approved_path, None)
    file_present = isinstance(approved, dict)
    ev_ap = (approved or {}).get("events") or {} if file_present else {}
    approve_ids = set(ev_ap.get("approve") or [])
    reject_ids = set(ev_ap.get("reject") or [])
    data_by = {}
    for row in data.get("events") or []:
        if isinstance(row, dict) and row.get("id"):
            data_by[row["id"]] = row
    archive_by = {}
    for row in archive.get("events") or []:
        if isinstance(row, dict) and row.get("id"):
            archive_by[row["id"]] = row
    records = []
    for eid in list(data_by) + [key for key in archive_by if key not in data_by]:
        payload = merge_event(data_by.get(eid), archive_by.get(eid))
        if eid in (ev_ap.get("notes") or {}):
            payload["note"] = ev_ap["notes"][eid]
        if eid in (ev_ap.get("notes_i18n") or {}):
            payload["note_i18n"] = ev_ap["notes_i18n"][eid]
        if eid in (ev_ap.get("title_en") or {}):
            payload["editor_title_en"] = ev_ap["title_en"][eid]
        if eid in (ev_ap.get("paid") or {}):
            payload["paid"] = ev_ap["paid"][eid]
        if eid in (ev_ap.get("sponsor") or {}):
            payload["sponsored"] = ev_ap["sponsor"][eid]
        archive_row = archive_by.get(eid) or {}
        if eid in reject_ids:
            review = "rejected"
        elif file_present:
            review = "approved" if eid in approve_ids else "pending"
        elif archive_row.get("status") == "published":
            review = "approved"
        else:
            review = "pending"
        records.append((payload, review))
    return records


def _insert_event(store, row):
    store.execute(
        """
        INSERT INTO events (
          id, url, title, country, start_at, item_status, review_status, reviewed_by, reviewed_at,
          review_note, payload, content_hash, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["id"], row["url"], row["title"], row["country"], row["start_at"], row["item_status"],
            row["review_status"], row["reviewed_by"], row["reviewed_at"], row["review_note"],
            row["payload"], row["content_hash"], row["created_at"], row["updated_at"],
        ),
    )


def _event_row(payload, review, at, created_at, reviewed_by=None, reviewed_at=None, review_note=None):
    text = dumps(payload)
    return {
        "id": payload["id"],
        "url": payload.get("url"),
        "title": payload.get("title"),
        "country": payload.get("country"),
        "start_at": payload.get("start"),
        "item_status": _event_item_status(review),
        "review_status": review,
        "reviewed_by": reviewed_by,
        "reviewed_at": reviewed_at,
        "review_note": review_note,
        "payload": text,
        "content_hash": digest(text),
        "created_at": created_at,
        "updated_at": at,
    }


_EVENT_UPDATE = """
UPDATE events SET
  url = ?, title = ?, country = ?, start_at = ?, item_status = ?, review_status = ?,
  reviewed_by = ?, reviewed_at = ?, review_note = ?, payload = ?, content_hash = ?, updated_at = ?
WHERE id = ?
"""


def import_events(store, records, at, actor="import"):
    stats = {"inserted": 0, "updated": 0, "skipped": 0, "kept": 0}
    for payload, review in records:
        row = _event_row(payload, review, at, at)
        existing = one(store, "SELECT * FROM events WHERE id = ?", (payload["id"],))
        if existing and existing["content_hash"] == row["content_hash"] and existing["review_status"] == review:
            stats["skipped"] += 1
            continue
        if existing and existing["review_status"] in ("approved", "rejected") and d1_is_newer(existing.get("reviewed_at"), None) and review == "pending":
            stats["kept"] += 1
            continue
        if existing and existing["review_status"] in ("approved", "rejected") and review != existing["review_status"] and existing.get("reviewed_at") and review == "pending":
            stats["kept"] += 1
            continue
        if existing:
            row["created_at"] = existing["created_at"]
            if existing["review_status"] in ("approved", "rejected") and review == existing["review_status"]:
                row["reviewed_by"] = existing.get("reviewed_by")
                row["reviewed_at"] = existing.get("reviewed_at")
                row["review_note"] = existing.get("review_note")
            store.execute(
                _EVENT_UPDATE,
                (
                    row["url"], row["title"], row["country"], row["start_at"], row["item_status"],
                    row["review_status"], row["reviewed_by"], row["reviewed_at"], row["review_note"],
                    row["payload"], row["content_hash"], row["updated_at"], row["id"],
                ),
            )
            audit(store, "event", payload["id"], "import", actor, at, "updated")
            stats["updated"] += 1
        else:
            _insert_event(store, row)
            audit(store, "event", payload["id"], "import", actor, at, "inserted")
            stats["inserted"] += 1
    return stats


def import_sources(store, sources, kind, at, actor="import"):
    stats = {"inserted": 0, "updated": 0, "skipped": 0}
    for src in sources or []:
        if not isinstance(src, dict) or not src.get("id"):
            raise D1Error("a source is missing id")
        text = dumps(src)
        row_hash = digest(text)
        existing = one(store, "SELECT content_hash, created_at, review_status FROM sources WHERE id = ?", (src["id"],))
        if existing and existing["content_hash"] == row_hash:
            stats["skipped"] += 1
            continue
        enabled = 1 if src.get("enabled", True) else 0
        if existing and existing["review_status"] == "rejected":
            enabled = 0
        values = (
            src["id"], kind, src.get("name"), src.get("country"), src.get("url"),
            enabled, "rejected" if existing and existing["review_status"] == "rejected" else "approved",
            None, None, None, text, row_hash, at,
        )
        if existing:
            store.execute(
                """
                UPDATE sources SET
                  kind = ?, name = ?, country = ?, url = ?, enabled = ?, payload = ?, content_hash = ?, updated_at = ?
                WHERE id = ?
                """,
                (kind, src.get("name"), src.get("country"), src.get("url"), enabled, text, row_hash, at, src["id"]),
            )
            stats["updated"] += 1
        else:
            store.execute(
                """
                INSERT INTO sources (
                  id, kind, name, country, url, enabled, review_status, reviewed_by, reviewed_at,
                  review_note, payload, content_hash, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values + (at,),
            )
            stats["inserted"] += 1
    if stats["inserted"] or stats["updated"]:
        audit(store, "source", kind, "import", actor, at, dumps(stats))
    return stats


def import_root(store, root, at=None, actor="import"):
    """Import news, events and sources from a checkout. Idempotent."""
    at = at or now_iso()
    news = load_json(os.path.join(root, "data", "news.json"), {"items": []}) or {}
    sources = load_json(os.path.join(root, "sources.json"), {}) or {}
    story_stats = import_stories(store, news.get("items") or [], at, actor)
    event_stats = import_events(store, load_event_records(root), at, actor)
    source_stats = import_sources(store, sources.get("sources") or [], "news", at, actor)
    event_source_stats = import_sources(store, sources.get("event_sources") or [], "event", at, actor)
    return {
        "stories": story_stats,
        "events": event_stats,
        "sources": source_stats,
        "event_sources": event_source_stats,
    }


def _coverage_merge(existing_payload, incoming):
    """Add what the fetch found. The checkout that ran the fetch can be older than D1,
    so an outlet it lacks is not a removal: keep everything D1 already has."""
    changed = False
    extras = list(existing_payload.get("also_covered_by") or [])
    have = {canon(existing_payload.get("url"))}
    have.update(canon(ex.get("url")) for ex in extras if isinstance(ex, dict))
    for ex in incoming.get("also_covered_by") or []:
        if not isinstance(ex, dict) or not ex.get("url") or canon(ex["url"]) in have:
            continue
        extras.append(ex)
        have.add(canon(ex["url"]))
        changed = True
    if changed:
        existing_payload["also_covered_by"] = extras
    for key in ("seen_via", "matched"):
        merged = list(existing_payload.get(key) or [])
        size = len(merged)
        for value in incoming.get(key) or []:
            if value not in merged:
                merged.append(value)
        if len(merged) > size:
            existing_payload[key] = merged
            changed = True
    if incoming.get("fetched") and not existing_payload.get("fetched"):
        existing_payload["fetched"] = incoming["fetched"]
        changed = True
    return changed


def sync_story(store, item, at, actor="fetch"):
    """Write a fetch result. New rows are pending. An approved or rejected row is not reopened.
    Coverage fields on an approved story are only added to, never replaced. The summary and the review are not."""
    if not isinstance(item, dict) or not item.get("id") or not item.get("url"):
        raise D1Error("a story is missing id or url")
    mapped = review_from_story(item)
    existing = one(store, "SELECT * FROM stories WHERE id = ?", (item["id"],))
    if not existing:
        row = _story_row(item, mapped, at, at)
        _insert_story(store, row)
        audit(store, "story", item["id"], "fetch", actor, at, "inserted")
        return "inserted"
    if existing["review_status"] in ("approved", "rejected") or existing["item_status"] == "merged":
        payload = json.loads(existing["payload"])
        if not _coverage_merge(payload, item):
            return "kept"
        text = dumps(payload)
        store.execute(
            "UPDATE stories SET payload = ?, content_hash = ?, updated_at = ? WHERE id = ?",
            (text, digest(text), at, item["id"]),
        )
        audit(store, "story", item["id"], "fetch", actor, at, "coverage")
        return "coverage"
    if mapped["review_status"] != "pending" or mapped["item_status"] not in ("pending", "merged"):
        return "kept"
    row = _story_row(item, mapped, at, existing["created_at"])
    if existing["content_hash"] == row["content_hash"]:
        return "skipped"
    store.execute(_STORY_UPDATE, _bind_story_update(row))
    audit(store, "story", item["id"], "fetch", actor, at, "updated")
    return "updated"


def sync_event(store, payload, at, actor="fetch", review=None):
    if not isinstance(payload, dict) or not payload.get("id"):
        raise D1Error("an event is missing id")
    existing = one(store, "SELECT * FROM events WHERE id = ?", (payload["id"],))
    if review is None:
        review = "rejected" if payload.get("status") == "rejected" else "pending"
    if not existing:
        row = _event_row(payload, review, at, at)
        _insert_event(store, row)
        audit(store, "event", payload["id"], "fetch", actor, at, "inserted")
        return "inserted"
    if existing["review_status"] in ("approved", "rejected"):
        return "kept"
    # The committed archive is what the public calendar shows today. A fetch that
    # runs before the one-time import must not hide those events behind "pending".
    if review == "approved" and existing["review_status"] == "pending":
        row = _event_row(payload, "approved", at, existing["created_at"])
        store.execute(
            _EVENT_UPDATE,
            (
                row["url"], row["title"], row["country"], row["start_at"], row["item_status"],
                row["review_status"], row["reviewed_by"], row["reviewed_at"], row["review_note"],
                row["payload"], row["content_hash"], row["updated_at"], row["id"],
            ),
        )
        audit(store, "event", payload["id"], "fetch", actor, at, "approved-from-archive")
        return "updated"
    row = _event_row(payload, "pending", at, existing["created_at"])
    if existing["content_hash"] == row["content_hash"]:
        return "skipped"
    store.execute(
        _EVENT_UPDATE,
        (
            row["url"], row["title"], row["country"], row["start_at"], row["item_status"],
            row["review_status"], row["reviewed_by"], row["reviewed_at"], row["review_note"],
            row["payload"], row["content_hash"], row["updated_at"], row["id"],
        ),
    )
    audit(store, "event", payload["id"], "fetch", actor, at, "updated")
    return "updated"


def put_document(store, name, obj, at):
    name = assert_document_name(name)
    text = obj if isinstance(obj, str) else dumps(obj)
    if len(text.encode("utf-8")) > MAX_DOCUMENT_BYTES:
        return "too_large"
    row_hash = digest(text)
    existing = one(store, "SELECT content_hash FROM documents WHERE name = ?", (name,))
    if existing and existing["content_hash"] == row_hash:
        return "skipped"
    if existing:
        store.execute(
            "UPDATE documents SET payload = ?, content_hash = ?, updated_at = ? WHERE name = ?",
            (text, row_hash, at, name),
        )
    else:
        store.execute(
            "INSERT INTO documents (name, payload, content_hash, updated_at) VALUES (?, ?, ?, ?)",
            (name, text, row_hash, at),
        )
    return "stored"


def sync_documents(store, root, at):
    results = {}
    for name, parts in DOC_FILES.items():
        path = os.path.join(root, *parts)
        if not os.path.exists(path):
            results[name] = "missing"
            continue
        with open(path, encoding="utf-8") as fh:
            results[name] = put_document(store, name, fh.read(), at)
    return results


def sync_root(store, root, at=None, actor="fetch"):
    """Push the working news and events files. Does not read private terms."""
    at = at or now_iso()
    news = load_json(os.path.join(root, "data", "news.json"), {"items": []}) or {}
    events = load_json(os.path.join(root, "data", "events.json"), {"events": []}) or {}
    stories = {"inserted": 0, "updated": 0, "skipped": 0, "kept": 0, "coverage": 0}
    for item in news.get("items") or []:
        stories[sync_story(store, item, at, actor)] += 1
    event_stats = {"inserted": 0, "updated": 0, "skipped": 0, "kept": 0}
    records = load_event_records(root)
    by_id = {payload["id"]: (payload, review) for payload, review in records}
    seen = set()
    for row in events.get("events") or []:
        payload, review = by_id.get(row.get("id"), (row, None))
        event_stats[sync_event(store, payload, at, actor, review=review)] += 1
        if row.get("id"):
            seen.add(row["id"])
    for payload, review in records:
        if payload["id"] in seen:
            continue
        event_stats[sync_event(store, payload, at, actor, review=review)] += 1
    documents = sync_documents(store, root, at)
    return {"stories": stories, "events": event_stats, "documents": documents}


def restore_root(store, root):
    """Fold D1 rows the checkout does not already have, and restore fetch documents.
    Does not write private terms or the HTTP cache."""
    news_path = os.path.join(root, "data", "news.json")
    events_path = os.path.join(root, "data", "events.json")
    news = load_json(news_path, {"items": []}) or {"items": []}
    events = load_json(events_path, {"events": []}) or {"events": []}
    items = list(news.get("items") or [])
    rows = list(events.get("events") or [])
    seen_ids = {item.get("id") for item in items}
    seen_urls = {canon(item.get("url")) for item in items if item.get("url")}
    added_stories = 0
    for row in store.query("SELECT payload FROM stories", ()):
        payload = json.loads(row["payload"])
        if payload.get("id") in seen_ids or (payload.get("url") and canon(payload["url"]) in seen_urls):
            continue
        items.append(payload)
        added_stories += 1
        if payload.get("id"):
            seen_ids.add(payload["id"])
    seen_events = {row.get("id") for row in rows}
    added_events = 0
    for row in store.query("SELECT payload FROM events", ()):
        payload = json.loads(row["payload"])
        if payload.get("id") in seen_events:
            continue
        rows.append(payload)
        added_events += 1
    news["items"] = items
    events["events"] = rows
    save_json(news_path, news)
    save_json(events_path, events)
    restored = []
    for name, parts in DOC_FILES.items():
        doc = one(store, "SELECT payload FROM documents WHERE name = ?", (name,))
        if not doc:
            continue
        path = os.path.join(root, *parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(doc["payload"])
            if not doc["payload"].endswith("\n"):
                fh.write("\n")
        restored.append(name)
    return {"stories_added": added_stories, "events_added": added_events, "documents": restored}


def story_columns(row):
    payload = json.loads(row["payload"])
    if row["item_status"] == "merged":
        payload["status"] = "merged"
    elif row["review_status"] == "approved":
        payload["status"] = "published"
        if row.get("reviewed_by"):
            payload["approved_by"] = row["reviewed_by"]
        if row.get("reviewed_at"):
            payload["approved_at"] = row["reviewed_at"]
        if row.get("summary"):
            payload["summary"] = row["summary"]
        payload.pop("reject_reason", None)
    elif row["review_status"] == "rejected":
        payload["status"] = "rejected"
        payload["summary"] = None
        if row.get("review_note"):
            payload["reject_reason"] = row["review_note"]
    else:
        payload["status"] = "pending"
    return payload


def event_payload(row):
    return json.loads(row["payload"])


def event_approvals(rows):
    """The events section build.py already understands. Notes come from the payload."""
    approvals = {
        "approve": [],
        "reject": [],
        "notes": {},
        "notes_i18n": {},
        "title_en": {},
        "paid": {},
        "sponsor": {},
        "sponsored": [],
    }
    for row in rows:
        payload = event_payload(row)
        eid = row["id"]
        if row["review_status"] == "approved":
            approvals["approve"].append(eid)
        elif row["review_status"] == "rejected":
            approvals["reject"].append(eid)
        if payload.get("note"):
            approvals["notes"][eid] = payload["note"]
        if payload.get("note_i18n"):
            approvals["notes_i18n"][eid] = payload["note_i18n"]
        if payload.get("editor_title_en"):
            approvals["title_en"][eid] = payload["editor_title_en"]
    return approvals


def materialize(root, preview=False, store=None, at=None):
    """Write data/news.json and data/events.json from D1. Does not write queue/approved.json,
    so the org-chart approvals on the box are left alone. Returns the event approval dict
    for this build. Refuses an empty story table so a missed import cannot publish a blank site."""
    if store is None:
        store = open_remote()
    story_rows = store.query(
        "SELECT * FROM stories ORDER BY published_at DESC, id",
        (),
    )
    if not story_rows:
        raise D1Error(
            "D1 has no stories. Run python3 tools/d1_import.py before setting NC_DATA_SOURCE=d1. "
            "The JSON files were not replaced."
        )
    approved = [row for row in story_rows if row["review_status"] == "approved"]
    if not approved and not preview:
        raise D1Error("D1 has no approved stories. Refusing to build an empty site.")
    archive_count = 0
    archive = load_json(os.path.join(root, "archive", "events.json"), {"events": []}) or {}
    archive_count = len(archive.get("events") or [])
    event_rows = store.query("SELECT * FROM events ORDER BY start_at, id", ())
    if archive_count and not event_rows:
        raise D1Error(
            "D1 has no events but archive/events.json does. Run python3 tools/d1_import.py "
            "before setting NC_DATA_SOURCE=d1."
        )
    stories = []
    for row in story_rows:
        if row["review_status"] == "pending" and row["item_status"] == "pending" and not preview:
            continue
        if row["review_status"] == "pending" and row["item_status"] == "merged":
            stories.append(story_columns(row))
            continue
        if row["review_status"] == "pending" and not preview:
            continue
        stories.append(story_columns(row))
    at = at or now_iso()
    save_json(os.path.join(root, "data", "news.json"), {"updated": at, "items": stories})
    save_json(
        os.path.join(root, "data", "events.json"),
        {"updated": at, "events": [event_payload(row) for row in event_rows]},
    )
    return event_approvals(event_rows)


def backup_files(store, at=None):
    """JSON documents for the git backup. No teasers, no private terms, no HTML cache."""
    at = at or now_iso()
    stories = [json.loads(row["payload"]) for row in store.query("SELECT payload FROM stories ORDER BY published_at DESC, id", ())]
    events = [json.loads(row["payload"]) for row in store.query("SELECT payload FROM events ORDER BY start_at, id", ())]
    news_sources = []
    event_sources = []
    for row in store.query("SELECT kind, payload FROM sources ORDER BY kind, id", ()):
        payload = json.loads(row["payload"])
        if row["kind"] == "event":
            event_sources.append(payload)
        else:
            news_sources.append(payload)
    audit_rows = store.query(
        "SELECT id, kind, item_id, action, actor, at, detail FROM review_audit ORDER BY id",
        (),
    )
    present = [row["name"] for row in store.query("SELECT name FROM documents ORDER BY name", ())]
    omitted = [name for name in present if name in PRIVATE_DOCUMENTS or name in FORBIDDEN_DOCUMENTS]
    source_status = one(store, "SELECT payload FROM documents WHERE name = ?", ("source_status",))
    files = {
        "news.json": {"updated": at, "items": stories},
        "events.json": {"updated": at, "events": events},
        "sources.json": {"sources": news_sources, "event_sources": event_sources},
        "audit.json": {"exported_at": at, "rows": audit_rows},
        "manifest.json": {
            "exported_at": at,
            "stories": len(stories),
            "events": len(events),
            "sources": len(news_sources),
            "event_sources": len(event_sources),
            "audit_rows": len(audit_rows),
            "omitted_documents": omitted,
        },
    }
    if source_status:
        try:
            files["source_status.json"] = json.loads(source_status["payload"])
        except json.JSONDecodeError:
            files["source_status.json"] = {"raw": source_status["payload"]}
    return files


def write_backup(store, dest, at=None):
    files = backup_files(store, at)
    os.makedirs(dest, exist_ok=True)
    for name, data in files.items():
        if "private_terms" in name or name in PRIVATE_DOCUMENTS:
            raise D1Error("refusing to export " + name)
        save_json(os.path.join(dest, name), data)
    return files["manifest.json"]


def assert_backup_dir(dest):
    """Fail if a staged backup contains working notes or the term list."""
    for dirpath, _, names in os.walk(dest):
        for name in names:
            plain = name.replace("\\", "/")
            if plain in FORBIDDEN_DOCUMENTS or "private_terms" in plain:
                raise D1Error("refusing to back up private terms")
            if plain in PRIVATE_DOCUMENTS or plain.replace(".json", "") in PRIVATE_DOCUMENTS:
                raise D1Error("refusing to back up " + plain)
            path = os.path.join(dirpath, name)
            if name.endswith((".json", ".txt", ".html")):
                with open(path, encoding="utf-8", errors="replace") as fh:
                    if "private_terms" in fh.read():
                        raise D1Error("refusing to back up a file that names private terms")


def stage_for_gate(root, dest):
    """Copy the JSON the sync is about to upload, including teasers, so the privacy
    gate can see them. Never copies the term list into dest."""
    os.makedirs(dest, exist_ok=True)
    pairs = [
        ("data", "news.json"),
        ("data", "events.json"),
        ("state", "teasers.json"),
        ("queue", "review.json"),
        ("state", "source_status.json"),
    ]
    copied = []
    for parts in pairs:
        src = os.path.join(root, *parts)
        if not os.path.exists(src):
            continue
        target_name = parts[-1]
        if "private_terms" in target_name:
            raise D1Error("refusing to stage private terms")
        with open(src, encoding="utf-8") as fh:
            text = fh.read()
        target = os.path.join(dest, target_name)
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(text)
        copied.append(target_name)
    return copied


def plan_story_review(row, action, summary, reason, actor, at, extra=None):
    """The columns and payload after an editor decision. Raises D1Error when the summary is missing."""
    payload = json.loads(row["payload"])
    extra = extra or {}
    if action == "approve":
        text = (summary or "").strip()
        if not text:
            raise D1Error("a story approval needs a summary")
        payload["status"] = "published"
        payload["summary"] = text
        payload["approved_by"] = actor
        payload["approved_at"] = at
        payload.pop("reject_reason", None)
        for key in (
            "title_en", "topics", "summary_i18n", "summary_i18n_source", "summary_i18n_review",
            "title_i18n", "title_i18n_source", "primary_source",
        ):
            if key in extra and extra[key] is not None:
                payload[key] = extra[key]
        mapped = {
            "review_status": "approved",
            "item_status": "published",
            "summary": text,
            "reviewed_by": actor,
            "reviewed_at": at,
            "review_note": None,
        }
    elif action == "reject":
        payload["status"] = "rejected"
        payload["summary"] = None
        payload.pop("approved_by", None)
        payload.pop("approved_at", None)
        if reason:
            payload["reject_reason"] = reason
        mapped = {
            "review_status": "rejected",
            "item_status": "rejected",
            "summary": None,
            "reviewed_by": actor,
            "reviewed_at": at,
            "review_note": reason,
        }
    else:
        raise D1Error("action must be approve or reject")
    text_payload = dumps(payload)
    mapped.update(
        id=row["id"],
        url=payload.get("url") or row.get("url") or "",
        canonical_url=canon(payload.get("url") or row.get("url")),
        title=payload.get("title"),
        source_id=payload.get("source") or row.get("source_id"),
        source_name=payload.get("source_name") or row.get("source_name"),
        country=payload.get("country"),
        language=payload.get("language"),
        published_at=payload.get("published") or row.get("published_at"),
        payload=text_payload,
        content_hash=digest(text_payload),
        updated_at=at,
        created_at=row.get("created_at") or at,
    )
    return mapped


def plan_event_review(row, action, actor, at, note=None, note_i18n=None, reason=None):
    payload = json.loads(row["payload"])
    if action == "approve":
        review = "approved"
        payload.pop("reject_reason", None)
        if note is not None:
            payload["note"] = note
        if note_i18n is not None:
            payload["note_i18n"] = note_i18n
        review_note = None
    elif action == "reject":
        review = "rejected"
        payload["status"] = "rejected"
        if reason:
            payload["reject_reason"] = reason
        review_note = reason
    else:
        raise D1Error("action must be approve or reject")
    text_payload = dumps(payload)
    return {
        "id": row["id"],
        "url": payload.get("url"),
        "title": payload.get("title"),
        "country": payload.get("country"),
        "start_at": payload.get("start"),
        "item_status": _event_item_status(review),
        "review_status": review,
        "reviewed_by": actor,
        "reviewed_at": at,
        "review_note": review_note,
        "payload": text_payload,
        "content_hash": digest(text_payload),
        "updated_at": at,
    }


def apply_story_plan(store, plan, actor, at):
    existing = one(store, "SELECT content_hash, review_status FROM stories WHERE id = ?", (plan["id"],))
    if existing and existing["content_hash"] == plan["content_hash"] and existing["review_status"] == plan["review_status"]:
        return "skipped"
    store.execute(_STORY_UPDATE, _bind_story_update(plan))
    action = "approve" if plan["review_status"] == "approved" else "reject"
    audit(store, "story", plan["id"], action, actor, at, plan["review_status"])
    return plan["review_status"]


def apply_event_plan(store, plan, actor, at):
    existing = one(store, "SELECT content_hash, review_status FROM events WHERE id = ?", (plan["id"],))
    if existing and existing["content_hash"] == plan["content_hash"] and existing["review_status"] == plan["review_status"]:
        return "skipped"
    store.execute(
        _EVENT_UPDATE,
        (
            plan["url"], plan["title"], plan["country"], plan["start_at"], plan["item_status"],
            plan["review_status"], plan["reviewed_by"], plan["reviewed_at"], plan["review_note"],
            plan["payload"], plan["content_hash"], plan["updated_at"], plan["id"],
        ),
    )
    action = "approve" if plan["review_status"] == "approved" else "reject"
    audit(store, "event", plan["id"], action, actor, at, plan["review_status"])
    return plan["review_status"]


def review_story(store, story_id, action, summary=None, reason=None, actor=None, at=None, extra=None):
    row = one(store, "SELECT * FROM stories WHERE id = ?", (story_id,))
    if not row:
        raise D1Error("no story " + str(story_id))
    actor = actor or DEFAULT_ACTOR
    at = at or now_iso()
    plan = plan_story_review(row, action, summary, reason, actor, at, extra)
    apply_story_plan(store, plan, actor, at)
    return plan


def review_event(store, event_id, action, actor=None, at=None, note=None, note_i18n=None, reason=None):
    row = one(store, "SELECT * FROM events WHERE id = ?", (event_id,))
    if not row:
        raise D1Error("no event " + str(event_id))
    actor = actor or DEFAULT_ACTOR
    at = at or now_iso()
    plan = plan_event_review(row, action, actor, at, note, note_i18n, reason)
    apply_event_plan(store, plan, actor, at)
    return plan


def pending_stories(store):
    return store.query(
        """
        SELECT id, title, country, url, published_at FROM stories
        WHERE review_status = 'pending' AND item_status = 'pending'
        ORDER BY published_at DESC, id
        """,
        (),
    )


def pending_events(store):
    return store.query(
        """
        SELECT id, title, country, url, start_at FROM events
        WHERE review_status = 'pending' AND item_status = 'pending'
        ORDER BY start_at, id
        """,
        (),
    )


def story_sql(plan):
    """One UPDATE and one audit INSERT for wrangler d1 execute --file."""
    update = (
        "UPDATE stories SET "
        f"url = {sql_quote(plan['url'])}, canonical_url = {sql_quote(plan['canonical_url'])}, "
        f"title = {sql_quote(plan['title'])}, source_id = {sql_quote(plan['source_id'])}, "
        f"source_name = {sql_quote(plan['source_name'])}, country = {sql_quote(plan['country'])}, "
        f"language = {sql_quote(plan['language'])}, published_at = {sql_quote(plan['published_at'])}, "
        f"item_status = {sql_quote(plan['item_status'])}, review_status = {sql_quote(plan['review_status'])}, "
        f"summary = {sql_quote(plan['summary'])}, reviewed_by = {sql_quote(plan['reviewed_by'])}, "
        f"reviewed_at = {sql_quote(plan['reviewed_at'])}, review_note = {sql_quote(plan['review_note'])}, "
        f"payload = {sql_quote(plan['payload'])}, content_hash = {sql_quote(plan['content_hash'])}, "
        f"updated_at = {sql_quote(plan['updated_at'])} WHERE id = {sql_quote(plan['id'])}"
    )
    action = "approve" if plan["review_status"] == "approved" else "reject"
    insert = (
        "INSERT INTO review_audit (kind, item_id, action, actor, at, detail) VALUES ("
        f"'story', {sql_quote(plan['id'])}, {sql_quote(action)}, {sql_quote(plan['reviewed_by'])}, "
        f"{sql_quote(plan['reviewed_at'])}, {sql_quote(plan['review_status'])})"
    )
    return update + ";\n" + insert + ";\n"


def event_sql(plan):
    action = "approve" if plan["review_status"] == "approved" else "reject"
    update = (
        "UPDATE events SET "
        f"url = {sql_quote(plan['url'])}, title = {sql_quote(plan['title'])}, "
        f"country = {sql_quote(plan['country'])}, start_at = {sql_quote(plan['start_at'])}, "
        f"item_status = {sql_quote(plan['item_status'])}, review_status = {sql_quote(plan['review_status'])}, "
        f"reviewed_by = {sql_quote(plan['reviewed_by'])}, reviewed_at = {sql_quote(plan['reviewed_at'])}, "
        f"review_note = {sql_quote(plan['review_note'])}, payload = {sql_quote(plan['payload'])}, "
        f"content_hash = {sql_quote(plan['content_hash'])}, updated_at = {sql_quote(plan['updated_at'])} "
        f"WHERE id = {sql_quote(plan['id'])}"
    )
    insert = (
        "INSERT INTO review_audit (kind, item_id, action, actor, at, detail) VALUES ("
        f"'event', {sql_quote(plan['id'])}, {sql_quote(action)}, {sql_quote(plan['reviewed_by'])}, "
        f"{sql_quote(plan['reviewed_at'])}, {sql_quote(plan['review_status'])})"
    )
    return update + ";\n" + insert + ";\n"


def wrangler_command(sql_path):
    return [
        "npx", "--yes", "wrangler", "d1", "execute", DATABASE_NAME,
        "--remote", "--json", "--file", sql_path,
    ]


# Public Worker and the static API share this allow-list. Working fields stay out.
PUBLIC_STORY_KEYS = (
    "id", "url", "title", "title_en", "title_i18n", "source", "source_name", "country",
    "language", "published", "topics", "summary", "summary_i18n", "paywall", "links", "status",
)
PUBLIC_EVENT_KEYS = (
    "id", "title", "title_orig", "start", "end", "place", "city", "country", "online",
    "organiser", "url", "source", "source_url", "paid", "sponsored", "note", "note_i18n",
    "description", "status",
)


def public_story(payload):
    """Fields the public API may return. No teasers, no match rules, no reject reason."""
    if payload.get("status") != "published":
        return None
    if not (payload.get("summary") or "").strip():
        return None
    if payload.get("summary_i18n_review", "approved") != "approved":
        payload = dict(payload)
        payload.pop("summary_i18n", None)
    out = {key: payload.get(key) for key in PUBLIC_STORY_KEYS if key in payload and payload.get(key) is not None}
    out["status"] = "published"
    return out


def public_event(payload, review_status):
    if review_status != "approved":
        return None
    out = {key: payload.get(key) for key in PUBLIC_EVENT_KEYS if key in payload and payload.get(key) is not None}
    out["status"] = "published"
    out.pop("editor_title_en", None)
    return out


def public_source(payload):
    kept = {}
    for key in ("id", "name", "country", "kind", "url", "enabled", "language", "paywall"):
        if key in payload and payload.get(key) is not None:
            kept[key] = payload[key]
    return kept
