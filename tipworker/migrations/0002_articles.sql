-- 0002_articles.sql – append-only article archive in Cloudflare D1 (mirror of archive/articles.db).
-- Same schema as archive/schema.sql (shared with Kryptonytt; `site` column tells the two apart) incl. the additive v2 column `country`.
-- Rows are never deleted: triggers block DELETE on articles and DELETE/UPDATE on article_events.
-- Apply:  npx wrangler d1 migrations apply <db-name> --remote   (needs CLOUDFLARE_API_TOKEN; not applied yet)
-- Load data: generate INSERTs from archive/articles.json (see tipworker/README.md).
CREATE TABLE IF NOT EXISTS articles (
  site                     TEXT NOT NULL,            -- 'kryptonytt' | 'nordic-crypto'
  id                       TEXT NOT NULL,            -- saks-id på nettstaden (stabil)
  url                      TEXT NOT NULL,            -- lenkja slik ho står på nettstaden
  canonical_url            TEXT NOT NULL,            -- normalisert (https, utan www., utan sporingsparametrar, utan / til slutt)
  title                    TEXT NOT NULL,            -- tittelen frå kjelda
  source                   TEXT,                     -- kjelde-id
  source_name              TEXT,
  published_at             TEXT,                     -- når kjelda publiserte (ISO 8601 med tidssone)
  first_published_on_site  TEXT NOT NULL,            -- første gong saka var publisert hos oss (ISO 8601)
  last_seen_on_site        TEXT,                     -- siste publisering der saka var med
  languages                TEXT NOT NULL DEFAULT '[]', -- JSON-liste med språk vi har oppsummering på, t.d. ["nn","nb","en"]
  summaries                TEXT NOT NULL DEFAULT '{}', -- JSON-objekt språk -> eiga oppsummering
  titles                   TEXT NOT NULL DEFAULT '{}', -- JSON-objekt språk -> eigen omsett tittel (berre når vi har laga ein)
  topics                   TEXT NOT NULL DEFAULT '[]', -- JSON-liste
  origin                   TEXT,                     -- intern merknad, t.d. «tips frå Crypto Nordic» (ikkje offentleg)
  removed                  INTEGER NOT NULL DEFAULT 0, -- 1 = teken av nettstaden seinare
  removed_at               TEXT,
  removal_reason           TEXT,
  updated_at               TEXT NOT NULL,
  country                  TEXT,                     -- v2: ISO 3166 code of the story's country
  PRIMARY KEY (site, id)
);
CREATE INDEX IF NOT EXISTS idx_articles_canonical ON articles(canonical_url);
CREATE INDEX IF NOT EXISTS idx_articles_first ON articles(site, first_published_on_site);
-- Hendingslogg (berre innsetjing): published, updated, removed, republished, backfill
CREATE TABLE IF NOT EXISTS article_events (
  seq        INTEGER PRIMARY KEY AUTOINCREMENT,
  site       TEXT NOT NULL,
  id         TEXT NOT NULL,
  at         TEXT NOT NULL,
  event      TEXT NOT NULL,
  detail     TEXT
);
CREATE TRIGGER IF NOT EXISTS articles_no_delete BEFORE DELETE ON articles BEGIN SELECT RAISE(ABORT, 'append-only: articles are never deleted'); END;
CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON article_events BEGIN SELECT RAISE(ABORT, 'append-only: events are never deleted'); END;
CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON article_events BEGIN SELECT RAISE(ABORT, 'append-only: events are never changed'); END;
-- Version 2 (2026-10-03, additive, Crypto Nordic): country column (ISO 3166 code of the story's country, e.g. 'SE').
-- SQLite has no "ADD COLUMN IF NOT EXISTS", so tools/article_archive.py adds it when missing:
--   ALTER TABLE articles ADD COLUMN country TEXT;
