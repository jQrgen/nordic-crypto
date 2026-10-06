(function () {
  const cfg = window.NCK_CONFIG || {};
  const API_BASE = cfg.apiBase || "https://raw.githubusercontent.com/jQrgen/nordic-crypto/gh-pages";
  const NEWS_PATH = cfg.newsPath || "/api/v1/news.json";
  const NEWS_REFRESH_SEC = Number(cfg.newsRefreshSec || 900);
  const SLIDE_SEC = Number(cfg.slideSec || 22);
  const LANG = (cfg.lang || "en").toLowerCase();
  const MAX_ITEMS = Number(cfg.maxItems || 24);

  const el = {
    clock: document.getElementById("clock"),
    updated: document.getElementById("updated"),
    title: document.getElementById("title"),
    summary: document.getElementById("summary"),
    source: document.getElementById("source"),
    country: document.getElementById("country"),
    topics: document.getElementById("topics"),
    status: document.getElementById("status"),
    dots: document.getElementById("dots"),
    panel: document.getElementById("panel"),
  };

  let items = [];
  let idx = 0;
  let slideTimer = null;

  function pad(n) { return String(n).padStart(2, "0"); }

  function tickClock() {
    const d = new Date();
    el.clock.textContent =
      pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds());
  }

  function pickSummary(it) {
    if (LANG !== "en" && it.summary_i18n && it.summary_i18n[LANG]) {
      return it.summary_i18n[LANG];
    }
    return it.summary || it.title_en || it.title || "";
  }

  function pickTitle(it) {
    if (LANG === "en" && it.title_en) return it.title_en;
    if (LANG !== "en" && it.title_i18n && it.title_i18n[LANG]) return it.title_i18n[LANG];
    return it.title || it.title_en || "";
  }

  function renderDots() {
    el.dots.innerHTML = "";
    const n = Math.min(items.length, 12);
    for (let i = 0; i < n; i++) {
      const d = document.createElement("span");
      d.className = "dot" + (i === (idx % n) ? " on" : "");
      el.dots.appendChild(d);
    }
  }

  function show(i) {
    if (!items.length) return;
    idx = ((i % items.length) + items.length) % items.length;
    const it = items[idx];
    el.panel.classList.remove("fade");
    void el.panel.offsetWidth;
    el.panel.classList.add("fade");
    el.title.textContent = pickTitle(it);
    el.summary.textContent = pickSummary(it);
    el.source.textContent = it.source_name || it.source || "—";
    el.country.textContent = (it.country || "?").toUpperCase();
    const topics = (it.topics || []).slice(0, 4).join(" · ");
    el.topics.textContent = topics || "news";
    renderDots();
  }

  function next() { show(idx + 1); }

  function startSlider() {
    if (slideTimer) clearInterval(slideTimer);
    slideTimer = setInterval(next, SLIDE_SEC * 1000);
  }

  async function loadNews() {
    el.status.textContent = "Updating…";
    el.status.className = "status";
    try {
      const url = API_BASE.replace(/\/$/, "") + NEWS_PATH + "?t=" + Date.now();
      const res = await fetch(url, { cache: "no-store" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      const list = Array.isArray(data.items) ? data.items : [];
      items = list.slice(0, MAX_ITEMS);
      if (!items.length) throw new Error("No news items");
      const gen = data.generated_at || data.updated || "";
      el.updated.textContent = gen
        ? "Feed " + new Date(gen).toLocaleString()
        : "Feed ok";
      el.status.textContent = items.length + " stories";
      show(0);
      startSlider();
    } catch (e) {
      el.status.textContent = "Offline / error: " + (e.message || e);
      el.status.className = "status err";
    }
  }

  tickClock();
  setInterval(tickClock, 1000);
  loadNews();
  setInterval(loadNews, NEWS_REFRESH_SEC * 1000);

  document.addEventListener("keydown", (ev) => {
    if (ev.key === "ArrowRight" || ev.key === " ") next();
    if (ev.key === "ArrowLeft") show(idx - 1);
    if (ev.key === "r" || ev.key === "R") loadNews();
  });
})();
