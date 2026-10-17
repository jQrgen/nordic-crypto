-- Private admin page (/admin/ on the site): passwordless magic-link login, bearer sessions, login log, and a record of
-- which newsletter issue each subscriber has received. Only SHA-256 hashes of login tokens and session tokens are stored.
CREATE TABLE IF NOT EXISTS admin_login_tokens (
  token_hash TEXT PRIMARY KEY,               -- SHA-256(one-time token); the token itself is only in the emailed link
  email TEXT NOT NULL,                       -- lower-cased, @ADMIN_EMAIL_DOMAIN only
  created_at INTEGER NOT NULL,               -- unix seconds
  expires_at INTEGER NOT NULL,               -- created_at + 15 minutes
  used_at INTEGER                            -- set on first use; a used token never works again
);
CREATE INDEX IF NOT EXISTS admin_login_tokens_email ON admin_login_tokens(email, created_at);
CREATE TABLE IF NOT EXISTS admin_sessions (
  token_hash TEXT PRIMARY KEY,               -- SHA-256(bearer session token)
  email TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL                -- created_at + 7 days
);
CREATE TABLE IF NOT EXISTS admin_logins (    -- login log: who signed in and when (no IP, no user agent)
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL,
  at TEXT NOT NULL                           -- UTC ISO
);
CREATE TABLE IF NOT EXISTS newsletter_deliveries (
  subscriber_id INTEGER NOT NULL,            -- subscribers.id
  issue INTEGER NOT NULL,                    -- newsletter issue number (#)
  sent_at TEXT NOT NULL,                     -- UTC ISO
  PRIMARY KEY (subscriber_id, issue)
);
CREATE INDEX IF NOT EXISTS newsletter_deliveries_issue ON newsletter_deliveries(issue);
