-- Public token ids created by the one-off admin setup. Not a key, not a minter address.

CREATE TABLE token_setup (
  chain TEXT PRIMARY KEY,
  public_id TEXT NOT NULL,
  txid TEXT NOT NULL,
  created_at TEXT NOT NULL
);
