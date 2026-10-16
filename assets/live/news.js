// Live news from the Nordic Crypto content Worker (Cloudflare D1), with the static
// api/v1/news.json on this site as the fallback. Read-only, public, no credentials.
// window.NC_LIVE = {api: "https://api.nordiccrypto.no", root: "../", lang: "no"}  (api empty: static only)
(function () {
  "use strict";
  var cfg = window.NC_LIVE || {};
  var grid = document.querySelector(".storygrid");
  if (!grid || !window.fetch) return;
  function get(url, ms) {
    var ctl = window.AbortController ? new AbortController() : null;
    var timer = ctl && setTimeout(function () { ctl.abort(); }, ms);
    return fetch(url, { signal: ctl && ctl.signal, credentials: "omit" }).then(function (r) {
      if (timer) clearTimeout(timer);
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    });
  }
  function load() {
    var live = cfg.api ? get(cfg.api.replace(/\/$/, "") + "/api/v1/news.json", 4000) : Promise.reject(new Error("no api"));
    return live.catch(function () { return get((cfg.root || "") + "api/v1/news.json?t=" + Date.now(), 6000); });
  }
  function seen() {
    var ids = {};
    document.querySelectorAll('a[href*="stories/"]').forEach(function (a) {
      var m = a.getAttribute("href").match(/stories\/([A-Za-z0-9]+)/);
      if (m) ids[m[1]] = true;
    });
    return ids;
  }
  function card(s) {
    var art = document.createElement("article");
    art.className = "storycard live";
    var h = document.createElement("h3");
    var a = document.createElement("a");
    a.href = "stories/" + s.id + "/";
    a.textContent = (cfg.lang !== "no" && s.title_en) || s.title || "";
    h.appendChild(a);
    art.appendChild(h);
    if (s.summary) {
      var p = document.createElement("p");
      p.className = "sum";
      p.textContent = s.summary;
      art.appendChild(p);
    }
    return art;
  }
  load().then(function (doc) {
    var have = seen();

    var fresh = (doc.items || []).filter(function (s) {
      return s && s.status === "published" && s.id && !have[s.id];
    }).sort(function (x, y) { return String(y.published).localeCompare(String(x.published)); });
    fresh.slice(0, 12).reverse().forEach(function (s) { grid.insertBefore(card(s), grid.firstChild); });

  }).catch(function () { /* keep the static page as built */ });
})();
