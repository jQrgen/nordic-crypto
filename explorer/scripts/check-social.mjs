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
  "twitter:site": "@nordiccryptobot",
  "twitter:image": IMAGE,
};

const bchTitle = `Bitcoin Cash explorer ${DASH} Nordic Crypto`;
const nexaTitle = `Nexa explorer ${DASH} Nordic Crypto`;
const bchAbout = "Blocks, transactions and addresses, read in this browser from a Bitcoin Cash Electrum server.";

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
      "og:description": "Blocks, transactions and addresses, read in this browser from a Nexa Rostrum server.",
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
    "bch/tx/index.html",
    {
      "og:title": `Transaction · Bitcoin Cash ${DASH} Nordic Crypto`,
      "og:url": `${ORIGIN}/bch/tx/`,
    },
  ],
  [
    "nexa/block/index.html",
    {
      "og:title": `Block · Nexa ${DASH} Nordic Crypto`,
      "og:url": `${ORIGIN}/nexa/block/`,
    },
  ],
  [
    "bch/address/index.html",
    {
      "og:title": `Address · Bitcoin Cash ${DASH} Nordic Crypto`,
      "og:url": `${ORIGIN}/bch/address/`,
    },
  ],
  [
    "nexa/token/index.html",
    {
      "og:title": `Token · Nexa ${DASH} Nordic Crypto`,
      "og:url": `${ORIGIN}/nexa/token/`,
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

const headerHrefs = [
  "https://nordiccrypto.no/newsletter/#signup",
  "https://t.me/nordiccryptochat",
  "https://x.com/nordiccryptobot",
  "https://github.com/jQrgen/nordic-crypto",
  "https://nordiccrypto.no/rss.xml",
  "https://testflight.apple.com/join/nQ2fpjZn",
  "https://nordiccrypto.no/",
];
const headerLabels = [
  "Follow",
  "Join on Telegram",
  "Follow on X",
  "Source code",
  "RSS",
  "Get the iOS app (TestFlight)",
  "Especially supports Apple TV.",
  "nordiccrypto.no",
];
for (const file of ["bch/index.html", "nexa/index.html", "bch/mempool/index.html", "nexa/tokens/index.html"]) {
  const html = readFileSync(join(out, file), "utf8");
  const bar = html.match(/<nav class="socialbar"[^>]*>[\s\S]*?<\/nav>/);
  if (!bar) {
    errors.push(`${file} missing social bar`);
    continue;
  }
  const hrefs = [...bar[0].matchAll(/href="([^"]+)"/g)].map((m) => m[1]);
  if (hrefs.join("\n") !== headerHrefs.join("\n")) {
    errors.push(`${file} social links: expected ${headerHrefs.join(", ")}, got ${hrefs.join(", ")}`);
  }
  for (const label of headerLabels) {
    if (!bar[0].includes(label)) errors.push(`${file} social bar missing ${JSON.stringify(label)}`);
  }
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
