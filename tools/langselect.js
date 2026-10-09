/* Nordic Crypto language auto-selection. Inlined (by build.py) ONLY in the <head> of the English home page (site root).
   The LANGS placeholder below is replaced with the site language codes from i18n.LANGS.

   The country map below is a default guess from the visitor's IP country. It is not a profile and nothing is stored.
   An explicit choice always wins.

   Order:
   1) nc_lang cookie, set only when the visitor clicks a language in the switcher (also copied to localStorage
      under the same name). The cookie wins when both are set. If the cookie is missing, localStorage nc_lang is
      the same override.
   2) first visit with no choice: the country from our own Worker (GET the GEO placeholder -> {"country":"NO"}). That URL is
      the tipworker /api/geo, which returns Cloudflare's request.cf.country. Nothing is stored or logged, and no
      third-party geo-IP service is used. A country that is not in BY_COUNTRY (and a null country) means English.
   3) the Worker is not deployed / unreachable (1.5 s timeout): the browser's navigator.languages
   4) otherwise English.

   It only ever redirects from the home page at the root; direct links to /nn/, /de/, ... and to any other page are never
   redirected. After one automatic choice a sessionStorage flag (nc_auto) stops it from redirecting again in that tab.
   Norwegian browser tags (no, nb, nn) default to nynorsk; bokmål is the quick link beside the switcher.
   India defaults to Hindi. Marathi (mr) has no country row. Mauritania's country code MR defaults to Arabic (ar);
   the language code mr is Marathi. */
(function (root) {
  var LANGS = __LANGS__;
  /* Country (ISO 3166-1 alpha-2) -> site language. Unknown countries fall through to English in fromCountry.
     The public API reads this object (tools/api_feed.py). Keep entries as XX: "yy" with a two-letter code. */
  var BY_COUNTRY = {
    /* Nordic, kept: Norway and Svalbard nynorsk; Sweden and Åland Swedish; Denmark, Faroe, Greenland Danish; Finland; Iceland. */
    NO: "nn", SJ: "nn", SE: "sv", AX: "sv", DK: "da", FO: "da", GL: "da", FI: "fi", IS: "is",
    /* Mandarin. Singapore is multilingual; zh is the guess the site uses. */
    CN: "zh", TW: "zh", HK: "zh", MO: "zh", SG: "zh",
    /* Hindi. Marathi is a site language with no country row, so India stays Hindi. */
    IN: "hi",
    /* Spanish. */
    ES: "es", MX: "es", AR: "es", CO: "es", CL: "es", PE: "es", VE: "es", EC: "es", GT: "es", CU: "es",
    BO: "es", DO: "es", HN: "es", PY: "es", SV: "es", NI: "es", CR: "es", PA: "es", UY: "es", PR: "es", GQ: "es",
    /* French. Belgium, Canada and Luxembourg stay unmapped: a known country code there stays English. */
    FR: "fr", MC: "fr", SN: "fr", CI: "fr", CM: "fr", CD: "fr", MG: "fr", ML: "fr", NE: "fr", BF: "fr",
    TG: "fr", BJ: "fr", GA: "fr", CG: "fr", GN: "fr", TD: "fr", CF: "fr", HT: "fr",
    /* Arabic. MR is Mauritania, not Marathi. */
    SA: "ar", EG: "ar", AE: "ar", QA: "ar", KW: "ar", BH: "ar", OM: "ar", JO: "ar", LB: "ar", SY: "ar",
    IQ: "ar", YE: "ar", LY: "ar", TN: "ar", DZ: "ar", MA: "ar", SD: "ar", PS: "ar", MR: "ar",
    /* Bengali, Portuguese, Russian, Urdu, Indonesian, German, Japanese, Swahili, Persian (Iran, and Afghanistan for Dari), Ukrainian. */
    BD: "bn",
    BR: "pt", PT: "pt", AO: "pt", MZ: "pt", CV: "pt", GW: "pt", ST: "pt", TL: "pt",
    RU: "ru", BY: "ru",
    PK: "ur",
    ID: "id",
    DE: "de", AT: "de", CH: "de", LI: "de",
    JP: "ja",
    KE: "sw", TZ: "sw", UG: "sw",
    IR: "fa", AF: "fa",
    UA: "uk"
  };
  function fromCountry(c) { return BY_COUNTRY[String(c || "").toUpperCase()] || "en"; }
  function fromLanguages(list) {
    for (var i = 0; i < (list || []).length; i++) {
      var p = String(list[i] || "").toLowerCase().split(/[-_]/)[0];
      if (p === "nn" || p === "nb" || p === "no") return "nn";
      if (LANGS.indexOf(p) >= 0) return p;
    }
    return "en";
  }
  function choice(code) {
    return code && LANGS.indexOf(code) >= 0 ? code : null;
  }
  function cookieLang(cookie) {
    var m = String(cookie || "").match(/(?:^|;\s*)nc_lang=([a-z]{2})(?:;|$)/);
    return m ? choice(m[1]) : null;
  }
  function storedLang(v) {
    return choice(String(v || "").toLowerCase());
  }
  /* Pure decision (unit-tested): o = {cookie, stored, autoDone, country (string|null|undefined = no geo answer), languages} */
  function decide(o) {
    o = o || {};
    var c = cookieLang(o.cookie);
    if (c) return { lang: c, why: "cookie" };
    var s = storedLang(o.stored);
    if (s) return { lang: s, why: "storage" };
    if (o.autoDone) return { lang: "en", why: "auto-done" };
    if (typeof o.country === "string") return { lang: fromCountry(o.country), why: "geo" };
    if (o.country === null) return { lang: "en", why: "geo-unknown" };
    return { lang: fromLanguages(o.languages), why: "navigator" };
  }
  var api = { decide: decide, fromCountry: fromCountry, fromLanguages: fromLanguages, cookieLang: cookieLang, storedLang: storedLang, BY_COUNTRY: BY_COUNTRY, LANGS: LANGS };
  if (typeof module !== "undefined" && module.exports) { module.exports = api; return; }
  root.ncLang = api;
  var GEO = __GEO__, d = document, h = d.documentElement;
  function ss(k, v) { try { if (v === undefined) return sessionStorage.getItem(k); sessionStorage.setItem(k, v); } catch (e) { return null; } }
  function ls(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function go(r) {
    h.className = h.className.replace(/\bnc-pick\b/, "");
    if (r.why !== "cookie" && r.why !== "storage" && r.why !== "auto-done") ss("nc_auto", "1");
    if (r.lang !== "en") location.replace(location.pathname.replace(/index\.html$/, "") + r.lang + "/" + location.hash);
  }
  var base = { cookie: d.cookie, stored: ls("nc_lang"), autoDone: ss("nc_auto") === "1", languages: navigator.languages || [navigator.language] };
  var first = decide(base);
  if (first.why === "cookie" || first.why === "storage" || first.why === "auto-done" || !GEO || !root.fetch) return go(first);
  h.className += " nc-pick";                       /* hide the English page for at most 1.5 s while we ask */
  var done = false, ac = root.AbortController ? new AbortController() : null;
  function fin(country) { if (done) return; done = true; base.country = country; go(decide(base)); }
  var timer = setTimeout(function () { if (ac) ac.abort(); fin(undefined); }, 1500);
  fetch(GEO, { cache: "no-store", credentials: "omit", referrerPolicy: "no-referrer", signal: ac ? ac.signal : undefined })
    .then(function (r) { return r.ok ? r.json() : Promise.reject(); })
    .then(function (j) { clearTimeout(timer); fin(j && typeof j.country === "string" && /^[A-Z]{2}$/.test(j.country) ? j.country : null); })
    .catch(function () { clearTimeout(timer); fin(undefined); });
})(this);
