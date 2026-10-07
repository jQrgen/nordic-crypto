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

  var SHARE_NUM = 3, SHARE_DEN = 100;
  var SHARE_COLORS = ["#0f5ea8", "#111111", "#b45309", "#047857", "#7c3aed", "#be123c", "#0e7490", "#a16207"];
  var SHARE_OTHER = "#9ca3af";

  function decInt(text, scale) {
    var item = parseDec(text);
    if (!item || typeof BigInt !== "function") return null;
    var frac = item.frac;
    while (frac.length < scale) frac += "0";
    var n = BigInt(item.whole + frac);
    return item.neg ? -n : n;
  }
  function isPositive(text) {
    var item = parseDec(text);
    if (!item || item.neg) return false;
    return item.whole.replace(/0/g, "") !== "" || item.frac.replace(/0/g, "") !== "";
  }
  function belowShare(part, total, num, den) {
    if (!isPositive(part) || !isPositive(total)) return true;
    var scale = Math.max(parseDec(part).frac.length, parseDec(total).frac.length);
    var p = decInt(part, scale), t = decInt(total, scale);
    return p * BigInt(den) < t * BigInt(num);
  }
  function tenthsDivision(part, total) {
    if (!isPositive(part) || !isPositive(total)) return [0, 0n, 1n];
    var scale = Math.max(parseDec(part).frac.length, parseDec(total).frac.length);
    var p = decInt(part, scale), t = decInt(total, scale);
    var num = p * 1000n;
    return [Number(num / t), num % t, t];
  }
  function volumeShares(tickers, names, logoMap) {
    names = names || {};
    logoMap = logoMap || {};
    if (typeof BigInt !== "function") return [];
    var byQuote = {};
    (tickers || []).forEach(function (row) {
      if (!row || !row.base || !row.quote || !isPositive(row.volume_quote_24h)) return;
      var g = byQuote[row.quote] || (byQuote[row.quote] = {});
      (g[row.base] || (g[row.base] = [])).push(row);
    });
    function quoteRank(q) { var i = FIAT.indexOf(q); return (i < 0 ? 99 : i) + q; }
    var quotes = Object.keys(byQuote).sort(function (a, b) { return quoteRank(a) < quoteRank(b) ? -1 : quoteRank(a) > quoteRank(b) ? 1 : 0; });
    return quotes.map(function (quote) {
      var coins = [];
      Object.keys(byQuote[quote]).forEach(function (base) {
        var rows = dedupe(byQuote[quote][base]).filter(function (row) { return isPositive(row.volume_quote_24h); });
        var total = rows.length ? sumDecimal(rows.map(function (row) { return row.volume_quote_24h; })) : null;
        if (!isPositive(total)) return;
        var sources = [], seen = {};
        rows.forEach(function (row) {
          var ex = row.exchange || {};
          var key = (ex.id || "") + "\n" + (row.source_url || "");
          if (seen[key]) return;
          seen[key] = true;
          sources.push({id: ex.id || "", name: ex.name || ex.id || "", url: row.source_url || ""});
        });
        sources.sort(function (a, b) { return exKey(a.id) < exKey(b.id) ? -1 : exKey(a.id) > exKey(b.id) ? 1 : (a.url < b.url ? -1 : a.url > b.url ? 1 : 0); });
        var fetched = [];
        rows.forEach(function (row) { if (row.fetched_at) fetched.push(row.fetched_at); });
        coins.push({
          base: base,
          name: names[base] || base,
          volume: total,
          logo_path: (logoMap[base] && logoMap[base].logo_path) || null,
          fetched: fetched,
          sources: sources
        });
      });
      if (!coins.length) return null;
      var grand = sumDecimal(coins.map(function (c) { return c.volume; }));
      if (!isPositive(grand)) return null;
      coins.sort(function (a, b) {
        var cmp = 0;
        var sa = parseDec(a.volume), sb = parseDec(b.volume);
        var scale = Math.max(sa.frac.length, sb.frac.length);
        var ia = decInt(a.volume, scale), ib = decInt(b.volume, scale);
        if (ia !== ib) cmp = ia > ib ? -1 : 1;
        else cmp = a.base < b.base ? -1 : a.base > b.base ? 1 : 0;
        return cmp;
      });
      var large = [], small = [];
      coins.forEach(function (c) { (belowShare(c.volume, grand, SHARE_NUM, SHARE_DEN) ? small : large).push(c); });
      if (!large.length) { large = coins; small = []; }
      var slices = large.map(function (c) {
        return {base: c.base, name: c.name, volume: c.volume, logo_path: c.logo_path, other: false, members: [c.base]};
      });
      if (small.length) {
        small.sort(function (a, b) {
          var sa = parseDec(a.volume), sb = parseDec(b.volume);
          var scale = Math.max(sa.frac.length, sb.frac.length);
          var ia = decInt(a.volume, scale), ib = decInt(b.volume, scale);
          if (ia !== ib) return ia > ib ? -1 : 1;
          return a.base < b.base ? -1 : a.base > b.base ? 1 : 0;
        });
        slices.push({
          base: null, name: null,
          volume: sumDecimal(small.map(function (c) { return c.volume; })),
          logo_path: null, other: true,
          members: small.map(function (c) { return c.base; })
        });
      }
      var parts = slices.map(function (sl) { return tenthsDivision(sl.volume, grand); });
      var allocated = 0;
      parts.forEach(function (p) { allocated += p[0]; });
      var remain = 1000 - allocated;
      var order = parts.map(function (_p, i) { return i; });
      order.sort(function (i, j) {
        var left = parts[i][1] * parts[j][2], right = parts[j][1] * parts[i][2];
        if (left !== right) return left > right ? -1 : 1;
        return i - j;
      });
      var tenths = parts.map(function (p) { return p[0]; });
      for (var n = 0; n < remain && n < order.length; n++) tenths[order[n]] += 1;
      slices.forEach(function (sl, i) {
        sl.tenths = tenths[i];
        sl.pct = String(Math.floor(tenths[i] / 10)) + "." + String(tenths[i] % 10);
      });
      var fetched = [];
      var sources = [], seenSrc = {};
      coins.forEach(function (c) {
        c.fetched.forEach(function (f) { fetched.push(f); });
        c.sources.forEach(function (src) {
          var key = src.id + "\n" + src.url;
          if (seenSrc[key]) return;
          seenSrc[key] = true;
          sources.push(src);
        });
      });
      fetched.sort();
      sources.sort(function (a, b) { return exKey(a.id) < exKey(b.id) ? -1 : exKey(a.id) > exKey(b.id) ? 1 : (a.url < b.url ? -1 : a.url > b.url ? 1 : 0); });
      return {
        quote: quote, window: "24h", field: "volume_quote_24h", total: grand,
        updated_at: fetched.length ? fetched[fetched.length - 1] : null,
        sources: sources, threshold_pct: SHARE_NUM, slices: slices
      };
    }).filter(Boolean);
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
    var KEYS = ["BTC", "ETH", "SOL", "XRP"];
    var EXSHORT = {firi: "Firi", nbx: "NBX", coinmotion: "Coinmotion"};
    function exShort(ex) {
      ex = ex || {};
      return EXSHORT[ex.id] || ex.name || ex.id || "";
    }
    function chgKind(text) {
      if (text == null || text === "") return "";
      var s = String(text);
      var body = s.charAt(0) === "-" ? s.slice(1) : s;
      if (body.replace(/\./g, "").replace(/0/g, "") === "") return "flat";
      return s.charAt(0) === "-" ? "dn" : "up";
    }
    function chgShown(text) {
      var shown = fmt(String(text));
      return chgKind(text) === "up" ? "+" + shown : shown;
    }
    function hasNum(v) { return v != null && v !== ""; }
    function volCell(vol, base, quote) {
      vol = vol || {};
      var bits = [];
      if (hasNum(vol.volume_quote_24h)) bits.push(["main", fmt(vol.volume_quote_24h) + " " + quote, "24h"]);
      else if (hasNum(vol.volume_base_24h)) bits.push(["main", fmt(vol.volume_base_24h) + " " + base, "24h"]);
      if (hasNum(vol.volume_base)) bits.push([bits.length ? "sub" : "main", fmt(vol.volume_base) + " " + base, "window"]);
      else if (hasNum(vol.volume_quote) && !hasNum(vol.volume_quote_24h)) bits.push([bits.length ? "sub" : "main", fmt(vol.volume_quote) + " " + quote, "window"]);
      if (!bits.length) return '<span class="meta">—</span>';
      return bits.map(function (b) {
        var label = b[2] === "24h" ? "24h" : (S.vol_window || "");
        if (b[0] === "main") return '<span class="pxs">' + esc(b[1]) + '</span><span class="meta sub">' + esc(label) + "</span>";
        return '<span class="meta sub">' + esc(b[1]) + " · " + esc(label) + "</span>";
      }).join("");
    }
    function exCell(row) {
      if (!row) return '<span class="meta">—</span>';
      var bits = [];
      if (hasNum(row.last)) bits.push('<span class="pxs">' + esc(fmt(row.last)) + "</span>");
      else {
        var ba = [];
        if (hasNum(row.bid)) ba.push(esc(S.bid || "Bid") + " " + esc(fmt(row.bid)));
        if (hasNum(row.ask)) ba.push(esc(S.ask || "Ask") + " " + esc(fmt(row.ask)));
        if (!ba.length) bits.push('<span class="meta">' + esc(S.no_last || "") + "</span>");
        else {
          bits.push('<span class="pxs">' + ba[0] + "</span>");
          if (ba.length > 1) bits.push('<span class="meta sub">' + ba[1] + "</span>");
        }
      }
      if (hasNum(row.change_pct)) {
        bits.push('<span class="chg ' + chgKind(row.change_pct) + '" title="' + esc(S.chg_tip || "") + '">' + esc(chgShown(row.change_pct)) + "%</span>");
      }
      if (row.exchange && live[row.exchange.id]) bits.push(' <span class="tag act">' + esc(S.live || "") + "</span>");
      return bits.join("");
    }
    function indexTickers(tickers) {
      var out = {};
      (tickers || []).forEach(function (row) {
        if (!row || !row.base || !row.quote) return;
        var id = row.exchange && row.exchange.id;
        if (!id) return;
        var key = row.base + "|" + row.quote;
        var slot = out[key] || (out[key] = {});
        var prev = slot[id];
        if (!prev || (row.fetched_at || "") >= (prev.fetched_at || "")) slot[id] = row;
      });
      return out;
    }
    function exIds(tickers) {
      var ids = [];
      (tickers || []).forEach(function (r) {
        var id = r && r.exchange && r.exchange.id;
        if (id && ids.indexOf(id) < 0) ids.push(id);
      });
      ids.sort(function (a, b) { return exKey(a) < exKey(b) ? -1 : exKey(a) > exKey(b) ? 1 : 0; });
      return ids;
    }
    function assetRank(b) { var i = ASSET.indexOf(b); return i < 0 ? 99 : i; }
    function quoteRank(q) { var i = FIAT.indexOf(q); return i < 0 ? 99 : i; }
    function cmpDec(a, b) {
      var scaled = scaledInts([String(a), String(b)]);
      if (!scaled) return 0;
      if (scaled.ints[0] < scaled.ints[1]) return -1;
      if (scaled.ints[0] > scaled.ints[1]) return 1;
      return 0;
    }
    function cmpDecDir(a, b, dir) {
      var am = !hasNum(a), bm = !hasNum(b);
      if (am && bm) return 0;
      if (am) return 1;
      if (bm) return -1;
      return cmpDec(a, b) * dir;
    }
    function exPx(indexed, pair, id) {
      var row = (indexed[pair.base + "|" + pair.quote] || {})[id];
      if (!row) return null;
      if (hasNum(row.last)) return row.last;
      if (hasNum(row.bid) && hasNum(row.ask)) return meanDecimal([row.bid, row.ask]);
      if (hasNum(row.bid)) return row.bid;
      if (hasNum(row.ask)) return row.ask;
      return null;
    }
    function cmpPair(a, b, mode, indexed) {
      if (mode === "coin") {
        var c = assetRank(a.base) - assetRank(b.base);
        if (c) return c;
        if (a.base !== b.base) return a.base < b.base ? -1 : 1;
        return quoteRank(a.quote) - quoteRank(b.quote);
      }
      if (mode === "quote") {
        var q = quoteRank(a.quote) - quoteRank(b.quote);
        if (q) return q;
        if (a.quote !== b.quote) return a.quote < b.quote ? -1 : 1;
        return assetRank(a.base) - assetRank(b.base);
      }
      var g = quoteRank(a.quote) - quoteRank(b.quote);
      if (g) return g;
      var av, bv, dir = 1;
      if (mode === "price" || mode === "price-desc") {
        av = a.price; bv = b.price; dir = mode === "price-desc" ? -1 : 1;
      } else if (mode === "vol") {
        av = a.volume && a.volume.volume_quote_24h;
        bv = b.volume && b.volume.volume_quote_24h;
        dir = -1;
      } else if (mode.indexOf("ex:") === 0) {
        var id = mode.slice(3);
        av = exPx(indexed, a, id);
        bv = exPx(indexed, b, id);
        dir = -1;
      }
      var d = cmpDecDir(av, bv, dir);
      if (d) return d;
      return assetRank(a.base) - assetRank(b.base);
    }
    function sortTh(key, label, title) {
      var mode = (document.getElementById("mk-sort") || {}).value || "coin";
      var on = mode === key || (key === "price" && mode === "price-desc");
      var extra = title ? ' title="' + esc(title) + '"' : "";
      return '<th scope="col"' + extra + '><button type="button" class="sort" data-sort="' + esc(key) + '" aria-pressed="' + (on ? "true" : "false") + '">' + esc(label) + "</button></th>";
    }
    function tableHtml(pairs, indexed, ids, names) {
      if (!pairs.length) return '<p class="empty">' + esc(S.no_match || S.empty || "") + "</p>";
      var heads = [sortTh("coin", S.col_coin || ""), sortTh("quote", S.col_quote || ""), sortTh("price", S.col_price || ""), sortTh("vol", S.col_vol || "")];
      ids.forEach(function (id) {
        var short = EXSHORT[id] || names[id] || id;
        heads.push(sortTh("ex:" + id, short, names[id] || short));
      });
      var body = pairs.map(function (p) {
        var name = NAMES[p.base] || p.base;
        var img = p.logo_path ? '<img src="' + esc(siteRoot() + p.logo_path) + '" width="22" height="22" alt="">' : "";
        var price = p.price
          ? '<span class="pxs">' + esc(fmt(p.price)) + '</span><span class="meta sub">' + esc(p.quote) + "</span>"
          : '<span class="meta">' + esc(S.agg_none || "") + "</span>";
        var slot = indexed[p.base + "|" + p.quote] || {};
        var tds = [
          '<td data-label="' + esc(S.col_coin || "") + '"><div class="coin">' + img + "<span>" + esc(name) + ' <span class="sym">' + esc(p.base) + "</span></span></div></td>",
          '<td data-label="' + esc(S.col_quote || "") + '">' + esc(p.quote) + "</td>",
          '<td data-label="' + esc(S.col_price || "") + '">' + price + "</td>",
          '<td data-label="' + esc(S.col_vol || "") + '">' + volCell(p.volume, p.base, p.quote) + "</td>"
        ];
        ids.forEach(function (id) {
          var short = EXSHORT[id] || names[id] || id;
          tds.push('<td data-label="' + esc(short) + '">' + exCell(slot[id]) + "</td>");
        });
        return "<tr>" + tds.join("") + "</tr>";
      }).join("");
      return '<div class="mkwrap"><table class="list mkpairs"><caption>' + esc(S.table_h || "") + "</caption><thead><tr>" + heads.join("") + "</tr></thead><tbody>" + body + "</tbody></table></div>";
    }
    function renderCredit() {
      var el = document.getElementById("mk-credit");
      if (!el || !state) return;
      var times = [];
      (state.tickers || []).forEach(function (r) { if (r.fetched_at) times.push(r.fetched_at); });
      times.sort();
      var parts = [];
      if (times.length) parts.push(esc(fill(S.updated || "", {when: when(times[times.length - 1])})));
      var links = (state.exchanges || []).filter(function (e) { return e.status === "ok"; }).map(function (e) {
        var name = e.name || e.id || "";
        return e.website ? '<a href="' + esc(e.website) + '" rel="noopener">' + esc(name) + "</a>" : esc(name);
      });
      if (links.length) parts.push(esc(S.sources || "") + ": " + links.join(", "));
      el.innerHTML = parts.join(" ");
    }
    function renderSummary() {
      var host = document.getElementById("mk-summary");
      if (!host || !state) return;
      var pairs = aggregatePairs(state.tickers || [], logos);
      var by = {};
      pairs.forEach(function (p) { by[p.base + "|" + p.quote] = p; });
      var indexed = indexTickers(state.tickers || []);
      var tiles = [];
      KEYS.forEach(function (base) {
        var pair = null;
        for (var i = 0; i < FIAT.length; i++) {
          var cand = by[base + "|" + FIAT[i]];
          if (cand && cand.price) { pair = cand; break; }
        }
        if (!pair) return;
        var name = NAMES[base] || base;
        var full = name !== base ? name + " (" + base + ")" : base;
        var img = pair.logo_path ? '<img src="' + esc(siteRoot() + pair.logo_path) + '" width="22" height="22" alt="' + esc(fill(S.logo_alt || "", {name: full})) + '">' : "";
        var how = S.agg_none || "";
        if (pair.method === "mean_last") how = fill(S.mean_last || "", {n: String(pair.last_count || 0)});
        else if (pair.method === "mean_bid_ask_mid") how = fill(S.mean_mid || "", {n: String(pair.mid_count || 0)});
        var slot = indexed[base + "|" + pair.quote] || {};
        var chg = "";
        exIds(Object.keys(slot).map(function (id) { return slot[id]; })).forEach(function (id) {
          var row = slot[id];
          if (!row || !hasNum(row.change_pct)) return;
          chg += '<p class="chg ' + chgKind(row.change_pct) + '">' + esc(fill(S.chg || "", {name: exShort(row.exchange), n: chgShown(row.change_pct)})) + "</p>";
        });
        tiles.push('<article class="mktile"><p class="k">' + img + esc(name) + ' <span class="sym">' + esc(base) + "</span></p>" +
          '<p class="px">' + esc(fmt(pair.price)) + ' <span class="unit">' + esc(pair.quote) + "</span></p>" +
          chg + '<p class="meta">' + esc(how) + "</p></article>");
      });
      volumeShares(state.tickers || [], NAMES, logos).forEach(function (g) {
        tiles.push('<article class="mktile"><p class="k">' + esc(S.vol_tile || "") + "</p>" +
          '<p class="px">' + esc(fmt(g.total)) + ' <span class="unit">' + esc(g.quote) + "</span></p>" +
          '<p class="meta">' + esc(S.vol_tile_note || "") + "</p></article>");
      });
      var ok = (state.exchanges || []).filter(function (e) { return e.status === "ok"; }).length;
      var bases = {};
      (state.tickers || []).forEach(function (r) { if (r.base) bases[r.base] = 1; });
      tiles.push('<article class="mktile"><p class="k">' + esc(S.tracked || "") + '</p><ul class="mkstats">' +
        "<li><b>" + ok + "</b> " + esc(S.n_ex || "") + "</li>" +
        "<li><b>" + pairs.length + "</b> " + esc(S.n_pairs || "") + "</li>" +
        "<li><b>" + Object.keys(bases).length + "</b> " + esc(S.n_coins || "") + "</li></ul></article>");
      var inner = (state.tickers || []).length ? '<div class="mktiles">' + tiles.join("") + "</div>" : '<p class="empty">' + esc(S.empty || "") + "</p>";
      host.innerHTML = '<h2 id="mk-glance">' + esc(S.glance || "") + "</h2>" + inner;
    }
    function renderTable() {
      var host = document.getElementById("mk-tables");
      if (!host || !state) return;
      var indexed = indexTickers(state.tickers || []);
      var pairs = aggregatePairs(state.tickers || [], logos);
      var q = ((document.getElementById("mk-q") || {}).value || "").trim().toLowerCase();
      var quote = (document.getElementById("mk-quote") || {}).value || "";
      pairs = pairs.filter(function (p) {
        if (quote && p.quote !== quote) return false;
        if (!q) return true;
        var name = (NAMES[p.base] || p.base).toLowerCase();
        var blob = (p.base + " " + name + " " + p.quote).toLowerCase();
        var slot = indexed[p.base + "|" + p.quote] || {};
        Object.keys(slot).forEach(function (id) {
          var ex = slot[id].exchange || {};
          blob += " " + (ex.name || "").toLowerCase() + " " + exShort(ex).toLowerCase() + " " + id;
        });
        return blob.indexOf(q) >= 0;
      });
      var mode = (document.getElementById("mk-sort") || {}).value || "coin";
      pairs.sort(function (a, b) { return cmpPair(a, b, mode, indexed); });
      var names = {};
      (state.tickers || []).forEach(function (r) {
        var ex = r.exchange || {};
        if (ex.id && !names[ex.id]) names[ex.id] = ex.name || ex.id;
      });
      host.innerHTML = tableHtml(pairs, indexed, exIds(state.tickers || []), names);
      var shown = document.getElementById("mk-shown");
      if (shown) shown.textContent = fill(S.row_count || "{n}", {n: String(pairs.length)});
    }
    function sliceLabel(sl) {
      if (sl.other) return S.share_other || "Other";
      var name = sl.name || sl.base;
      return name && name !== sl.base ? name + " (" + sl.base + ")" : (sl.base || "");
    }
    function tenthsStr(n) {
      var sign = n < 0 ? "-" : "";
      n = Math.abs(n);
      return sign + Math.floor(n / 10) + "." + (n % 10);
    }
    function sharePct(sl) { return sl.tenths ? sl.pct : "<0.1"; }
    function donutSvg(slices, quote, title) {
      var titleId = "mkvol-t-" + quote;
      var descId = "mkvol-d-" + quote;
      var desc = slices.map(function (sl) { return sliceLabel(sl) + " " + sharePct(sl) + "%"; }).join(", ");
      var rings = "";
      var drawn = slices.filter(function (sl) { return sl.tenths; });
      if (drawn.length === 1 && drawn[0].tenths >= 1000) {
        rings = '<circle cx="21" cy="21" r="15.9155" fill="none" stroke="' + drawn[0].color + '" stroke-width="6"><title>' + esc(sliceLabel(drawn[0])) + " " + esc(sharePct(drawn[0])) + "%</title></circle>";
      } else {
        var offset = 250;
        slices.forEach(function (sl) {
          if (!sl.tenths) return;
          var gap = 1000 - sl.tenths;
          var pct = tenthsStr(sl.tenths);
          var gapS = tenthsStr(gap);
          var off = tenthsStr(offset);
          rings += '<circle cx="21" cy="21" r="15.9155" fill="none" stroke="' + sl.color + '" stroke-width="6" stroke-dasharray="' + pct + " " + gapS + '" stroke-dashoffset="' + off + '"><title>' + esc(sliceLabel(sl)) + " " + esc(sharePct(sl)) + "%</title></circle>";
          offset -= sl.tenths;
        });
      }
      return '<svg viewBox="0 0 42 42" role="img" aria-labelledby="' + titleId + " " + descId + '">' +
        '<title id="' + titleId + '">' + esc(title) + "</title>" +
        '<desc id="' + descId + '">' + esc(desc) + "</desc>" +
        rings +
        '<text x="21" y="20.4" text-anchor="middle" font-family="system-ui,sans-serif" font-size="3.4" font-weight="700" fill="#111">' + esc(quote) + "</text>" +
        '<text x="21" y="23.8" text-anchor="middle" font-family="system-ui,sans-serif" font-size="2.1" fill="#4B5563">24h</text></svg>';
    }
    function shareHtml(groups) {
      var head = '<h2>' + esc(S.share_h || "") + "</h2><p class=\"meta\">" + esc(S.share_note || "") + "</p>";
      if (!groups.length) return '<section class="mkvol">' + head + '<p class="meta">' + esc(S.share_empty || "") + "</p></section>";
      var figures = groups.map(function (g) {
        var q = g.quote;
        var colorI = 0;
        var slices = g.slices.map(function (sl) {
          var color = sl.other ? SHARE_OTHER : SHARE_COLORS[colorI % SHARE_COLORS.length];
          if (!sl.other) colorI += 1;
          var copy = {};
          Object.keys(sl).forEach(function (k) { copy[k] = sl[k]; });
          copy.color = color;
          return copy;
        });
        var title = fill(S.share_caption || "", {q: q});
        var legend = slices.map(function (sl) {
          var label = sliceLabel(sl);
          var img = sl.logo_path ? '<img src="' + esc(siteRoot() + sl.logo_path) + '" width="22" height="22" alt="' + esc(fill(S.logo_alt || "", {name: label})) + '">' : "";
          var extra = sl.other && sl.members && sl.members.length ? '<span class="meta">' + esc(fill(S.share_includes || "", {names: sl.members.join(", ")})) + "</span>" : "";
          return '<li><span class="sw" style="background:' + sl.color + '"></span>' + img + '<span class="nm">' + esc(label) + "</span>" + extra + '<span class="pct">' + esc(sharePct(sl)) + "%</span></li>";
        }).join("");
        var rows = slices.map(function (sl) {
          return "<tr><th scope=\"row\">" + esc(sliceLabel(sl)) + "</th><td>" + esc(fmt(sl.volume)) + " " + esc(q) + "</td><td>" + esc(sharePct(sl)) + "%</td></tr>";
        }).join("");
        var src = (g.sources || []).map(function (s) {
          var name = s.name || s.id || "";
          return s.url ? '<a href="' + esc(s.url) + '" rel="noopener">' + esc(name) + "</a>" : esc(name);
        }).filter(Boolean).join(", ");
        var meta = esc(fill(S.share_window || "", {q: q}));
        if (g.updated_at) meta += " " + esc(fill(S.share_updated || "", {when: when(g.updated_at)}));
        if (src) meta += " " + esc(S.share_source || "") + ": " + src;
        meta += " " + esc(S.share_group || "");
        return '<figure class="mkvol-fig"><div class="mkvol-row">' + donutSvg(slices, q, title) + '<ul class="mklegend">' + legend + "</ul></div>" +
          '<p class="meta">' + meta + "</p>" +
          '<table class="list mkshare"><caption>' + esc(title) + "</caption><thead><tr><th scope=\"col\">" + esc(S.share_coin || "") + "</th><th scope=\"col\">" + esc(fill(S.share_vol || "", {q: q})) + "</th><th scope=\"col\">" + esc(S.share_pct || "") + "</th></tr></thead><tbody>" + rows + "</tbody></table></figure>";
      }).join("");
      return '<section class="mkvol">' + head + figures + "</section>";
    }
    function renderShare() {
      var host = document.getElementById("mk-share");
      if (!host || !state) return;
      host.innerHTML = shareHtml(volumeShares(state.tickers || [], NAMES, logos));
    }
    function render() {
      if (!state) return;
      renderShare();
      renderCredit();
      renderSummary();
      renderTable();
      var errs = (state.exchanges || []).filter(function (e) { return e.status && e.status !== "ok"; });
      var errBox = document.getElementById("mk-errors");
      if (errBox) {
        errBox.innerHTML = errs.map(function (e) {
          return '<p class="notice warn">' + esc(fill(S.error, {name: e.name, when: when(e.fetched_at)})) + "</p>";
        }).join("");
      }
      if (status) status.textContent = Object.keys(live).length ? (S.browser || "") : (S.file || "");
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
        render();
      });
    }
    var board = document.getElementById("mk-board");
    if (board) board.addEventListener("click", function (ev) {
      var btn = ev.target.closest ? ev.target.closest("button.sort") : null;
      if (!btn) return;
      var key = btn.getAttribute("data-sort") || "coin";
      var sel = document.getElementById("mk-sort");
      var cur = sel ? sel.value : "coin";
      var next = key === "price" ? (cur === "price" ? "price-desc" : "price") : key;
      if (sel) sel.value = next;
      renderTable();
    });
    var qf = document.getElementById("mk-q");
    if (qf) qf.addEventListener("input", renderTable);
    var qsel = document.getElementById("mk-quote");
    if (qsel) qsel.addEventListener("change", renderTable);
    var ssel = document.getElementById("mk-sort");
    if (ssel) ssel.addEventListener("change", renderTable);
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
  return {meanDecimal: meanDecimal, sumDecimal: sumDecimal, aggregatePairs: aggregatePairs, volumeShares: volumeShares};
})();
if (typeof module !== "undefined" && module.exports) module.exports = NCMarkets;
