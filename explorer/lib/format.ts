import type { ChainMeta, Fiat } from "./types";

const FIAT_LABEL: Record<Fiat, string> = {
  NOK: "NOK",
  SEK: "SEK",
  DKK: "DKK",
  EUR: "EUR",
  USD: "USD",
};

export function formatCompact(value: number) {
  const abs = Math.abs(value);
  if (abs >= 1e12) return `${(value / 1e12).toFixed(2)} trillion`;
  if (abs >= 1e9) return `${(value / 1e9).toFixed(2)} billion`;
  if (abs >= 1e6) return `${(value / 1e6).toFixed(2)} million`;
  return formatNumber(value);
}

export function formatNumber(value: number, digits = 0) {
  return new Intl.NumberFormat("en-GB", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

export function formatCoin(amount: number, chain: Pick<ChainMeta, "ticker" | "decimals">) {
  const min = amount !== 0 && Math.abs(amount) < 1 ? 0 : 2;
  const body = new Intl.NumberFormat("en-GB", {
    minimumFractionDigits: Math.min(min, chain.decimals),
    maximumFractionDigits: chain.decimals,
  }).format(amount);
  return `${body} ${chain.ticker}`;
}

export function formatTokenAmount(amount: number, decimals: number, ticker: string) {
  const body = new Intl.NumberFormat("en-GB", {
    minimumFractionDigits: 0,
    maximumFractionDigits: decimals,
  }).format(amount);
  return `${body} ${ticker}`;
}

export function formatFiat(value: number, fiat: Fiat) {
  const abs = Math.abs(value);
  const digits = abs === 0 || abs >= 0.01 ? 2 : 6;
  const body = new Intl.NumberFormat("en-GB", {
    minimumFractionDigits: 2,
    maximumFractionDigits: digits,
  }).format(value);
  return `${body} ${FIAT_LABEL[fiat]}`;
}

/** Bytes assumed when a fee rate is turned into a transaction cost. */
export const TYPICAL_TX_BYTES = 250;

/** Stated wherever a fee-rate fiat estimate is shown. */
export const TYPICAL_TX_NOTE = `for a ~${TYPICAL_TX_BYTES} byte transaction`;

const SATS_PER_COIN = 100_000_000;

const LOCAL_MARK: Record<Fiat, { place: "prefix" | "suffix"; mark: string }> = {
  NOK: { place: "suffix", mark: "kr" },
  SEK: { place: "suffix", mark: "kr" },
  DKK: { place: "suffix", mark: "kr" },
  EUR: { place: "prefix", mark: "€" },
  USD: { place: "prefix", mark: "$" },
};

/**
 * Whole coins a transaction of `bytes` costs at this fee rate.
 * `sat/byte` counts chain subunits (`satsPerCoin` is 1e8 on Bitcoin Cash and 100 on Nexa).
 * Any other unit, such as `NEX/byte`, is already whole coins.
 * Returns null when the text is not `number unit/byte`.
 */
export function coinCostAtFeeRate(feeRate: string, bytes = TYPICAL_TX_BYTES, satsPerCoin = SATS_PER_COIN): number | null {
  const match = /^(\d+(?:\.\d+)?)\s+([A-Za-z]+)\/byte$/.exec(feeRate.trim());
  if (!match) return null;
  const perByte = Number(match[1]);
  if (!Number.isFinite(perByte) || satsPerCoin <= 0) return null;
  return match[2].toLowerCase() === "sat" ? (perByte * bytes) / satsPerCoin : perByte * bytes;
}

/** Amount in the currency's usual symbol, with the site's en-GB digits. */
export function formatLocalFiat(value: number, fiat: Fiat) {
  const abs = Math.abs(value);
  const digits = abs === 0 || abs >= 0.01 ? 2 : 6;
  const body = new Intl.NumberFormat("en-GB", {
    minimumFractionDigits: 2,
    maximumFractionDigits: digits,
  }).format(value);
  const { place, mark } = LOCAL_MARK[fiat];
  return place === "prefix" ? `${mark}${body}` : `${body} ${mark}`;
}

/**
 * `5 sat/byte · ≈ 0.12 kr`.
 * `pricePerCoin` is the fiat price of one whole coin. The caller supplies it; this does not look a price up.
 * An unrecognised rate, or a missing price, is returned unchanged.
 */
export function formatFeeRateQuote(
  feeRate: string,
  pricePerCoin: number,
  fiat: Fiat,
  bytes = TYPICAL_TX_BYTES,
  satsPerCoin = SATS_PER_COIN,
): string {
  const coin = coinCostAtFeeRate(feeRate, bytes, satsPerCoin);
  if (coin == null || !Number.isFinite(pricePerCoin)) return feeRate;
  return `${feeRate} · ≈ ${formatLocalFiat(coin * pricePerCoin, fiat)}`;
}

export function formatFeeRateLabel(
  feeRate: string,
  pricePerCoin: number,
  fiat: Fiat,
  bytes = TYPICAL_TX_BYTES,
  satsPerCoin = SATS_PER_COIN,
) {
  const quote = formatFeeRateQuote(feeRate, pricePerCoin, fiat, bytes, satsPerCoin);
  return { quote, note: quote === feeRate ? null : TYPICAL_TX_NOTE };
}

export function formatUnitPrice(value: number, fiat: Fiat) {
  const digits = value >= 1 ? 2 : value >= 0.01 ? 4 : 8;
  const body = new Intl.NumberFormat("en-GB", {
    minimumFractionDigits: 2,
    maximumFractionDigits: digits,
  }).format(value);
  return `${body} ${FIAT_LABEL[fiat]}`;
}

export function formatDifficulty(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return "—";
  if (value >= 100) return formatNumber(value, 0);
  if (value >= 1) return formatNumber(value, 2);
  return value.toPrecision(4);
}

export function formatSatPerByte(satPerByte: number) {
  const body = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 2, useGrouping: false }).format(satPerByte);
  return `${body} sat/byte`;
}

export function formatRawAmount(amount: string) {
  if (!/^\d+$/.test(amount)) return amount;
  try {
    return BigInt(amount).toLocaleString("en-GB");
  } catch {
    return amount;
  }
}

export function formatAge(iso: string | null, now = Date.now()) {
  if (!iso) return "Waiting";
  const mins = Math.max(0, Math.round((now - Date.parse(iso)) / 60000));
  if (mins < 1) return "Under a minute ago";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.floor(mins / 60);
  const rest = mins % 60;
  if (hours < 48) return rest ? `${hours} h ${rest} min ago` : `${hours} h ago`;
  return `${Math.floor(hours / 24)} days ago`;
}

export function formatWhen(iso: string) {
  const oslo = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Oslo",
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).format(new Date(iso));
  const utc = new Intl.DateTimeFormat("en-GB", {
    timeZone: "UTC",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).format(new Date(iso));
  return `${oslo} Oslo · ${utc} UTC`;
}

export function formatBytes(bytes: number) {
  if (bytes < 1024) return `${formatNumber(bytes)} B`;
  if (bytes < 1024 * 1024) return `${formatNumber(bytes / 1024, 1)} KB`;
  return `${formatNumber(bytes / (1024 * 1024), 2)} MB`;
}

export function formatGap(laterIso: string, earlierIso: string) {
  const secs = Math.max(0, Math.round((Date.parse(laterIso) - Date.parse(earlierIso)) / 1000));
  const mins = Math.floor(secs / 60);
  const rest = secs % 60;
  if (mins <= 0) return `${rest} sec`;
  return `${mins} min ${rest.toString().padStart(2, "0")} sec`;
}

export function shortId(value: string, head = 18, tail = 8) {
  if (value.length <= head + tail + 1) return value;
  return `${value.slice(0, head)}…${value.slice(-tail)}`;
}

export function formatChange(change: number | null) {
  if (change == null) return null;
  const sign = change > 0 ? "+" : "";
  return `${sign}${change.toFixed(1)}%`;
}
