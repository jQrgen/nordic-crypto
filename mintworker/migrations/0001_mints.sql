-- Mint dedupe and public hot-wallet address. No private key, no raw NexaID, no raw address of a minter.
-- The hot key is a Worker secret, not a column.

CREATE TABLE hot_address (
  chain TEXT PRIMARY KEY,
  address TEXT NOT NULL
);

CREATE TABLE hot_observed (
  chain TEXT PRIMARY KEY,
  amount INTEGER NOT NULL,
  observed_at TEXT NOT NULL
);

CREATE TABLE mint_claim (
  h TEXT PRIMARY KEY,
  chain TEXT NOT NULL,
  event_id TEXT NOT NULL,
  day TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX mint_claim_event ON mint_claim (chain, event_id);
CREATE INDEX mint_claim_day ON mint_claim (chain, day);
