-- Private tip inbox. No IP address, user agent, or raw request is stored.
-- status: new | read | handled. editor_notes is for the newsroom, never shown to the sender.

CREATE TABLE IF NOT EXISTS tips (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  language TEXT NOT NULL,
  page TEXT NOT NULL,
  tip TEXT NOT NULL,
  contact TEXT,
  attachments TEXT,
  status TEXT NOT NULL DEFAULT 'new',
  editor_notes TEXT
);
CREATE INDEX IF NOT EXISTS tips_status ON tips(status, id);

-- Rate limiting. rate_hits.h is SHA-256(salt || key). The salt lives only until expires_at
-- (the rate-limit window). When it expires, the salt and the hashes are deleted.
-- The IP itself is never written. Onion forwards use a fixed key, not the VPS address.
CREATE TABLE IF NOT EXISTS rate_salt (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  salt TEXT NOT NULL,
  expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS rate_hits (
  h TEXT NOT NULL,
  ts INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS rate_hits_h ON rate_hits(h, ts);
CREATE INDEX IF NOT EXISTS rate_hits_ts ON rate_hits(ts);
