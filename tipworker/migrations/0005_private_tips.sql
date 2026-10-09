-- Private tip inbox (free text from /tip/). Separate from `tips`, which holds article-URL tips for tools/reader_tips.py.
-- No IP address, user agent or raw request is stored. Rate limiting reuses rate_salt/rate_hits from 0001_tips.sql.
-- status: new | read | handled. editor_notes is for the newsroom and is never shown to the sender.
CREATE TABLE IF NOT EXISTS private_tips (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,                 -- UTC ISO timestamp
  language TEXT NOT NULL,                   -- site language of the page the tip came from
  page TEXT NOT NULL,                       -- /tip/ path (or full https URL of a site tip page)
  tip TEXT NOT NULL,                        -- up to 8000 characters
  contact TEXT,                             -- optional, never published
  attachments TEXT,                         -- JSON list of http(s) links, or NULL
  status TEXT NOT NULL DEFAULT 'new',
  editor_notes TEXT
);
CREATE INDEX IF NOT EXISTS private_tips_status ON private_tips(status, id);
