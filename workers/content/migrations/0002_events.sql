-- Calendar events in D1 (issue #138 prepares for user-submitted events and registrations).
-- events.payload stays the full JSON object (nothing is dropped), the new columns are for queries.
-- A merged duplicate is never deleted (events_no_delete): item_status becomes 'merged' and
-- merged_into names the kept id. event_redirects is the public redirect list built from that.
-- origin says where a row came from: 'fetch' (pipeline), 'import' (JSON in git) or, later,
-- 'submission' (an event_submissions row an editor accepted). submitted_by is reserved for that.
-- Not created yet (#138): event_submissions (proposed event, submitter contact, moderation state,
-- accepted_event_id) and event_registrations (event_id, attendee, status, created_at). Both will
-- reference events.id and must never be part of the public export or the git backup.

ALTER TABLE events ADD COLUMN end_at TEXT;
ALTER TABLE events ADD COLUMN city TEXT;
ALTER TABLE events ADD COLUMN merged_into TEXT;
ALTER TABLE events ADD COLUMN origin TEXT NOT NULL DEFAULT 'fetch';
ALTER TABLE events ADD COLUMN submitted_by TEXT;

CREATE TABLE IF NOT EXISTS event_translations (
  event_id TEXT NOT NULL,
  field TEXT NOT NULL CHECK (field IN ('description', 'note', 'title')),
  lang TEXT NOT NULL,
  source_text TEXT NOT NULL,
  text TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (event_id, field, lang)
);

CREATE TABLE IF NOT EXISTS event_redirects (
  old_id TEXT PRIMARY KEY,
  new_id TEXT NOT NULL,
  reason TEXT NOT NULL DEFAULT 'duplicate',
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS events_merged ON events (merged_into);
CREATE INDEX IF NOT EXISTS events_city_start ON events (city, start_at);
CREATE INDEX IF NOT EXISTS event_translations_event ON event_translations (event_id);
CREATE INDEX IF NOT EXISTS event_redirects_new ON event_redirects (new_id);

INSERT INTO schema_meta (key, value) VALUES ('version', '2')
  ON CONFLICT(key) DO UPDATE SET value = excluded.value;
