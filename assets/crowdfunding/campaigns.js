/* Nordic Crypto crowdfunding pilot: QR codes for each project's own payment URI, and a read-only
   progress figure. Progress asks public Electrum/Rostrum servers over WebSocket for the current
   balance of the project's address. Runs in the reader's browser; nothing is sent to Nordic Crypto,
   no cookies, no donor data. Demo entries get a QR but no lookup. */
(function () {
  var SERVERS = {
    bch: ["wss://electrum-bch.nordiccrypto.no:50004", "wss://bch.imaginary.cash:50004", "wss://electroncash.de:60002"],
    nexa: ["wss://electrum-nexa.nordiccrypto.no:20004", "wss://electrum.nexa.org:20004"]
  };
  var UNIT = { bch: 1e8, nexa: 100 };
  var TIMEOUT_MS = 8000;
  var L = window.NC_CF || {};

  function qr(el) {
    if (typeof qrcode !== "function") return;
    var q = qrcode(0, "M"); q.addData(el.getAttribute("data-uri")); q.make();
    el.innerHTML = q.createSvgTag({ cellSize: 4, margin: 2, scalable: true, alt: el.getAttribute("data-alt") || "" });
  }

  function balance(chain, addr, i, cb) {
    var list = SERVERS[chain] || [];
    if (i >= list.length) return cb(null);
    var done = false, ws;
    function next() { if (done) return; done = true; try { ws.close(); } catch (e) {} balance(chain, addr, i + 1, cb); }
    var timer = setTimeout(next, TIMEOUT_MS);
    try { ws = new WebSocket(list[i]); } catch (e) { clearTimeout(timer); return next(); }
    ws.onopen = function () { ws.send(JSON.stringify({ jsonrpc: "2.0", id: 1, method: "blockchain.address.get_balance", params: [addr] })); };
    ws.onmessage = function (m) {
      var r; try { r = JSON.parse(m.data); } catch (e) { return; }
      if (r.id !== 1) return;
      if (!r.result) { clearTimeout(timer); return next(); }
      done = true; clearTimeout(timer); try { ws.close(); } catch (e) {}
      cb((Number(r.result.confirmed || 0) + Number(r.result.unconfirmed || 0)) / UNIT[chain]);
    };
    ws.onerror = function () { clearTimeout(timer); next(); };
  }

  function progress(el) {
    var chain = el.getAttribute("data-chain"), addr = el.getAttribute("data-addr"), goal = Number(el.getAttribute("data-goal") || 0);
    var out = el.querySelector(".cf-amt"), bar = el.querySelector("progress");
    if (!("WebSocket" in window)) { out.textContent = L.unavailable || "Unavailable"; return; }
    out.textContent = L.checking || "Checking…";
    balance(chain, addr, 0, function (v) {
      if (v === null) { out.textContent = L.unavailable || "Unavailable"; return; }
      var unit = chain === "bch" ? "BCH" : "NEXA";
      var s = v.toLocaleString(document.documentElement.lang || "en", { maximumFractionDigits: chain === "bch" ? 8 : 2 }) + " " + unit;
      if (goal > 0) { s += " / " + goal.toLocaleString(document.documentElement.lang || "en") + " " + unit; if (bar) { bar.max = goal; bar.value = Math.min(v, goal); bar.hidden = false; } }
      out.textContent = s;
    });
  }

  Array.prototype.forEach.call(document.querySelectorAll(".cf-qr[data-uri]"), qr);
  Array.prototype.forEach.call(document.querySelectorAll(".cf-prog[data-addr]"), progress);
})();
