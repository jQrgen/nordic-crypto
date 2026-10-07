// node --test workers/country-domains/  (pure routing and link mapping; HTMLRewriter is only used at runtime)
import test from "node:test";
import assert from "node:assert/strict";
import { route, mapUrl, toCountryPath } from "./worker.js";

test("routing on nordiccrypto.se", () => {
  assert.deepEqual(route("/", "sv", ""), { origin: "/sv/" });
  assert.deepEqual(route("/", "sv", "nc_lang=sv"), { origin: "/sv/" });
  assert.deepEqual(route("/", "sv", "a=1; nc_lang=en"), { redirect: "/en/", status: 302 });
  assert.deepEqual(route("/", "sv", "nc_lang=da"), { redirect: "/da/", status: 302 });
  assert.deepEqual(route("/sv/", "sv", ""), { redirect: "/", status: 301 });
  assert.deepEqual(route("/en/", "sv", ""), { origin: "/", english: true });
  assert.deepEqual(route("/en/sv/", "sv", ""), { redirect: "/", status: 302 });
  assert.deepEqual(route("/sv/about/", "sv", ""), { origin: "/sv/about/" });
  assert.deepEqual(route("/api/v1/news.json", "sv", ""), { origin: "/api/v1/news.json" });
});

test("link mapping keeps readers on the country domain", () => {
  const page = "https://nordiccrypto.no/sv/";
  assert.equal(mapUrl("../", page, "sv"), "/en/");
  assert.equal(mapUrl("../sv/", page, "sv"), "/");
  assert.equal(mapUrl("stories/abc/", page, "sv"), "/sv/stories/abc/");
  assert.equal(mapUrl("../assets/x.webp", page, "sv"), "/assets/x.webp");
  assert.equal(mapUrl("https://nordiccrypto.no/da/", page, "sv"), "/da/");
  assert.equal(mapUrl("https://x.com/xcryptonordic", page, "sv"), null);
  assert.equal(mapUrl("#top", page, "sv"), null);
  assert.equal(mapUrl("mailto:a@b.c", page, "sv"), null);
  assert.equal(toCountryPath("/fi/index.html", "fi"), "/");
});
