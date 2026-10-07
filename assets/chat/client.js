/* Nordic Crypto shoutbox. One room: every language page reads and writes the same stream.
   The page language is sent only as a tag. Messages are plain text: textContent escapes
   HTML, and URLs are not turned into links (no user-content anchor, so no rel=nofollow ugc).
   The nickname is kept in localStorage. This file does not set a cookie. */
(function () {
  var cfg = window.NC_SHOUT;
  if (!cfg || !cfg.endpoint) return;
  var root = document.querySelector(".shoutbox");
  if (!root) return;
  var S = cfg.strings || {};
  var list = root.querySelector(".shout-list");
  var empty = root.querySelector(".shout-empty");
  var form = root.querySelector(".shout-form");
  var status = root.querySelector(".shout-status");
  var older = root.querySelector(".shout-older");
  var toggle = root.querySelector(".shout-toggle");
  var nick = form.querySelector('input[name="nickname"]');
  var msg = form.querySelector('textarea[name="message"]');
  var seen = Object.create(null);
  var token = "";
  var wid = "";
  var NICK_KEY = "nc_shout_nick";

  try { nick.value = localStorage.getItem(NICK_KEY) || ""; } catch (e) {}
  nick.addEventListener("input", function () {
    try { localStorage.setItem(NICK_KEY, nick.value); } catch (e) {}
  });

  if (toggle) {
    toggle.addEventListener("click", function () {
      var open = root.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      toggle.textContent = open ? (S.toggle_hide || "") : (S.toggle_show || "");
    });
  }

  function say(key) { if (status) status.textContent = S[key] || S.fail || ""; }

  function rel(iso) {
    var t = Date.parse(iso);
    if (!t) return "";
    var sec = Math.max(0, (Date.now() - t) / 1000);
    if (sec < 45) return S.time_now || "";
    if (sec < 3600) return (S.time_m || "").replace("{n}", String(Math.max(1, Math.round(sec / 60))));
    if (sec < 86400) return (S.time_h || "").replace("{n}", String(Math.max(1, Math.round(sec / 3600))));
    return (S.time_d || "").replace("{n}", String(Math.max(1, Math.round(sec / 86400))));
  }

  function tick() {
    var nodes = list.querySelectorAll("time");
    for (var i = 0; i < nodes.length; i++) nodes[i].textContent = rel(nodes[i].dateTime);
  }

  function rowEl(row) {
    var li = document.createElement("li");
    li.className = "shout-item";
    li.setAttribute("data-id", String(row.id));
    var meta = document.createElement("div");
    meta.className = "shout-meta";
    var name = document.createElement("span");
    name.className = "shout-nick";
    name.textContent = row.nickname || "";
    var time = document.createElement("time");
    time.dateTime = row.created_at || "";
    time.textContent = rel(row.created_at);
    meta.appendChild(name);
    meta.appendChild(time);
    if (row.lang && cfg.langNames && cfg.langNames[row.lang]) {
      var tag = document.createElement("span");
      tag.className = "shout-lang";
      tag.lang = row.lang;
      tag.textContent = cfg.langNames[row.lang];
      meta.appendChild(tag);
    }
    var text = document.createElement("p");
    text.className = "shout-msg";
    text.textContent = row.message || "";
    var report = document.createElement("button");
    report.type = "button";
    report.className = "shout-report";
    report.textContent = S.report || "";
    report.addEventListener("click", function () { sendReport(row.id, report); });
    li.appendChild(meta);
    li.appendChild(text);
    li.appendChild(report);
    return li;
  }

  function remember(rows) {
    for (var i = 0; i < rows.length; i++) {
      var row = rows[i];
      if (!row || seen[row.id]) continue;
      seen[row.id] = 1;
      list.appendChild(rowEl(row));
    }
    var items = [].slice.call(list.children);
    items.sort(function (a, b) { return Number(a.getAttribute("data-id")) - Number(b.getAttribute("data-id")); });
    for (var j = 0; j < items.length; j++) list.appendChild(items[j]);
    if (empty) empty.hidden = list.children.length > 0;
    tick();
  }

  function dropMissing(rows) {
    if (!rows.length) return;
    var ids = Object.create(null);
    var min = 0;
    for (var i = 0; i < rows.length; i++) {
      ids[rows[i].id] = 1;
      if (!min || rows[i].id < min) min = rows[i].id;
    }
    [].slice.call(list.children).forEach(function (li) {
      var id = Number(li.getAttribute("data-id"));
      if (id >= min && !ids[id]) {
        li.remove();
        delete seen[id];
      }
    });
  }

  function endpoint(path) { return String(cfg.endpoint).replace(/\/$/, "") + path; }

  function refresh() {
    // Latest window only. No lang, room or channel query: one shared stream.
    return fetch(endpoint("/api/shouts?limit=50"), { headers: { Accept: "application/json" } })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var rows = (data && data.shouts) || [];
        dropMissing(rows);
        remember(rows);
        if (older && !older.dataset.done) older.hidden = rows.length < 50;
      })
      .catch(function () {});
  }

  function loadOlder() {
    var first = list.firstElementChild;
    if (!first) return;
    var before = first.getAttribute("data-id");
    fetch(endpoint("/api/shouts?limit=50&before=" + encodeURIComponent(before)), { headers: { Accept: "application/json" } })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var rows = (data && data.shouts) || [];
        remember(rows);
        if (older && rows.length < 50) { older.hidden = true; older.dataset.done = "1"; }
      })
      .catch(function () {});
  }

  function sendReport(id, button) {
    button.disabled = true;
    fetch(endpoint("/api/shouts/report"), {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ id: id })
    }).then(function (r) {
      if (!r.ok) { button.disabled = false; return; }
      button.textContent = S.reported || "";
    }).catch(function () { button.disabled = false; });
  }

  function bootTurnstile() {
    if (!cfg.turnstileSiteKey) return;
    var el = root.querySelector(".shout-turnstile");
    if (!el) return;
    if (!window.turnstile) { setTimeout(bootTurnstile, 300); return; }
    wid = window.turnstile.render(el, {
      sitekey: cfg.turnstileSiteKey,
      callback: function (tok) { token = tok || ""; },
      "expired-callback": function () { token = ""; },
      "error-callback": function () { token = ""; }
    });
  }

  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    if (cfg.turnstileSiteKey && !token) { say("turnstile"); return; }
    var honey = form.querySelector('input[name="website"]');
    var body = {
      nickname: nick.value,
      message: msg.value,
      lang: cfg.lang || "",
      website: honey ? honey.value : ""
    };
    if (cfg.turnstileSiteKey) body["cf-turnstile-response"] = token;
    say("sending");
    var submit = form.querySelector('button[type="submit"]');
    submit.disabled = true;
    fetch(endpoint("/api/shouts"), {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body)
    }).then(function (r) {
      return r.json().then(function (j) { return { ok: r.ok, status: r.status, j: j || {} }; });
    }).then(function (res) {
      submit.disabled = false;
      if (res.status === 429 || (res.j && res.j.error === "rate")) { say("rate"); return; }
      var err = res.j && res.j.error;
      if (err === "spam") { say("spam"); return; }
      if (err === "turnstile") { say("turnstile"); return; }
      if (err === "nickname") { say("nick_err"); return; }
      if (err === "message") { say("msg_err"); return; }
      if (err === "banned") { say("banned"); return; }
      if (!res.ok) { say("fail"); return; }
      say("sent");
      msg.value = "";
      token = "";
      if (window.turnstile && wid) window.turnstile.reset(wid);
      refresh();
    }).catch(function () { submit.disabled = false; say("fail"); });
  });

  if (older) older.addEventListener("click", loadOlder);
  bootTurnstile();
  refresh();
  setInterval(function () {
    if (document.hidden) return;
    refresh();
  }, cfg.pollMs || 15000);
})();
