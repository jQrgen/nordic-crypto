-- Nordic Crypto reader tips (same columns as tipserver/server.py's SQLite table, so tools/reader_tips.py can import them).
CREATE TABLE IF NOT EXISTS tips (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,                 -- UTC ISO timestamp, e.g. 2026-10-03T20:10:11+00:00
  url TEXT NOT NULL,
  country TEXT NOT NULL,                    -- NO | SE | DK | FI | IS | unsure
  note TEXT NOT NULL DEFAULT '',
  name TEXT,                                -- optional, never published and never read by the importer
  status TEXT NOT NULL DEFAULT 'pending',   -- pending | imported | duplicate | invalid
  imported_at TEXT,
  queue_item_id TEXT
);
CREATE INDEX IF NOT EXISTS tips_status ON tips(status, id);

-- Rate limiting without raw IPs: rate_hits.h = SHA-256(daily random salt || IP). The salt lives only in rate_salt, a new
-- random one is created every UTC day and older salts are deleted, and hits older than the 10-minute window are deleted
-- on every request. So a hash can't be linked to an IP or across days once its salt is gone. The IP itself is never stored.
CREATE TABLE IF NOT EXISTS rate_salt (
  day TEXT PRIMARY KEY,                     -- UTC date YYYY-MM-DD
  salt TEXT NOT NULL                        -- 32 random bytes, hex
);
CREATE TABLE IF NOT EXISTS rate_hits (
  h TEXT NOT NULL,
  ts INTEGER NOT NULL                       -- unix seconds
);
CREATE INDEX IF NOT EXISTS rate_hits_h ON rate_hits(h, ts);
CREATE INDEX IF NOT EXISTS rate_hits_ts ON rate_hits(ts);
