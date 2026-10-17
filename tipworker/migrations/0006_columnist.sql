-- Columnist applications from /columnist/ (private; replaces the public GitHub issue form).
-- No IP address, user agent or raw request is stored. Rate limiting reuses rate_salt/rate_hits (scope 'columnist').
CREATE TABLE IF NOT EXISTS columnist_applications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,          -- UTC ISO timestamp
  language TEXT NOT NULL,            -- site language of the page
  name TEXT,                         -- optional
  email TEXT NOT NULL,               -- reply address, never published
  languages TEXT NOT NULL,
  pitch TEXT NOT NULL,
  sample TEXT,                       -- optional http(s) link
  why TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'new',  -- new | read | handled
  emailed INTEGER NOT NULL DEFAULT 0   -- 1 once forwarded to COLUMNIST_TO
);
CREATE INDEX IF NOT EXISTS columnist_status ON columnist_applications(status, id);
