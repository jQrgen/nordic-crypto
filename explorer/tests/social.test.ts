import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import {
  OG_IMAGE_HEIGHT,
  OG_IMAGE_URL,
  OG_IMAGE_WIDTH,
  SITE_NAME,
  TWITTER_SITE,
  chainExplorerTitle,
  pageUrl,
  rootSocial,
  socialMetadata,
  socialTitle,
} from "../lib/social";

test("chain pages use the explorer title", () => {
  assert.equal(chainExplorerTitle("Bitcoin Cash"), "Bitcoin Cash explorer \u2013 Nordic Crypto");
  assert.equal(chainExplorerTitle("Nexa"), "Nexa explorer \u2013 Nordic Crypto");
  assert.equal(socialTitle("Search"), "Search \u2013 Nordic Crypto");
});

test("the share card is absolute https and names Nordic Crypto", () => {
  const meta = socialMetadata({
    title: chainExplorerTitle("Nexa"),
    description: "Blocks, transactions, addresses and group tokens.",
    path: "/nexa/",
  });
  const graph = meta.openGraph;
  assert.ok(graph);
  assert.equal(
    graph.title && typeof graph.title === "object" && "absolute" in graph.title ? graph.title.absolute : "",
    chainExplorerTitle("Nexa"),
  );
  assert.equal("url" in graph ? graph.url : "", pageUrl("/nexa/"));
  assert.equal(pageUrl("/nexa/"), "https://explorer.nordiccrypto.no/nexa/");
  assert.equal(graph.siteName, SITE_NAME);
  const image = Array.isArray(graph.images) ? graph.images[0] : graph.images;
  assert.ok(image && typeof image === "object" && "url" in image);
  assert.equal(image.url, OG_IMAGE_URL);
  assert.equal(OG_IMAGE_URL, "https://explorer.nordiccrypto.no/og.png");
  assert.equal(meta.twitter?.card, "summary_large_image");
  assert.equal(TWITTER_SITE, "@nordiccryptobot");
  assert.equal(meta.twitter && "site" in meta.twitter ? meta.twitter.site : "", TWITTER_SITE);
});

test("the root card is the Bitcoin Cash explorer", () => {
  const meta = rootSocial();
  const title = meta.title;
  assert.ok(title && typeof title === "object" && "absolute" in title);
  assert.equal(title.absolute, chainExplorerTitle("Bitcoin Cash"));
  const graph = meta.openGraph;
  assert.ok(graph && "url" in graph);
  assert.equal(graph.url, "https://explorer.nordiccrypto.no/");
  assert.equal(graph.description, meta.description);
});

test("the preview image is a 1200 by 630 PNG", () => {
  const png = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "../public/og.png"));
  assert.equal(png.subarray(0, 8).toString("hex"), "89504e470d0a1a0a");
  assert.equal(png.readUInt32BE(16), OG_IMAGE_WIDTH);
  assert.equal(png.readUInt32BE(20), OG_IMAGE_HEIGHT);
});
