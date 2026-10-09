// Unit tests for tools/langselect.js decide(). Run: node --test tests/*.test.js  (Node >= 18)
const test = require("node:test"), assert = require("node:assert"), fs = require("fs"), path = require("path"), Module = require("module");
const { execFileSync } = require("child_process");
const root = path.join(__dirname, "..");
const langs = JSON.parse(execFileSync("python3", ["-c", "import json,i18n; print(json.dumps(i18n.ALL_LANGS))"], { cwd: root, encoding: "utf8" }));
const NEED = ["en", "nn", "nb", "sv", "da", "fi", "is", "zh", "hi", "es", "fr", "ar", "bn", "pt", "ru", "ur", "id", "de", "ja", "sw", "mr", "fa"];
const src = fs.readFileSync(path.join(root, "tools", "langselect.js"), "utf8")
  .replace("__LANGS__", JSON.stringify(langs)).replace("__GEO__", JSON.stringify("https://geo.example/api/geo"));
const m = new Module("langselect"); m._compile(src, "langselect.js"); const L = m.exports;
test("site languages cover Nordic and the wider spoken set", () => {
  assert.deepStrictEqual(langs.slice().sort(), NEED.slice().sort());
});
test("cookie wins over geo, storage and navigator", () => {
  assert.deepStrictEqual(L.decide({ cookie: "nc_lang=nb", country: "SE", languages: ["fi"], stored: "ja" }), { lang: "nb", why: "cookie" });
  assert.strictEqual(L.decide({ cookie: "a=1; nc_lang=en; b=2", country: "NO" }).lang, "en");
  assert.strictEqual(L.decide({ cookie: "nc_lang=de", country: "DK" }).lang, "de");
  assert.strictEqual(L.decide({ cookie: "nc_lang=zh", country: "NO", stored: "ja" }).lang, "zh");
});
test("invalid cookie is ignored", () => {
  assert.strictEqual(L.decide({ cookie: "nc_lang=nl", country: "DK" }).lang, "da");
  assert.strictEqual(L.decide({ cookie: "nc_lang=nbx", country: "DK" }).why, "geo");
  assert.strictEqual(L.decide({ cookie: "xnc_lang=sv", country: "FI" }).lang, "fi");
});
test("stored switcher choice is used only when the cookie is missing", () => {
  assert.deepStrictEqual(L.decide({ cookie: "", stored: "ja", country: "NO" }), { lang: "ja", why: "storage" });
  assert.strictEqual(L.decide({ cookie: "nc_lang=sv", stored: "ja", country: "NO" }).why, "cookie");
  assert.strictEqual(L.decide({ cookie: "", stored: "nl", country: "JP" }).lang, "ja");
  assert.strictEqual(L.decide({ cookie: "", stored: "zh", autoDone: true }).lang, "zh");
});
test("country map, Nordic kept and new languages added", () => {
  const exp = {
    NO: "nn", SE: "sv", DK: "da", FI: "fi", IS: "is", AX: "sv", FO: "da", GL: "da", SJ: "nn", no: "nn",
    CN: "zh", TW: "zh", SG: "zh", IN: "hi", ES: "es", MX: "es", AR: "es", FR: "fr",
    SA: "ar", EG: "ar", AE: "ar", BD: "bn", BR: "pt", PT: "pt", RU: "ru", PK: "ur",
    ID: "id", DE: "de", AT: "de", CH: "de", JP: "ja", KE: "sw", TZ: "sw", MR: "ar",
    IR: "fa", AF: "fa",
  };
  for (const [c, l] of Object.entries(exp)) assert.strictEqual(L.decide({ cookie: "", country: c }).lang, l, c);
  for (const [c, l] of Object.entries(L.BY_COUNTRY)) assert.ok(langs.includes(l), c + " -> " + l);
});
test("unknown country gives English", () => {
  for (const c of ["US", "GB", "XX", "AU", "CA", "BE"]) assert.strictEqual(L.decide({ cookie: "", country: c }).lang, "en", c);
  assert.deepStrictEqual(L.decide({ cookie: "", country: null, languages: ["sv-SE"] }), { lang: "en", why: "geo-unknown" });
});
test("navigator fallback when geo is unavailable", () => {
  assert.deepStrictEqual(L.decide({ cookie: "", languages: ["nb-NO", "en"] }), { lang: "nn", why: "navigator" });
  assert.strictEqual(L.decide({ cookie: "", languages: ["no"] }).lang, "nn");
  assert.strictEqual(L.decide({ cookie: "", languages: ["nn-NO"] }).lang, "nn");
  assert.strictEqual(L.decide({ cookie: "", languages: ["de-DE", "da-DK"] }).lang, "de");
  assert.strictEqual(L.decide({ cookie: "", languages: ["nl", "da-DK"] }).lang, "da");
  assert.strictEqual(L.decide({ cookie: "", languages: ["fi_FI"] }).lang, "fi");
  assert.strictEqual(L.decide({ cookie: "", languages: ["zh-CN", "en"] }).lang, "zh");
  assert.strictEqual(L.decide({ cookie: "", languages: ["mr-IN"] }).lang, "mr");
  assert.strictEqual(L.decide({ cookie: "", languages: ["nl", "xx"] }).lang, "en");
  assert.strictEqual(L.decide({ cookie: "", languages: [] }).lang, "en");
});
test("no second automatic redirect in the same tab", () => {
  assert.deepStrictEqual(L.decide({ cookie: "", autoDone: true, country: "NO" }), { lang: "en", why: "auto-done" });
  assert.strictEqual(L.decide({ cookie: "nc_lang=sv", autoDone: true }).lang, "sv");
});
