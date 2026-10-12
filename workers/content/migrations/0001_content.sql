-- Nordic Crypto stories, events and sources (Cloudflare D1).
-- The payload column is the original JSON object, so an import drops no field.
-- Rows are not deleted. Rejecting a story sets review_status and leaves the row.
-- Private terms are not a table. The tools refuse to write that list.
-- Teasers and other working notes live in documents. The public export does not read them.
-- review_status is the editor's decision: pending, approved or rejected.
-- item_status keeps the JSON status (pending, published, rejected, merged) so nothing is flattened away.
-- A merged story has item_status 'merged' and stays out of the editor queue.

CREATE TABLE IF NOT EXISTS schema_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sources (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  name TEXT,
  country TEXT,
  url TEXT,
  enabled INTEGER NOT NULL DEFAULT 0,
  review_status TEXT NOT NULL CHECK (review_status IN ('pending', 'approved', 'rejected')),
  reviewed_by TEXT,
  reviewed_at TEXT,
  review_note TEXT,
  payload TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stories (
  id TEXT PRIMARY KEY,
  url TEXT NOT NULL,
  canonical_url TEXT NOT NULL,
  title TEXT,
  source_id TEXT,
  source_name TEXT,
  country TEXT,
  language TEXT,
  published_at TEXT,
  item_status TEXT NOT NULL,
  review_status TEXT NOT NULL CHECK (review_status IN ('pending', 'approved', 'rejected')),
  summary TEXT,
  reviewed_by TEXT,
  reviewed_at TEXT,
  review_note TEXT,
  payload TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
  id TEXT PRIMARY KEY,
  url TEXT,
  title TEXT,
  country TEXT,
  start_at TEXT,
  item_status TEXT NOT NULL,
  review_status TEXT NOT NULL CHECK (review_status IN ('pending', 'approved', 'rejected')),
  reviewed_by TEXT,
  reviewed_at TEXT,
  review_note TEXT,
  payload TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
  name TEXT PRIMARY KEY,
  payload TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL,
  item_id TEXT NOT NULL,
  action TEXT NOT NULL,
  actor TEXT,
  at TEXT NOT NULL,
  detail TEXT
);

CREATE INDEX IF NOT EXISTS stories_review ON stories (review_status, published_at);
CREATE INDEX IF NOT EXISTS stories_canon ON stories (canonical_url);
CREATE INDEX IF NOT EXISTS events_review ON events (review_status, start_at);
CREATE INDEX IF NOT EXISTS sources_review ON sources (review_status, kind);
CREATE INDEX IF NOT EXISTS audit_item ON review_audit (kind, item_id);

INSERT INTO schema_meta (key, value) VALUES ('version', '1')
  ON CONFLICT(key) DO UPDATE SET value = excluded.value;

CREATE TRIGGER IF NOT EXISTS stories_no_delete
BEFORE DELETE ON stories
BEGIN
  SELECT RAISE(ABORT, 'stories are not deleted');
END;

CREATE TRIGGER IF NOT EXISTS events_no_delete
BEFORE DELETE ON events
BEGIN
  SELECT RAISE(ABORT, 'events are not deleted');
END;

CREATE TRIGGER IF NOT EXISTS sources_no_delete
BEFORE DELETE ON sources
BEGIN
  SELECT RAISE(ABORT, 'sources are not deleted');
END;

CREATE TRIGGER IF NOT EXISTS audit_no_delete
BEFORE DELETE ON review_audit
BEGIN
  SELECT RAISE(ABORT, 'the review audit is append-only');
END;

CREATE TRIGGER IF NOT EXISTS audit_no_update
BEFORE UPDATE ON review_audit
BEGIN
  SELECT RAISE(ABORT, 'the review audit is append-only');
END;
