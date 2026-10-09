/* API page: asks each Rostrum server for its version and chain tip over
   WebSocket, and shows the answer with the round-trip time. Runs in the
   reader's browser, so a row shows what that reader can reach. No cookies. */
(function () {
  var TIMEOUT_MS = 8000;
  var table = document.getElementById("electrum-status");
  if (!table || !("WebSocket" in window)) return;
  var button = document.getElementById("electrum-recheck");

  function cell(row, name, text, cls) {
    var td = row.querySelector('[data-f="' + name + '"]');
    td.textContent = text;
    td.className = cls || "";
  }

  function check(row) {
    var url = row.getAttribute("data-url");
    var pending = {};
    var nextId = 1;
    var done = false;
    var ws;

    cell(row, "state", "Checking…");
    cell(row, "height", "–");
    cell(row, "version", "–");
    cell(row, "ms", "–");

    function finish(ok, message) {
      if (done) return;
      done = true;
      clearTimeout(timer);
      if (!ok) cell(row, "state", message || "Down", "bad");
      try { ws.close(); } catch (e) { /* already closed */ }
    }

    function call(method, params) {
      var id = nextId++;
      return new Promise(function (resolve, reject) {
        pending[id] = { resolve: resolve, reject: reject };
        ws.send(JSON.stringify({ jsonrpc: "2.0", id: id, method: method, params: params }));
      });
    }

    var timer = setTimeout(function () { finish(false, "No answer in " + TIMEOUT_MS / 1000 + " s"); }, TIMEOUT_MS);
    try {
      ws = new WebSocket(url);
    } catch (e) {
      finish(false, "Down");
      return;
    }
    ws.onerror = function () { finish(false, "Down"); };
    ws.onclose = function () { finish(false, "Closed"); };
    ws.onmessage = function (event) {
      var msg;
      try { msg = JSON.parse(event.data); } catch (e) { return; }
      var p = pending[msg.id];
      if (!p) return;
      delete pending[msg.id];
      if (msg.error) p.reject(msg.error); else p.resolve(msg.result);
    };
    ws.onopen = function () {
      call("server.version", ["nordiccrypto.no api page", "1.4"]).then(function (version) {
        cell(row, "version", Array.isArray(version) ? version[0] + " (protocol " + version[1] + ")" : String(version));
        var t0 = performance.now();
        return call("blockchain.headers.subscribe", []).then(function (tip) {
          cell(row, "ms", Math.round(performance.now() - t0) + " ms");
          cell(row, "height", tip && tip.height != null ? Number(tip.height).toLocaleString("en") : "?");
          cell(row, "state", "Up", "ok");
          finish(true);
        });
      }).catch(function (err) {
        finish(false, "Error: " + (err && err.message ? err.message : "no tip"));
      });
    };
  }

  function checkAll() {
    [].forEach.call(table.querySelectorAll("tr[data-url]"), check);
  }

  if (button) {
    button.hidden = false;
    button.addEventListener("click", checkAll);
  }
  checkAll();
})();
