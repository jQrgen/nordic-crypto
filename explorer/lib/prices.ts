import { chainOrder } from "./chains";
import type { ChainId, Fiat } from "./types";

const GECKO_URL =
  "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin-cash,nexacoin&vs_currencies=usd,eur,nok,sek,dkk&include_24hr_change=true";

/**
 * CoinGecko ids. `nexacoin` is NEXA. The id `nexa` is a different listing whose
 * price is about 1,000× higher and whose market cap is zero.
 */
const IDS: Record<ChainId, string> = { bch: "bitcoin-cash", nexa: "nexacoin" };
const FIATS: Fiat[] = ["USD", "EUR", "NOK", "SEK", "DKK"];

export type PriceBook = Record<ChainId, { quotes: Partial<Record<Fiat, number>>; change: Partial<Record<Fiat, number | null>> }>;

export function parseGecko(body: unknown): PriceBook | null {
  if (!body || typeof body !== "object") return null;
  const root = body as Record<string, unknown>;
  let any = false;
  const book = {} as PriceBook;
  for (const chain of chainOrder) {
    const row = root[IDS[chain]];
    const quotes: Partial<Record<Fiat, number>> = {};
    const change: Partial<Record<Fiat, number | null>> = {};
    if (row && typeof row === "object") {
      const record = row as Record<string, unknown>;
      for (const fiat of FIATS) {
        const key = fiat.toLowerCase();
        const price = record[key];
        if (typeof price === "number" && Number.isFinite(price)) {
          quotes[fiat] = price;
          any = true;
        }
        const delta = record[`${key}_24h_change`];
        if (typeof delta === "number" && Number.isFinite(delta)) change[fiat] = delta;
        else if (delta === null) change[fiat] = null;
      }
    }
    book[chain] = { quotes, change };
  }
  return any ? book : null;
}

let cache: { at: number; book: PriceBook } | null = null;
const TTL_MS = 60_000;

export function clearPriceCache() {
  cache = null;
}

export async function loadPrices(fetchImpl: typeof fetch = fetch): Promise<PriceBook | null> {
  if (cache && Date.now() - cache.at < TTL_MS) return cache.book;
  try {
    const response = await fetchImpl(GECKO_URL, { headers: { accept: "application/json" } });
    if (!response.ok) return null;
    const book = parseGecko(await response.json());
    if (book) cache = { at: Date.now(), book };
    return book;
  } catch {
    return null;
  }
}

/** Fiat value of a coin amount. Null hides the figure instead of inventing a rate. */
export function fiatAmount(coins: number, unitPrice: number | null): number | null {
  if (unitPrice == null || !Number.isFinite(unitPrice)) return null;
  return coins * unitPrice;
}
