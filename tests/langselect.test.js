// Unit tests for tools/langselect.js decide(). Run: node --test tests/*.test.js  (Node >= 18)
const test = require("node:test"), assert = require("node:assert"), fs = require("fs"), path = require("path"), Module = require("module");
const src = fs.readFileSync(path.join(__dirname, "..", "tools", "langselect.js"), "utf8")
  .replace("__LANGS__", JSON.stringify(["en", "nn", "nb", "sv", "da", "fi", "is"])).replace("__GEO__", JSON.stringify("https://geo.example/api/geo"));
const m = new Module("langselect"); m._compile(src, "langselect.js"); const L = m.exports;
test("cookie wins over geo and navigator", () => {
  assert.deepStrictEqual(L.decide({ cookie: "nc_lang=nb", country: "SE", languages: ["fi"] }), { lang: "nb", why: "cookie" });
  assert.strictEqual(L.decide({ cookie: "a=1; nc_lang=en; b=2", country: "NO" }).lang, "en");
});
test("invalid cookie is ignored", () => {
  assert.strictEqual(L.decide({ cookie: "nc_lang=de", country: "DK" }).lang, "da");
  assert.strictEqual(L.decide({ cookie: "nc_lang=nbx", country: "DK" }).why, "geo");
  assert.strictEqual(L.decide({ cookie: "xnc_lang=sv", country: "FI" }).lang, "fi");
});
test("country map", () => {
  const exp = { NO: "nn", SE: "sv", DK: "da", FI: "fi", IS: "is", AX: "sv", FO: "da", GL: "da", no: "nn" };
  for (const [c, l] of Object.entries(exp)) assert.strictEqual(L.decide({ cookie: "", country: c }).lang, l, c);
});
test("unknown country gives English", () => {
  for (const c of ["US", "DE", "GB", "XX"]) assert.strictEqual(L.decide({ cookie: "", country: c }).lang, "en", c);
  assert.deepStrictEqual(L.decide({ cookie: "", country: null, languages: ["sv-SE"] }), { lang: "en", why: "geo-unknown" });
});
test("navigator fallback when geo is unavailable", () => {
  assert.deepStrictEqual(L.decide({ cookie: "", languages: ["nb-NO", "en"] }), { lang: "nn", why: "navigator" });
  assert.strictEqual(L.decide({ cookie: "", languages: ["no"] }).lang, "nn");
  assert.strictEqual(L.decide({ cookie: "", languages: ["nn-NO"] }).lang, "nn");
  assert.strictEqual(L.decide({ cookie: "", languages: ["de-DE", "da-DK"] }).lang, "da");
  assert.strictEqual(L.decide({ cookie: "", languages: ["fi_FI"] }).lang, "fi");
  assert.strictEqual(L.decide({ cookie: "", languages: ["de", "fr"] }).lang, "en");
  assert.strictEqual(L.decide({ cookie: "", languages: [] }).lang, "en");
});
test("no second automatic redirect in the same tab", () => {
  assert.deepStrictEqual(L.decide({ cookie: "", autoDone: true, country: "NO" }), { lang: "en", why: "auto-done" });
  assert.strictEqual(L.decide({ cookie: "nc_lang=sv", autoDone: true }).lang, "sv");
});
