// Writes the Nexa token list ranked by transfer count from explorer.nexa.org's Token Tracker.
// Usage: node token-stats.mjs <out.json>
import { renameSync, writeFileSync } from "node:fs";

const base = "https://explorer.nexa.org/tokens";
const out = process.argv[2] ?? "nexa-tokens.json";
const text = (s) => s.replace(/<[^>]+>/g, "").replace(/&amp;/g, "&").replace(/&#39;/g, "'").replace(/&quot;/g, '"').replace(/&lt;/g, "<").replace(/&gt;/g, ">").trim();
const num = (s) => Number(text(s).replace(/,/g, ""));

async function page() {
  const res = await fetch(`${base}?sort=desc&limit=5000&offset=0`, { headers: { "user-agent": "explorer.nordiccrypto.no token-stats" } });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.text();
}

const html = await page();
const total = num(html.match(/Tokens<\/h5><span[^>]*>([\d,]+)/)?.[1] ?? "0");
const lastBlock = num(html.match(/Last Block<\/h5><span[^>]*>([\d,]+)/)?.[1] ?? "0");
if (!total) throw new Error("token count not found");
const tokens = new Map();
{
  for (const row of html.split("<tr>").slice(1)) {
    const cells = [...row.matchAll(/<td[^>]*>([\s\S]*?)<\/td>/g)].map((m) => m[1]);
    const id = cells[2]?.match(/\/token\/(nexa:[a-z0-9]+)/)?.[1];
    if (!id || cells.length < 6) continue;
    const label = text(cells[1]);
    const m = label.match(/^(.*) \(([^()]*)\)$/);
    tokens.set(id, { id, name: m ? m[1] : label || null, ticker: m ? m[2] : null, txs: num(cells[3]), holders: num(cells[4]) });
  }
}
const list = [...tokens.values()].filter((t) => Number.isFinite(t.txs)).sort((a, b) => b.txs - a.txs);
if (list.length < total * 0.9) throw new Error(`only ${list.length} of ${total} tokens parsed`);
writeFileSync(`${out}.tmp`, JSON.stringify({ source: base, fetchedAt: new Date().toISOString(), lastBlock, tokens: list }));
renameSync(`${out}.tmp`, out);
console.log(`${list.length} tokens, block ${lastBlock}`);
