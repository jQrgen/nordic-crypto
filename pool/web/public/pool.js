(function () {
  var text = window.POOL_TEXT || {};
  var msg = document.getElementById("status-msg");
  var figures = document.getElementById("figures");
  var live = document.getElementById("live-line");
  var since = document.getElementById("since");
  var list = document.getElementById("blocks");

  function fill(template, map) {
    return String(template || "").replace(/\{(\w+)\}/g, function (_, key) {
      return map[key] == null ? "" : String(map[key]);
    });
  }

  function rate(n) {
    if (typeof n !== "number" || !isFinite(n)) return "";
    var units = ["H/s", "KH/s", "MH/s", "GH/s", "TH/s", "PH/s", "EH/s"];
    var i = 0;
    var v = n;
    while (v >= 1000 && i < units.length - 1) {
      v /= 1000;
      i++;
    }
    var digits = v >= 100 || v === 0 ? 0 : 2;
    return v.toFixed(digits) + " " + units[i];
  }

  function share(n) {
    if (typeof n !== "number" || !isFinite(n)) return "";
    var pct = n * 100;
    if (pct > 0 && pct < 0.0001) return "< 0.0001%";
    return pct.toFixed(4) + "%";
  }

  function ago(iso) {
    var ms = Date.now() - Date.parse(iso);
    if (!isFinite(ms) || ms < 0) ms = 0;
    var s = Math.floor(ms / 1000);
    var d = Math.floor(s / 86400);
    var h = Math.floor((s % 86400) / 3600);
    var m = Math.floor((s % 3600) / 60);
    if (d > 0) return d + "d " + h + "h";
    if (h > 0) return h + "h " + m + "m";
    return m + "m " + (s % 60) + "s";
  }

  function statusWord(status) {
    if (status === "mature") return text.statusMature || status;
    if (status === "orphan") return text.statusOrphan || status;
    if (status === "immature") return text.statusImmature || status;
    return status || "";
  }

  function showDown() {
    if (msg) msg.textContent = text.apiDown || "The pool API is not responding.";
    if (figures) figures.hidden = true;
    if (live) live.textContent = "";
    if (since) since.textContent = "";
    if (list) list.replaceChildren();
  }

  function renderBlocks(blocks) {
    if (!list) return;
    list.replaceChildren();
    if (!blocks || !blocks.length) {
      var empty = document.createElement("li");
      empty.textContent = text.emptyBlocks || "";
      list.appendChild(empty);
      return;
    }
    blocks.forEach(function (block) {
      var li = document.createElement("li");
      if (block.url) {
        var a = document.createElement("a");
        a.href = block.url;
        a.rel = "noopener";
        a.textContent = fill(text.blockLink || "block {height}", {height: block.height});
        li.appendChild(a);
      }
      var rest = document.createElement("span");
      rest.textContent = " · " + statusWord(block.status) + " · " + (block.found_at || "");
      li.appendChild(rest);
      list.appendChild(li);
    });
  }

  function show(stats, blocks) {
    if (!stats || typeof stats.node_online !== "boolean") {
      showDown();
      return;
    }
    if (!stats.node_online) {
      if (msg) msg.textContent = text.nodeDown || "";
      if (figures) figures.hidden = true;
    } else {
      if (msg) msg.textContent = "";
      if (figures) figures.hidden = false;
      document.getElementById("pool-hash").textContent = rate(stats.pool_hashrate);
      document.getElementById("miner-count").textContent = String(stats.miners);
      document.getElementById("net-hash").textContent = rate(stats.network_hashrate);
      document.getElementById("pool-share").textContent = share(stats.pool_share);
    }
    if (live && stats.fee_percent != null && stats.min_payout) {
      live.textContent = fill(text.liveLine, {fee: stats.fee_percent, min: stats.min_payout});
    }
    if (since) {
      since.textContent = stats.last_block
        ? (text.since || "") + " " + ago(stats.last_block.found_at)
        : (text.noBlock || "");
    }
    renderBlocks(blocks);
  }

  function okJson(response) {
    if (!response.ok) throw new Error("status");
    return response.json();
  }

  if (msg) msg.textContent = text.loading || "";
  Promise.all([
    fetch("/api/v1/stats").then(okJson),
    fetch("/api/v1/blocks").then(okJson)
  ]).then(function (parts) {
    show(parts[0], parts[1]);
  }).catch(showDown);

  var copy = document.getElementById("copy");
  if (copy) {
    copy.addEventListener("click", function () {
      var url = document.getElementById("stratum").textContent;
      var done = function () {
        copy.textContent = text.copied || copy.textContent;
        setTimeout(function () { copy.textContent = text.copy || "Copy"; }, 1500);
      };
      var fallback = function () {
        var area = document.createElement("textarea");
        area.value = url;
        area.setAttribute("readonly", "");
        document.body.appendChild(area);
        area.select();
        document.execCommand("copy");
        area.remove();
        done();
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(done).catch(fallback);
      } else {
        fallback();
      }
    });
  }

  function payoutList(rows) {
    var ul = document.createElement("ul");
    ul.id = "payouts";
    if (!rows || !rows.length) {
      var li = document.createElement("li");
      li.textContent = text.statsNoPay || "";
      ul.appendChild(li);
      return ul;
    }
    rows.forEach(function (row) {
      var li = document.createElement("li");
      li.textContent = row.amount + " NEX · " + statusWord(row.status) + (row.txid ? " · " + row.txid : "");
      ul.appendChild(li);
    });
    return ul;
  }

  function renderMine(body) {
    var host = document.getElementById("mine");
    host.replaceChildren();
    var quiet = body.valid_shares === 0 && body.invalid_shares === 0 &&
      body.balance === "0.00" && body.immature === "0.00" && body.paid === "0.00" &&
      (!body.payouts || body.payouts.length === 0);
    if (quiet) {
      var p = document.createElement("p");
      p.className = "notice";
      p.textContent = text.statsEmpty || "";
      host.appendChild(p);
      return;
    }
    var dl = document.createElement("dl");
    dl.className = "figures";
    function row(label, value) {
      var wrap = document.createElement("div");
      var dt = document.createElement("dt");
      dt.textContent = label;
      var dd = document.createElement("dd");
      dd.textContent = value;
      wrap.appendChild(dt);
      wrap.appendChild(dd);
      dl.appendChild(wrap);
    }
    row(text.statsHash, rate(body.hashrate));
    row(text.statsShares, String(body.valid_shares) + " " + (text.valid || "") + " · " + String(body.invalid_shares) + " " + (text.invalid || ""));
    row(text.statsBalance, body.balance + " NEX");
    row(text.statsImmature, body.immature + " NEX");
    row(text.statsPaid, body.paid + " NEX");
    host.appendChild(dl);
    var h = document.createElement("h3");
    h.textContent = text.statsPayouts || "";
    host.appendChild(h);
    host.appendChild(payoutList(body.payouts));
  }

  function lookup(address) {
    var host = document.getElementById("mine");
    host.replaceChildren();
    fetch("/api/v1/address/" + encodeURIComponent(address)).then(function (response) {
      if (response.status === 400) {
        var bad = document.createElement("p");
        bad.className = "notice";
        bad.textContent = text.statsBad || "";
        host.appendChild(bad);
        return null;
      }
      if (!response.ok) throw new Error("status");
      return response.json();
    }).then(function (body) {
      if (body) renderMine(body);
    }).catch(function () {
      var p = document.createElement("p");
      p.className = "notice";
      p.textContent = text.apiDown || "The pool API is not responding.";
      host.appendChild(p);
    });
  }

  var form = document.getElementById("lookup");
  if (form) {
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var address = document.getElementById("addr").value.trim();
      if (!address) return;
      var url = new URL(window.location.href);
      url.searchParams.set("address", address);
      history.replaceState(null, "", url);
      lookup(address);
    });
    var initial = new URL(window.location.href).searchParams.get("address");
    if (initial) {
      document.getElementById("addr").value = initial;
      lookup(initial);
    }
  }
})();
