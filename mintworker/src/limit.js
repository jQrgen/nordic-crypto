// In-memory mint rate limit. The raw IP is hashed and then dropped. Nothing
// here is written to D1. An isolate that restarts forgets the window.

const WINDOW_MS = 10 * 60 * 1000;
const PER_CLIENT = 8;
const GLOBAL_MAX = 40;

const clients = new Map();
let globalHits = [];

const hex = (buf) => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");

export function resetRates() {
  clients.clear();
  globalHits = [];
}

export async function clientHash(ip) {
  const raw = String(ip || "unknown").trim().slice(0, 64);
  return hex(await crypto.subtle.digest("SHA-256", new TextEncoder().encode("mint-rate|" + raw)));
}

export async function allowClient(ip, now = Date.now()) {
  const hash = await clientHash(ip);
  globalHits = globalHits.filter((t) => now - t < WINDOW_MS);
  const mine = (clients.get(hash) || []).filter((t) => now - t < WINDOW_MS);
  if (mine.length >= PER_CLIENT || globalHits.length >= GLOBAL_MAX) {
    clients.set(hash, mine);
    return false;
  }
  mine.push(now);
  globalHits.push(now);
  clients.set(hash, mine);
  if (clients.size > 4000) {
    const oldest = clients.keys().next().value;
    clients.delete(oldest);
  }
  return true;
}

export { PER_CLIENT, WINDOW_MS };
