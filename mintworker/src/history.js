// Public treasury history. Rows are refills (coins in) and mints (coins out).
// The public shape is an allow-list: time, kind, amount, txid, explorer link,
// and the event id for a mint. No name, no NexaID, no funder label.

const EXPLORER = {
  nexa: "https://testnet-explorer.nexa.org/tx/",
  bch: "https://chipnet.imaginary.cash/tx/",
};

const NEXA_PER_SAT = 100;

// hot_observed stores the chain's smallest unit (satoshis). Nexa's public
// unit is NEXA, and 1 NEXA is 100 of those. Policy compares NEXA, so a Nexa
// balance is divided here. Floor keeps a partial NEXA from counting as a
// whole one against the reserve.
export function displayAmount(chain, sats) {
  if (sats == null) return null;
  const n = Number(sats);
  if (!Number.isFinite(n)) return null;
  return chain === "nexa" ? n / NEXA_PER_SAT : n;
}

export function policyAmount(chain, sats) {
  const shown = displayAmount(chain, sats);
  if (shown == null) return null;
  return chain === "nexa" ? Math.floor(shown) : shown;
}

export function explorerUrl(chain, txid) {
  const base = EXPLORER[chain];
  if (!base || !/^[0-9a-fA-F]{64}$/.test(String(txid))) return null;
  return base + String(txid).toLowerCase();
}

export function toPublic(row) {
  const amount = row.chain === "nexa" ? row.amount / NEXA_PER_SAT : row.amount;
  const out = {
    chain: row.chain,
    kind: row.kind,
    at: row.at,
    amount,
    unit: row.chain === "nexa" ? "NEXA" : "sats",
    txid: String(row.txid).toLowerCase(),
    explorer_url: explorerUrl(row.chain, row.txid),
  };
  if (row.kind === "mint" && row.event_id) out.event_id = row.event_id;
  return out;
}

export function seriesFrom(chain, snapshots, ledger) {
  const points = [];
  for (const s of snapshots || []) {
    if (s.chain === chain) points.push({ at: s.at, amount: s.amount, set: true });
  }
  for (const row of ledger || []) {
    if (row.chain !== chain) continue;
    const delta = row.kind === "refill" ? row.amount : -row.amount;
    points.push({ at: row.at, amount: delta, set: false });
  }
  points.sort((a, b) => (a.at < b.at ? -1 : a.at > b.at ? 1 : 0));
  let balance = 0;
  const series = [];
  for (const p of points) {
    balance = p.set ? p.amount : balance + p.amount;
    const shown = chain === "nexa" ? balance / NEXA_PER_SAT : balance;
    series.push({ at: p.at, amount: shown });
  }
  return series;
}

export async function ingestRefills(db, chain, txs) {
  for (const tx of txs || []) {
    if (!tx || !tx.txid || tx.amount == null || !tx.at) continue;
    await recordLedger(db, {
      txid: tx.txid,
      chain,
      kind: "refill",
      amount: Number(tx.amount),
      at: tx.at,
      event_id: null,
    });
  }
}

export async function recordLedger(db, row) {
  if (!db) return;
  await db.prepare(
    "INSERT OR IGNORE INTO treasury_ledger (txid, chain, kind, amount, at, event_id) VALUES (?, ?, ?, ?, ?, ?)"
  ).bind(row.txid, row.chain, row.kind, row.amount, row.at, row.event_id || null).run();
}

export async function recordSnapshot(db, chain, amount, at) {
  if (!db) return;
  await db.prepare(
    "INSERT OR REPLACE INTO balance_snapshot (chain, at, amount) VALUES (?, ?, ?)"
  ).bind(chain, at, amount).run();
}

export async function readLedger(db) {
  if (!db) return [];
  const res = await db.prepare(
    "SELECT txid, chain, kind, amount, at, event_id FROM treasury_ledger ORDER BY at"
  ).all();
  return res.results || [];
}

export async function readSnapshots(db) {
  if (!db) return [];
  const res = await db.prepare(
    "SELECT chain, at, amount FROM balance_snapshot ORDER BY at"
  ).all();
  return res.results || [];
}

function addressList(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value.map((a) => String(a));
  return [String(value)];
}

function outputAddresses(output) {
  const script = output.scriptPubKey || output.script || {};
  return addressList(output.address || output.addresses || script.address || script.addresses);
}

function inputAddresses(input) {
  const script = input.scriptPubKey || input.script || {};
  return addressList(input.address || input.addresses || script.address || script.addresses);
}

function satValue(output) {
  const raw = output.value_satoshis ?? output.value_sats ?? output.satoshis ?? output.value;
  if (typeof raw === "string" && /^[0-9]+$/.test(raw)) {
    const n = Number(raw);
    return Number.isSafeInteger(n) ? n : null;
  }
  if (typeof raw === "number" && Number.isSafeInteger(raw)) return raw;
  return null;
}

function isoTime(raw) {
  if (typeof raw === "number" && raw > 1_000_000_000) return new Date(raw * 1000).toISOString();
  if (typeof raw === "string" && /^\d{4}-\d{2}-\d{2}T/.test(raw)) return raw;
  return null;
}

// A refill is coins arriving at the hot address from a transaction that does
// not spend that address. Amounts must already be integer satoshis. A float
// (some explorers use whole coins) is skipped rather than guessed.
export function refillFromTx(tx, address) {
  if (!tx || typeof tx !== "object") return null;
  const mine = String(address || "");
  if (!mine) return null;
  const at = isoTime(tx.time || tx.blocktime || tx.at);
  if (!at) return null;
  const outputs = tx.vout || tx.outputs || [];
  let incoming = 0;
  let saw = false;
  for (const output of outputs) {
    if (!outputAddresses(output).includes(mine)) continue;
    const sats = satValue(output);
    if (sats == null) return null;
    incoming += sats;
    saw = true;
  }
  if (!saw || incoming <= 0) return null;
  let sawInputAddress = false;
  for (const input of tx.vin || tx.inputs || []) {
    const addrs = inputAddresses(input);
    if (!addrs.length) continue;
    sawInputAddress = true;
    if (addrs.includes(mine)) return null;
  }
  if (!sawInputAddress) return null;
  const txid = String(tx.txid || tx.hash || "").toLowerCase();
  if (!/^[0-9a-f]{64}$/.test(txid)) return null;
  return { txid, amount: incoming, at };
}

export async function publicHistory(db) {
  const ledger = await readLedger(db);
  const snapshots = await readSnapshots(db);
  return {
    history: ledger.map(toPublic),
    balance_series: {
      nexa: seriesFrom("nexa", snapshots, ledger),
      bch: seriesFrom("bch", snapshots, ledger),
    },
  };
}
