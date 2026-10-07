-- One shared shoutbox. There is no language column used as a room: lang is only the page
-- the message was posted from. Every reader sees every visible row.
-- ip_hash is SHA-256(daily salt || IP). The salt in shout_salt is replaced every UTC day and
-- older salts are deleted, so a hash cannot be turned back into an IP or matched across days.
-- The raw IP is never stored. shout_hits older than the rate-limit window are deleted on write.
CREATE TABLE IF NOT EXISTS shouts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,                 -- UTC ISO timestamp
  nickname TEXT NOT NULL,                   -- plain text, 2–24 characters
  message TEXT NOT NULL,                    -- plain text, tags removed, max 280 characters
  lang TEXT,                                -- optional page-language tag, not a channel
  ip_hash TEXT NOT NULL,                    -- daily-rotated hash, never the raw IP
  status TEXT NOT NULL DEFAULT 'visible',   -- visible | hidden (hidden = pending review)
  reports INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS shouts_visible_id ON shouts(status, id);

CREATE TABLE IF NOT EXISTS shout_reports (
  shout_id INTEGER NOT NULL,
  ip_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (shout_id, ip_hash)
);

CREATE TABLE IF NOT EXISTS shout_bans (
  ip_hash TEXT PRIMARY KEY,                 -- today's hash only; the salt is gone tomorrow
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shout_salt (
  day TEXT PRIMARY KEY,                     -- UTC date YYYY-MM-DD
  salt TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shout_hits (
  h TEXT NOT NULL,
  ts INTEGER NOT NULL,                      -- unix seconds
  kind TEXT NOT NULL                        -- post | report
);
CREATE INDEX IF NOT EXISTS shout_hits_h ON shout_hits(h, kind, ts);
CREATE INDEX IF NOT EXISTS shout_hits_ts ON shout_hits(ts);
