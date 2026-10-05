/* Markets page. Renders api/v1/markets.json and, where the exchange allows it,
   refreshes Firi and Coinmotion from the browser. No cookies. No new numbers:
   a missing or non-decimal field stays blank. */
(function () {
  var root = document.getElementById("mk");
  if (!root) return;
  var S = window.NC_MK || {};
  var jsonUrl = root.getAttribute("data-json");
  var box = document.getElementById("mk-tables");
  var status = document.getElementById("mk-status");
  var FIAT = ["NOK", "SEK", "DKK", "EUR"];
  var ASSET = ["BTC", "ETH", "SOL", "XRP", "ADA", "LTC", "DOGE", "DOT", "LINK", "BNB", "AVAX", "UNI", "AAVE", "XLM", "ATOM", "ALGO", "POL", "MATIC", "USDC"];
  var NAMES = {BTC: "Bitcoin", ETH: "Ether", SOL: "Solana", XRP: "XRP", ADA: "Cardano", LTC: "Litecoin", DOGE: "Dogecoin", DOT: "Polkadot", LINK: "Chainlink", BNB: "BNB", AVAX: "Avalanche", UNI: "Uniswap", AAVE: "Aave", XLM: "Stellar", ATOM: "Cosmos", ALGO: "Algorand", POL: "Polygon", MATIC: "Polygon", USDC: "USD Coin"};
  var state = null;
  var live = {};

  function dec(v) {
    if (v == null || v === true || v === false) return null;
    var s = String(v).trim();
    return /^-?\d+(\.\d+)?$/.test(s) ? s : null;
  }
  function fmt(s) {
    if (!s) return "—";
    var neg = s.charAt(0) === "-";
    var body = neg ? s.slice(1) : s;
    var parts = body.split(".");
    var whole = parts[0];
    var frac = (parts[1] || "").replace(/0+$/, "");
    var g = "";
    while (whole.length) { g = whole.slice(-3) + (g ? " " + g : ""); whole = whole.slice(0, -3); }
    return (neg ? "-" : "") + g + (frac ? "." + frac : "");
  }
  function when(iso) {
    if (!iso) return "";
    return iso.replace("T", " ").replace("+00:00", " UTC").replace(".000Z", " UTC").replace("Z", " UTC");
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c];
    });
  }
  function assetKey(b) { var i = ASSET.indexOf(b); return (i < 0 ? 99 : i) + b; }
  function quoteKey(q) { var i = FIAT.indexOf(q); return (i < 0 ? 99 : i) + q; }

  function card(row) {
    var ex = row.exchange || {};
    var last = row.last;
    var price = last
      ? '<p class="px">' + esc(fmt(last)) + ' <span class="unit">' + esc(row.quote) + '</span></p>'
      : '<p class="px">' + esc(S.no_last || "No last trade published") + '</p>';
    var fresh = live[ex.id] ? ' <span class="tag act">' + esc(S.live || "") + '</span>' : "";
    return '<article class="mkcard" data-base="' + esc(row.base) + '" data-ex="' + esc(ex.id) + '">' +
      '<p class="meta"><b>' + esc(ex.name || "") + '</b> · ' + esc(ex.country || "") + ' · ' + esc(row.base) + '/' + esc(row.quote) + fresh + '</p>' +
      price +
      '<p class="ba"><span>' + esc(S.bid || "Bid") + ' ' + esc(fmt(row.bid)) + '</span> <span>' + esc(S.ask || "Ask") + ' ' + esc(fmt(row.ask)) + '</span></p>' +
      '<p class="meta">' + esc(S.fetched || "Fetched") + ' <time datetime="' + esc(row.fetched_at || "") + '">' + esc(when(row.fetched_at)) + '</time>' +
      (row.source_url ? ' · <a href="' + esc(row.source_url) + '" rel="noopener">' + esc(S.source || "Source") + '</a>' : "") +
      '</p></article>';
  }

  function render() {
    if (!state) return;
    var pick = (document.getElementById("mk-asset") || {}).value || "";
    var rows = (state.tickers || []).filter(function (r) { return !pick || r.base === pick; });
    var groups = {};
    rows.forEach(function (r) {
      var g = groups[r.base] || (groups[r.base] = {});
      (g[r.quote] || (g[r.quote] = [])).push(r);
    });
    var bases = Object.keys(groups).sort(function (a, b) { return assetKey(a) < assetKey(b) ? -1 : 1; });
    if (!bases.length) {
      box.innerHTML = '<p class="empty">' + esc(S.empty || "") + '</p>';
    } else {
      box.innerHTML = bases.map(function (base) {
        var quotes = Object.keys(groups[base]).sort(function (a, b) { return quoteKey(a) < quoteKey(b) ? -1 : 1; });
        var title = (NAMES[base] ? NAMES[base] + " (" + base + ")" : base);
        var body = quotes.map(function (q) {
          var cards = groups[base][q].map(card).join("");
          return '<h3 class="mkq">' + esc((S.in_quote || "Prices in {q}").replace("{q}", q)) + '</h3><div class="mkcards">' + cards + '</div>';
        }).join("");
        return '<section class="mkasset"><h2>' + esc(title) + '</h2>' + body + '</section>';
      }).join("");
    }
    var errs = (state.exchanges || []).filter(function (e) { return e.status && e.status !== "ok"; });
    var errBox = document.getElementById("mk-errors");
    if (errBox) {
      errBox.innerHTML = errs.map(function (e) {
        return '<p class="notice warn">' + esc((S.error || "{name}").replace("{name}", e.name).replace("{when}", when(e.fetched_at))) + '</p>';
      }).join("");
    }
    if (status) status.textContent = Object.keys(live).length ? (S.browser || "") : (S.file || "");
  }

  function fillSelect() {
    var sel = document.getElementById("mk-asset");
    if (!sel || !state) return;
    var cur = sel.value;
    var bases = [];
    (state.tickers || []).forEach(function (r) { if (bases.indexOf(r.base) < 0) bases.push(r.base); });
    bases.sort(function (a, b) { return assetKey(a) < assetKey(b) ? -1 : 1; });
    sel.innerHTML = '<option value="">' + esc(S.all || "All") + '</option>' + bases.map(function (b) {
      return '<option value="' + esc(b) + '">' + esc(NAMES[b] ? NAMES[b] + " (" + b + ")" : b) + '</option>';
    }).join("");
    if (cur) sel.value = cur;
  }

  function splitSuffix(symbol, suffixes) {
    for (var i = 0; i < suffixes.length; i++) {
      var q = suffixes[i];
      if (symbol.length > q.length && symbol.slice(-q.length) === q) return [symbol.slice(0, -q.length), q];
    }
    return null;
  }
  function row(ex, exchangeSymbol, base, quote, source, last, bid, ask, extra) {
    if (FIAT.indexOf(quote) < 0) return null;
    last = dec(last); bid = dec(bid); ask = dec(ask);
    if (last == null && bid == null && ask == null) return null;
    var out = {
      id: ex.id + ":" + base + "-" + quote,
      symbol: base + "-" + quote,
      exchange_symbol: exchangeSymbol,
      base: base, quote: quote,
      last: last, bid: bid, ask: ask,
      exchange: {id: ex.id, name: ex.name, country: ex.country},
      fetched_at: new Date().toISOString().replace(/\.\d+Z$/, "+00:00"),
      source_url: source
    };
    if (extra) Object.keys(extra).forEach(function (k) { var n = dec(extra[k]); if (n != null) out[k] = n; });
    return out;
  }

  function applyLive(id, rows) {
    if (!state) return;
    var rest = (state.tickers || []).filter(function (t) { return !t.exchange || t.exchange.id !== id; });
    state.tickers = rest.concat(rows);
    live[id] = true;
    var ex = (state.exchanges || []).filter(function (e) { return e.id === id; })[0];
    if (ex) { ex.status = "ok"; ex.error = null; ex.ticker_count = rows.length; ex.fetched_at = rows[0] ? rows[0].fetched_at : ex.fetched_at; }
    fillSelect();
    render();
  }

  function getJSON(url) {
    return fetch(url, {credentials: "omit", cache: "no-store", referrerPolicy: "no-referrer", headers: {Accept: "application/json"}})
      .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); });
  }

  function refreshFiri() {
    return Promise.all([
      getJSON("https://api.firi.com/v2/markets"),
      getJSON("https://api.firi.com/v2/markets/tickers")
    ]).then(function (both) {
      var books = {};
      (both[1] || []).forEach(function (t) { if (t && t.market) books[t.market] = t; });
      var ex = {id: "firi", name: "Firi", country: "NO"};
      var rows = [];
      (both[0] || []).forEach(function (m) {
        if (!m || !m.id) return;
        var sp = splitSuffix(m.id, FIAT);
        if (!sp) return;
        var book = books[m.id] || {};
        var item = row(ex, m.id, sp[0], sp[1], "https://api.firi.com/v2/markets/" + m.id, m.last, book.bid, book.ask, {volume_base: m.volume, high: m.high, low: m.low, change_pct: m.change});
        if (item) rows.push(item);
      });
      if (rows.length) applyLive("firi", rows);
    });
  }

  function refreshCoinmotion() {
    return getJSON("https://api.coinmotion.com/v2/rates").then(function (payload) {
      var body = payload && payload.payload ? payload.payload : payload;
      var ex = {id: "coinmotion", name: "Coinmotion", country: "FI"};
      var rows = [];
      Object.keys(body || {}).forEach(function (key) {
        var rec = body[key];
        if (!rec || typeof rec !== "object" || !rec.currencyCode || !rec.baseCurrencyCode) return;
        var item = row(ex, key, String(rec.currencyCode).toUpperCase(), String(rec.baseCurrencyCode).toUpperCase(), "https://api.coinmotion.com/v2/rates", null, rec.buy, rec.sell, {high: rec.high, low: rec.low});
        if (item) rows.push(item);
      });
      if (rows.length) applyLive("coinmotion", rows);
    });
  }

  function refreshFile() {
    return getJSON(jsonUrl).then(function (doc) {
      state = doc;
      live = {};
      fillSelect();
      render();
    });
  }

  var sel = document.getElementById("mk-asset");
  if (sel) sel.addEventListener("change", render);

  refreshFile().catch(function () { if (status) status.textContent = S.file || ""; }).then(function () {
    refreshFiri().catch(function () {});
    refreshCoinmotion().catch(function () {});
  });
  setInterval(function () { refreshFile().catch(function () {}); }, 900000);
  setInterval(function () {
    refreshFiri().catch(function () {});
    refreshCoinmotion().catch(function () {});
  }, 300000);
})();
