// Opt-in for browser notifications. One button turns them on; the same button turns them off.
// The Worker URL and the strings come from window.NC_PUSH, injected by the build.
(function () {
  var cfg = window.NC_PUSH || {};
  var box = document.querySelector(".pushopt");
  if (!box) return;
  var S = cfg.strings || {};
  var btn = box.querySelector(".push-btn");
  var status = box.querySelector(".push-status");
  var root = box.getAttribute("data-root") || "./";
  var all = box.querySelector('input[value="ALL"]');
  var boxes = [].slice.call(box.querySelectorAll('input[name="country"]'));
  var LS = "nc_push_countries";

  function say(text) { if (status) status.textContent = text || ""; }
  function countries() {
    if (!all || all.checked) return [];
    return boxes.filter(function (el) { return el.value !== "ALL" && el.checked; }).map(function (el) { return el.value; });
  }
  function reflect(list) {
    var on = !list || !list.length;
    boxes.forEach(function (el) {
      if (el.value === "ALL") el.checked = on;
      else el.checked = !on && list.indexOf(el.value) >= 0;
    });
  }
  function remember() {
    try { localStorage.setItem(LS, JSON.stringify(countries())); } catch (e) {}
  }
  function recalled() {
    try {
      var raw = localStorage.getItem(LS);
      if (raw) reflect(JSON.parse(raw));
    } catch (e) {}
  }
  function b64url(buf) {
    var bytes = new Uint8Array(buf), s = "";
    for (var i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
    return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
  }
  function keyBytes(b64) {
    var pad = b64.length % 4 === 0 ? "" : "====".slice(b64.length % 4);
    var bin = atob(b64.replace(/-/g, "+").replace(/_/g, "/") + pad);
    var out = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }
  function setButton(on) {
    btn.textContent = on ? (S.off || "Turn off notifications") : (S.on || "Turn on notifications");
    btn.setAttribute("data-on", on ? "1" : "0");
  }
  function supported() {
    return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
  }

  boxes.forEach(function (el) {
    el.addEventListener("change", function () {
      if (el.value === "ALL" && el.checked) {
        boxes.forEach(function (other) { if (other !== el) other.checked = false; });
      } else if (el.value !== "ALL" && el.checked && all) {
        all.checked = false;
      } else if (el.value !== "ALL" && !countries().length && all) {
        all.checked = true;
      }
      remember();
      if (btn.getAttribute("data-on") === "1") save(true);
    });
  });
  recalled();

  function endpoint() { return (cfg.endpoint || "").replace(/\/$/, ""); }

  function save(alreadyOn) {
    var ep = endpoint();
    if (!ep) { say(S.unavailable || ""); return Promise.resolve(); }
    say(S.working || "");
    return navigator.serviceWorker.ready.then(function (reg) {
      return reg.pushManager.getSubscription();
    }).then(function (sub) {
      if (!sub) return;
      return fetch(ep + "/api/push/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify({
          endpoint: sub.endpoint,
          keys: { p256dh: b64url(sub.getKey("p256dh")), auth: b64url(sub.getKey("auth")) },
          lang: cfg.lang || "en",
          countries: countries()
        })
      }).then(function (r) {
        if (!r.ok) throw new Error("save");
        if (alreadyOn) say(S.saved || S.on_status || "");
      });
    }).catch(function () { say(S.fail || ""); });
  }

  function turnOn() {
    var ep = endpoint();
    if (!ep) { say(S.unavailable || ""); return; }
    if (!supported()) { say(S.unsupported || ""); return; }
    say(S.working || "");
    Notification.requestPermission().then(function (perm) {
      if (perm !== "granted") { say(S.denied || ""); return; }
      return navigator.serviceWorker.register(root + "sw.js").then(function () {
        return navigator.serviceWorker.ready;
      }).then(function (reg) {
        return fetch(ep + "/api/push/config", { headers: { Accept: "application/json" } }).then(function (r) {
          if (!r.ok) throw new Error("config");
          return r.json();
        }).then(function (conf) {
          if (!conf.vapid_public_key) throw new Error("config");
          return reg.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: keyBytes(conf.vapid_public_key)
          });
        });
      }).then(function (sub) {
        return fetch(ep + "/api/push/subscribe", {
          method: "POST",
          headers: { "Content-Type": "application/json", "Accept": "application/json" },
          body: JSON.stringify({
            endpoint: sub.endpoint,
            keys: { p256dh: b64url(sub.getKey("p256dh")), auth: b64url(sub.getKey("auth")) },
            lang: cfg.lang || "en",
            countries: countries()
          })
        }).then(function (r) {
          if (!r.ok) throw new Error("subscribe");
          remember();
          setButton(true);
          say(S.on_status || "");
        });
      });
    }).catch(function () { say(S.fail || ""); });
  }

  function turnOff() {
    say(S.working || "");
    var done = function () { setButton(false); say(S.off_status || ""); };
    var local = supported()
      ? navigator.serviceWorker.getRegistration().then(function (reg) {
          return reg ? reg.pushManager.getSubscription() : null;
        }).then(function (sub) {
          if (!sub) return;
          var ep = endpoint();
          var remote = ep ? fetch(ep + "/api/push/unsubscribe", {
            method: "POST",
            headers: { "Content-Type": "application/json", "Accept": "application/json" },
            body: JSON.stringify({ endpoint: sub.endpoint })
          }).catch(function () {}) : Promise.resolve();
          return remote.then(function () { return sub.unsubscribe(); });
        })
      : Promise.resolve();
    local.then(done).catch(function () { say(S.fail || ""); });
  }

  btn.addEventListener("click", function () {
    if (btn.getAttribute("data-on") === "1") turnOff();
    else turnOn();
  });

  if (!supported()) {
    say(S.unsupported || "");
    return;
  }
  navigator.serviceWorker.getRegistration().then(function (reg) {
    return reg ? reg.pushManager.getSubscription() : null;
  }).then(function (sub) {
    if (sub) { setButton(true); say(S.on_status || ""); }
  }).catch(function () {});
})();
