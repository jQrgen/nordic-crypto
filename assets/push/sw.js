/* Nordic Crypto push service worker. Handles a push and opens the story.
   It does not intercept page loads and it does not cache browsing. */
self.addEventListener("install", function (event) {
  event.waitUntil(self.skipWaiting());
});
self.addEventListener("activate", function (event) {
  event.waitUntil(self.clients.claim());
});
self.addEventListener("push", function (event) {
  var data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    data = { title: "Nordic Crypto", body: "" };
  }
  var title = data.title || "Nordic Crypto";
  var options = {
    body: data.body || "",
    icon: "assets/brand/icon-192.png",
    badge: "assets/brand/icon-192.png",
    lang: data.lang || "en",
    tag: data.tag || "nordic-crypto-latest",
    renotify: true,
    data: { url: data.url || "./" }
  };
  event.waitUntil(self.registration.showNotification(title, options));
});
self.addEventListener("notificationclick", function (event) {
  event.notification.close();
  var url = (event.notification.data && event.notification.data.url) || "./";
  event.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (list) {
    for (var i = 0; i < list.length; i++) {
      if (list[i].url === url && "focus" in list[i]) return list[i].focus();
    }
    if (self.clients.openWindow) return self.clients.openWindow(url);
  }));
});
