/* Nordic Crypto language auto-selection. Inlined (by build.py) ONLY in the <head> of the English home page (site root).
   Order: 1) an explicit choice in the first-party cookie nc_lang (set when the visitor clicks a language in the switcher)
          2) first visit with no choice: the country from our own Worker (GET __GEO__ -> {"country":"NO"}), Cloudflare's
             request.cf.country; nothing is stored or logged; no third-party geo-IP service
          3) the Worker is not deployed / unreachable (1.5 s timeout): the browser's navigator.languages
          4) otherwise English.
   It only ever redirects from the home page at the root; direct links to /nn/, /nb/, ... and to any other page are never
   redirected. After one automatic choice a sessionStorage flag (nc_auto) stops it from redirecting again in that tab. */
(function (root) {
  var LANGS = __LANGS__;
  var BY_COUNTRY = { NO: "nn", SE: "sv", DK: "da", FI: "fi", IS: "is", AX: "sv", FO: "da", GL: "da" };
  function fromCountry(c) { return BY_COUNTRY[String(c || "").toUpperCase()] || "en"; }
  function fromLanguages(list) {
    for (var i = 0; i < (list || []).length; i++) {
      var p = String(list[i] || "").toLowerCase().split(/[-_]/)[0];
      if (p === "nn" || p === "nb" || p === "no") return "nn";
      if (p === "en" || p === "sv" || p === "da" || p === "fi" || p === "is") return p;
    }
    return "en";
  }
  function cookieLang(cookie) {
    var m = String(cookie || "").match(/(?:^|;\s*)nc_lang=([a-z]{2})(?:;|$)/);
    return m && LANGS.indexOf(m[1]) >= 0 ? m[1] : null;
  }
  /* Pure decision (unit-tested): o = {cookie, autoDone, country (string|null|undefined = no geo answer), languages} */
  function decide(o) {
    var c = cookieLang(o.cookie);
    if (c) return { lang: c, why: "cookie" };
    if (o.autoDone) return { lang: "en", why: "auto-done" };
    if (typeof o.country === "string") return { lang: fromCountry(o.country), why: "geo" };
    if (o.country === null) return { lang: "en", why: "geo-unknown" };
    return { lang: fromLanguages(o.languages), why: "navigator" };
  }
  var api = { decide: decide, fromCountry: fromCountry, fromLanguages: fromLanguages, cookieLang: cookieLang };
  if (typeof module !== "undefined" && module.exports) { module.exports = api; return; }
  root.ncLang = api;
  var GEO = __GEO__, d = document, h = d.documentElement;
  function ss(k, v) { try { if (v === undefined) return sessionStorage.getItem(k); sessionStorage.setItem(k, v); } catch (e) { return null; } }
  function go(r) {
    h.className = h.className.replace(/\bnc-pick\b/, "");
    if (r.why !== "cookie" && r.why !== "auto-done") ss("nc_auto", "1");
    if (r.lang !== "en") location.replace(location.pathname.replace(/index\.html$/, "") + r.lang + "/" + location.hash);
  }
  var base = { cookie: d.cookie, autoDone: ss("nc_auto") === "1", languages: navigator.languages || [navigator.language] };
  var first = decide(base);
  if (first.why === "cookie" || first.why === "auto-done" || !GEO || !root.fetch) return go(first);
  h.className += " nc-pick";                       /* hide the English page for at most 1.5 s while we ask */
  var done = false, ac = root.AbortController ? new AbortController() : null;
  function fin(country) { if (done) return; done = true; base.country = country; go(decide(base)); }
  var timer = setTimeout(function () { if (ac) ac.abort(); fin(undefined); }, 1500);
  fetch(GEO, { cache: "no-store", credentials: "omit", referrerPolicy: "no-referrer", signal: ac ? ac.signal : undefined })
    .then(function (r) { return r.ok ? r.json() : Promise.reject(); })
    .then(function (j) { clearTimeout(timer); fin(j && typeof j.country === "string" && /^[A-Z]{2}$/.test(j.country) ? j.country : null); })
    .catch(function () { clearTimeout(timer); fin(undefined); });
})(this);
