-- Public refill and mint history, and balance snapshots. No private key,
-- no NexaID, no funder name. txid is the public transaction id.

CREATE TABLE treasury_ledger (
  txid TEXT NOT NULL,
  chain TEXT NOT NULL,
  kind TEXT NOT NULL,
  amount INTEGER NOT NULL,
  at TEXT NOT NULL,
  event_id TEXT,
  PRIMARY KEY (chain, txid, kind)
);

CREATE TABLE balance_snapshot (
  chain TEXT NOT NULL,
  at TEXT NOT NULL,
  amount INTEGER NOT NULL,
  PRIMARY KEY (chain, at)
);
