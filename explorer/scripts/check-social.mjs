/**
 * Confirm the static export carries Open Graph and Twitter cards.
 * npm runs this after `next build`. nginx sends `/` to `/bch/`; the root
 * index.html still has the card, for crawlers that do not follow the redirect.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const out = join(root, "out");
const ORIGIN = "https://explorer.nordiccrypto.no";
const IMAGE = `${ORIGIN}/og.png`;
const DASH = "\u2013";

function decode(value) {
  return value
    .replace(/&#x([0-9a-f]+);/gi, (_, hex) => String.fromCodePoint(Number.parseInt(hex, 16)))
    .replace(/&#(\d+);/g, (_, num) => String.fromCodePoint(Number(num)))
    .replace(/&quot;/g, '"')
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&");
}

function metas(html) {
  const found = new Map();
  for (const tag of html.matchAll(/<meta\s+([^>]+)>/g)) {
    const attrs = {};
    for (const attr of tag[1].matchAll(/([\w:-]+)="([^"]*)"/g)) attrs[attr[1]] = decode(attr[2]);
    const key = attrs.property || attrs.name;
    if (!key || attrs.content == null) continue;
    const list = found.get(key) ?? [];
    list.push(attrs.content);
    found.set(key, list);
  }
  return found;
}

function expect(file, checks) {
  const tags = metas(readFileSync(join(out, file), "utf8"));
  const errors = [];
  for (const [key, value] of Object.entries(checks)) {
    const got = tags.get(key) ?? [];
    if (!got.includes(value)) {
      errors.push(`${file} ${key}: expected ${JSON.stringify(value)}, got ${JSON.stringify(got)}`);
    }
  }
  return errors;
}

const shared = {
  "og:site_name": "Nordic Crypto",
  "og:image": IMAGE,
  "og:image:width": "1200",
  "og:image:height": "630",
  "twitter:card": "summary_large_image",
  "twitter:site": "@xcryptonordic",
  "twitter:image": IMAGE,
};

const bchTitle = `Bitcoin Cash explorer ${DASH} Nordic Crypto`;
const nexaTitle = `Nexa explorer ${DASH} Nordic Crypto`;
const bchAbout =
  "Blocks, transactions, addresses and CashTokens, read from Nordic Crypto\u2019s own Rostrum server.";

const pages = [
  [
    "index.html",
    {
      "og:title": bchTitle,
      "og:description": bchAbout,
      "og:url": `${ORIGIN}/`,
    },
  ],
  [
    "bch/index.html",
    {
      "og:title": bchTitle,
      "og:description": bchAbout,
      "og:url": `${ORIGIN}/bch/`,
    },
  ],
  [
    "nexa/index.html",
    {
      "og:title": nexaTitle,
      "og:description":
        "Blocks, transactions, addresses and native group tokens, read from Nordic Crypto\u2019s own Rostrum server.",
      "og:url": `${ORIGIN}/nexa/`,
    },
  ],
  [
    "search/index.html",
    {
      "og:title": `Search ${DASH} Nordic Crypto`,
      "og:url": `${ORIGIN}/search/`,
    },
  ],
  [
    "bch/mempool/index.html",
    {
      "og:title": `Mempool · Bitcoin Cash ${DASH} Nordic Crypto`,
      "og:url": `${ORIGIN}/bch/mempool/`,
    },
  ],
  [
    "nexa/tokens/index.html",
    {
      "og:title": `Tokens · Nexa ${DASH} Nordic Crypto`,
      "og:url": `${ORIGIN}/nexa/tokens/`,
    },
  ],
  [
    "bch/tx/fjord-send/index.html",
    {
      "og:title": `Transaction · Bitcoin Cash ${DASH} Nordic Crypto`,
      "og:url": `${ORIGIN}/bch/tx/fjord-send/`,
    },
  ],
  [
    "nexa/block/1168213/index.html",
    {
      "og:title": `Block 1,168,213 · Nexa ${DASH} Nordic Crypto`,
      "og:url": `${ORIGIN}/nexa/block/1168213/`,
    },
  ],
  [
    "bch/address/sigrid-bch/index.html",
    {
      "og:title": `Sigrid · Bitcoin Cash ${DASH} Nordic Crypto`,
      "og:url": `${ORIGIN}/bch/address/sigrid-bch/`,
    },
  ],
  [
    "nexa/token/agnar/index.html",
    {
      "og:title": `AGNAR · Agnar · Nexa ${DASH} Nordic Crypto`,
      "og:url": `${ORIGIN}/nexa/token/agnar/`,
    },
  ],
  [
    "design/loading/index.html",
    {
      "og:title": `Loading ${DASH} Nordic Crypto`,
      "og:url": `${ORIGIN}/design/loading/`,
    },
  ],
  [
    "404.html",
    {
      "og:title": `Page not found ${DASH} Nordic Crypto`,
      "og:url": `${ORIGIN}/404.html`,
    },
  ],
];

const errors = [];
for (const [file, checks] of pages) {
  errors.push(...expect(file, { ...shared, ...checks }));
  const tags = metas(readFileSync(join(out, file), "utf8"));
  const title = tags.get("og:title")?.[0];
  if (title && tags.get("twitter:title")?.[0] !== title) {
    errors.push(`${file} twitter:title does not match og:title`);
  }
  if (!tags.get("og:description")?.[0]) errors.push(`${file} missing og:description`);
}

const png = readFileSync(join(out, "og.png"));
if (png.subarray(0, 8).toString("hex") !== "89504e470d0a1a0a" || png.readUInt32BE(16) !== 1200 || png.readUInt32BE(20) !== 630) {
  errors.push("out/og.png is not a 1200x630 PNG");
}

if (errors.length) {
  console.error(errors.join("\n"));
  process.exit(1);
}

console.log(`social cards ok (${pages.length} pages)`);
