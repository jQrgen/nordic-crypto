/* Markets page. Renders api/v1/markets.json and, where the exchange allows it,
   refreshes Firi and Coinmotion from the browser. No cookies. No new numbers:
   a missing or non-decimal field stays blank. Aggregates use decimal arithmetic
   (BigInt), the same rules as tools/markets.py. */
var NCMarkets = (function () {
  var FIAT = ["NOK", "SEK", "DKK", "EUR"];
  var EXCHANGES = ["firi", "nbx", "coinmotion"];

  function parseDec(text) {
    if (text == null || text === true || text === false) return null;
    var s = String(text).trim();
    if (!/^-?\d+(\.\d+)?$/.test(s)) return null;
    var neg = s.charAt(0) === "-";
    var body = neg ? s.slice(1) : s;
    var dot = body.indexOf(".");
    var whole = dot < 0 ? body : body.slice(0, dot);
    var frac = dot < 0 ? "" : body.slice(dot + 1);
    return {neg: neg, whole: whole || "0", frac: frac};
  }
  function formatScaled(n, scale, neg) {
    var text = n.toString();
    if (scale > 0) {
      while (text.length < scale + 1) text = "0" + text;
      text = text.slice(0, text.length - scale) + "." + text.slice(text.length - scale);
    }
    if (neg && n !== 0n) text = "-" + text;
    return text;
  }
  function scaledInts(texts) {
    if (typeof BigInt !== "function") return null;
    var parsed = [];
    for (var i = 0; i < texts.length; i++) {
      var item = parseDec(texts[i]);
      if (!item) return null;
      parsed.push(item);
    }
    if (!parsed.length) return null;
    var scale = 0;
    for (var j = 0; j < parsed.length; j++) if (parsed[j].frac.length > scale) scale = parsed[j].frac.length;
    var ints = [];
    for (var k = 0; k < parsed.length; k++) {
      var frac = parsed[k].frac;
      while (frac.length < scale) frac += "0";
      var n = BigInt(parsed[k].whole + frac);
      ints.push(parsed[k].neg ? -n : n);
    }
    return {ints: ints, scale: scale};
  }
  function sumDecimal(texts) {
    var scaled = scaledInts(texts);
    if (!scaled) return null;
    var total = 0n;
    for (var i = 0; i < scaled.ints.length; i++) total += scaled.ints[i];
    var neg = total < 0n;
    if (neg) total = -total;
    return formatScaled(total, scaled.scale, neg);
  }
  function meanDecimal(texts) {
    var scaled = scaledInts(texts);
    if (!scaled) return null;
    var count = BigInt(scaled.ints.length);
    var total = 0n;
    for (var i = 0; i < scaled.ints.length; i++) total += scaled.ints[i];
    var neg = total < 0n;
    if (neg) total = -total;
    var q = total / count;
    var r = total % count;
    var extra = [];
    var used = scaled.scale;
    while (r !== 0n && used < 12) {
      r *= 10n;
      extra.push(r / count);
      r = r % count;
      used += 1;
    }
    if (r !== 0n && (r * 10n) / count >= 5n) {
      if (extra.length) {
        var k = extra.length - 1;
        extra[k] += 1n;
        while (extra[k] === 10n) {
          extra[k] = 0n;
          if (k === 0) { q += 1n; break; }
          k -= 1;
          extra[k] += 1n;
        }
      } else q += 1n;
    }
    for (var e = 0; e < extra.length; e++) q = q * 10n + extra[e];
    return formatScaled(q, scaled.scale + extra.length, neg);
  }
  function extreme(texts, want) {
    var parsed = [];
    for (var i = 0; i < texts.length; i++) {
      var item = parseDec(texts[i]);
      if (item) parsed.push({text: texts[i], item: item});
    }
    if (!parsed.length || typeof BigInt !== "function") return null;
    var scale = 0;
    for (var j = 0; j < parsed.length; j++) if (parsed[j].item.frac.length > scale) scale = parsed[j].item.frac.length;
    var best = null, bestKey = null;
    for (var k = 0; k < parsed.length; k++) {
      var frac = parsed[k].item.frac;
      while (frac.length < scale) frac += "0";
      var n = BigInt(parsed[k].item.whole + frac);
      if (parsed[k].item.neg) n = -n;
      if (best === null || (want === "min" ? n < bestKey : n > bestKey)) { best = parsed[k].text; bestKey = n; }
    }
    return best;
  }
  function exKey(id) {
    var i = EXCHANGES.indexOf(id);
    return (i < 0 ? 99 : i) + ":" + id;
  }
  function dedupe(rows) {
    var chosen = {}, order = [];
    rows.forEach(function (row) {
      var id = (row.exchange && row.exchange.id) || "";
      if (!chosen[id]) { chosen[id] = row; order.push(id); return; }
      if ((row.fetched_at || "") >= (chosen[id].fetched_at || "")) chosen[id] = row;
    });
    return order.map(function (id) { return chosen[id]; }).sort(function (a, b) {
      var ka = exKey(a.exchange.id), kb = exKey(b.exchange.id);
      return ka < kb ? -1 : ka > kb ? 1 : 0;
    });
  }
  function volBlock(rows) {
    var out = {};
    ["volume_base", "volume_quote", "volume_base_24h", "volume_quote_24h"].forEach(function (field) {
      var vals = [];
      rows.forEach(function (row) { if (row[field] != null && row[field] !== "") vals.push(row[field]); });
      out[field] = vals.length ? sumDecimal(vals) : null;
      out[field + "_exchanges"] = vals.length;
    });
    return out;
  }
  function aggregatePairs(tickers, logoMap) {
    var groups = {};
    (tickers || []).forEach(function (row) {
      if (!row || !row.base || !row.quote) return;
      var key = row.base + "\n" + row.quote;
      (groups[key] || (groups[key] = [])).push(row);
    });
    return Object.keys(groups).map(function (key) {
      var parts = key.split("\n");
      var base = parts[0], quote = parts[1];
      var rows = dedupe(groups[key]);
      var contributors = rows.map(function (row) {
        var bid = row.bid, ask = row.ask, last = row.last;
        var mid = (bid != null && ask != null) ? meanDecimal([bid, ask]) : null;
        var ex = row.exchange || {};
        return {
          exchange_id: ex.id, name: ex.name, country: ex.country,
          last: last, bid: bid, ask: ask, mid: mid,
          included_in_last: last != null, included_in_mid: mid != null,
          volume_base: row.volume_base == null || row.volume_base === "" ? null : row.volume_base,
          volume_quote: row.volume_quote == null || row.volume_quote === "" ? null : row.volume_quote,
          volume_base_24h: row.volume_base_24h == null || row.volume_base_24h === "" ? null : row.volume_base_24h,
          volume_quote_24h: row.volume_quote_24h == null || row.volume_quote_24h === "" ? null : row.volume_quote_24h,
          fetched_at: row.fetched_at || null, source_url: row.source_url || null
        };
      });
      var lasts = [], mids = [];
      contributors.forEach(function (c) { if (c.last != null) lasts.push(c.last); if (c.mid != null) mids.push(c.mid); });
      var last = lasts.length ? meanDecimal(lasts) : null;
      var mid = mids.length ? meanDecimal(mids) : null;
      var method = null, series = [], price = null;
      if (lasts.length) { method = "mean_last"; series = lasts; price = last; }
      else if (mids.length) { method = "mean_bid_ask_mid"; series = mids; price = mid; }
      var fetched = [];
      contributors.forEach(function (c) { if (c.fetched_at) fetched.push(c.fetched_at); });
      fetched.sort();
      var logo = (logoMap && logoMap[base]) || {};
      contributors.forEach(function (c) {
        c.included_in_price = method === "mean_last" ? c.last != null : method === "mean_bid_ask_mid" ? c.mid != null : false;
      });
      return {
        symbol: base + "-" + quote, base: base, quote: quote, currency: quote,
        updated_at: fetched.length ? fetched[fetched.length - 1] : null,
        oldest_fetched_at: fetched.length ? fetched[0] : null,
        exchange_count: contributors.length, method: method, price: price,
        min: series.length ? extreme(series, "min") : null,
        max: series.length ? extreme(series, "max") : null,
        last: last, last_count: lasts.length, mid: mid, mid_count: mids.length,
        vwap: null, volume_used_for_price: false,
        volume: volBlock(contributors),
        logo_url: logo.logo_url || null, logo_path: logo.logo_path || null, logo: logo.logo || null
      };
    });
  }

  function boot() {
    var root = document.getElementById("mk");
    if (!root) return;
    var S = window.NC_MK || {};
    var jsonUrl = root.getAttribute("data-json");
    var box = document.getElementById("mk-tables");
    var status = document.getElementById("mk-status");
    var ASSET = ["BTC", "ETH", "SOL", "XRP", "ADA", "LTC", "DOGE", "DOT", "LINK", "BNB", "AVAX", "UNI", "AAVE", "XLM", "ATOM", "ALGO", "POL", "MATIC", "USDC"];
    var NAMES = {BTC: "Bitcoin", ETH: "Ether", SOL: "Solana", XRP: "XRP", ADA: "Cardano", LTC: "Litecoin", DOGE: "Dogecoin", DOT: "Polkadot", LINK: "Chainlink", BNB: "BNB", AVAX: "Avalanche", UNI: "Uniswap", AAVE: "Aave", XLM: "Stellar", ATOM: "Cosmos", ALGO: "Algorand", POL: "Polygon", MATIC: "Polygon", USDC: "USD Coin"};
    var state = null;
    var live = {};
    var logos = {};

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
    function siteRoot() {
      var u = jsonUrl || "";
      var i = u.indexOf("api/v1/markets.json");
      return i >= 0 ? u.slice(0, i) : "";
    }
    function fill(tmpl, map) {
      var s = tmpl || "";
      Object.keys(map).forEach(function (k) { s = s.split("{" + k + "}").join(map[k]); });
      return s;
    }
    function volumeHtml(vol, base, quote, summed) {
      if (!vol) return "";
      var bits = [];
      function line(key, unit, day) {
        if (vol[key] == null || vol[key] === "") return;
        var tmpl = summed ? (day ? S.vol_sum_24h : S.vol_sum_plain) : (day ? S.vol_24h : S.vol_plain);
        if (!tmpl) return;
        bits.push(esc(fill(tmpl, {n: fmt(vol[key]), unit: unit, count: String(vol[key + "_exchanges"] || 0)})));
      }
      line("volume_base_24h", base, true);
      line("volume_quote_24h", quote, true);
      line("volume_base", base, false);
      line("volume_quote", quote, false);
      if (!bits.length) return "";
      return '<p class="meta vol">' + bits.join(" · ") + "</p>";
    }
    function aggHtml(pair) {
      if (!pair) return "";
      var q = pair.quote;
      var price = pair.price
        ? '<p class="px">' + esc(fmt(pair.price)) + ' <span class="unit">' + esc(q) + "</span></p>"
        : '<p class="px">' + esc(S.agg_none || "") + "</p>";
      var how = S.agg_none || "";
      if (pair.method === "mean_last") how = fill(S.agg_last, {n: String(pair.last_count || 0)});
      else if (pair.method === "mean_bid_ask_mid") how = fill(S.agg_mid, {n: String(pair.mid_count || 0)});
      var span = (pair.min != null && pair.max != null) ? (" " + fill(S.agg_minmax, {min: fmt(pair.min), max: fmt(pair.max), q: q})) : "";
      var bits = [how + span, fill(S.agg_exchanges, {n: String(pair.exchange_count || 0)})];
      if (pair.updated_at) bits.push(fill(S.agg_updated, {when: when(pair.updated_at)}));
      return '<div class="mkagg"><p class="meta"><b>' + esc(S.agg || "") + "</b> · " + esc(pair.base) + "/" + esc(q) + "</p>" +
        price + '<p class="meta">' + esc(bits.filter(Boolean).join(" ")) + "</p>" +
        volumeHtml(pair.volume, pair.base, q, true) + "</div>";
    }
    function card(row) {
      var ex = row.exchange || {};
      var last = row.last;
      var price = last
        ? '<p class="px">' + esc(fmt(last)) + ' <span class="unit">' + esc(row.quote) + "</span></p>"
        : '<p class="px">' + esc(S.no_last || "No last trade published") + "</p>";
      var fresh = live[ex.id] ? ' <span class="tag act">' + esc(S.live || "") + "</span>" : "";
      return '<article class="mkcard" data-base="' + esc(row.base) + '" data-ex="' + esc(ex.id) + '">' +
        '<p class="meta"><b>' + esc(ex.name || "") + "</b> · " + esc(ex.country || "") + " · " + esc(row.base) + "/" + esc(row.quote) + fresh + "</p>" +
        price +
        '<p class="ba"><span>' + esc(S.bid || "Bid") + " " + esc(fmt(row.bid)) + "</span> <span>" + esc(S.ask || "Ask") + " " + esc(fmt(row.ask)) + "</span></p>" +
        volumeHtml(row, row.base, row.quote, false) +
        '<p class="meta">' + esc(S.fetched || "Fetched") + ' <time datetime="' + esc(row.fetched_at || "") + '">' + esc(when(row.fetched_at)) + "</time>" +
        (row.source_url ? ' · <a href="' + esc(row.source_url) + '" rel="noopener">' + esc(S.source || "Source") + "</a>" : "") +
        "</p></article>";
    }
    function render() {
      if (!state || !box) return;
      var pick = (document.getElementById("mk-asset") || {}).value || "";
      var rows = (state.tickers || []).filter(function (r) { return !pick || r.base === pick; });
      var groups = {};
      rows.forEach(function (r) {
        var g = groups[r.base] || (groups[r.base] = {});
        (g[r.quote] || (g[r.quote] = [])).push(r);
      });
      var agg = {};
      aggregatePairs(rows, logos).forEach(function (p) { agg[p.base + "|" + p.quote] = p; });
      var bases = Object.keys(groups).sort(function (a, b) { return assetKey(a) < assetKey(b) ? -1 : 1; });
      if (!bases.length) {
        box.innerHTML = '<p class="empty">' + esc(S.empty || "") + "</p>";
      } else {
        box.innerHTML = bases.map(function (base) {
          var quotes = Object.keys(groups[base]).sort(function (a, b) { return quoteKey(a) < quoteKey(b) ? -1 : 1; });
          var title = (NAMES[base] ? NAMES[base] + " (" + base + ")" : base);
          var img = "";
          if (logos[base] && logos[base].logo_path) {
            img = '<img src="' + esc(siteRoot() + logos[base].logo_path) + '" width="28" height="28" alt="' + esc(fill(S.logo_alt, {name: title})) + '">';
          }
          var body = quotes.map(function (q) {
            var cards = groups[base][q].map(card).join("");
            return aggHtml(agg[base + "|" + q]) + '<h3 class="mkq">' + esc(fill(S.in_quote, {q: q})) + '</h3><div class="mkcards">' + cards + "</div>";
          }).join("");
          return '<section class="mkasset"><h2>' + img + esc(title) + "</h2>" + body + "</section>";
        }).join("");
      }
      var errs = (state.exchanges || []).filter(function (e) { return e.status && e.status !== "ok"; });
      var errBox = document.getElementById("mk-errors");
      if (errBox) {
        errBox.innerHTML = errs.map(function (e) {
          return '<p class="notice warn">' + esc(fill(S.error, {name: e.name, when: when(e.fetched_at)})) + "</p>";
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
      sel.innerHTML = '<option value="">' + esc(S.all || "All") + "</option>" + bases.map(function (b) {
        return '<option value="' + esc(b) + '">' + esc(NAMES[b] ? NAMES[b] + " (" + b + ")" : b) + "</option>";
      }).join("");
      if (cur) sel.value = cur;
    }
    function rememberLogos(doc) {
      (doc.aggregated || []).forEach(function (p) {
        if (p && p.base && p.logo_path) logos[p.base] = p;
      });
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
        rememberLogos(doc);
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
  }

  if (typeof document !== "undefined") boot();
  return {meanDecimal: meanDecimal, sumDecimal: sumDecimal, aggregatePairs: aggregatePairs};
})();
if (typeof module !== "undefined" && module.exports) module.exports = NCMarkets;
