-- Newsletter signups for Crypto Nordic and Kryptonytt (double opt-in). One row per (email, site).
-- No IP address, user agent or other request metadata is stored. Rate limiting reuses rate_hits (salted hash, 10 minutes).
-- token_hash = SHA-256 of the confirmation token; the token itself only exists in the confirmation link (never stored).
-- Unsubscribe links carry an HMAC (UNSUB_SECRET) over id + email, so no unsubscribe token is stored either.
-- Retention: pending rows that are not confirmed within 7 days are deleted (on the next signup request).
CREATE TABLE IF NOT EXISTS subscribers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL,                       -- lower-cased, trimmed
  site TEXT NOT NULL,                        -- nordic-crypto | kryptonytt
  lang TEXT NOT NULL,                        -- site language at signup (nordic-crypto: en nn nb sv da fi is; kryptonytt: nn nb en)
  status TEXT NOT NULL DEFAULT 'pending',    -- pending | confirmed | unsubscribed
  token_hash TEXT,                           -- SHA-256(confirmation token), NULL once confirmed/unsubscribed
  token_expires INTEGER,                     -- unix seconds
  last_sent_at INTEGER,                      -- unix seconds of the last confirmation email attempt (resend throttle)
  created_at TEXT NOT NULL,                  -- UTC ISO
  confirmed_at TEXT,
  unsubscribed_at TEXT,
  UNIQUE (email, site)
);
CREATE INDEX IF NOT EXISTS subscribers_token ON subscribers(token_hash);
CREATE INDEX IF NOT EXISTS subscribers_site_status ON subscribers(site, status);
