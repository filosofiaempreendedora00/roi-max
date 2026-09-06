/* Service worker: recebe o push mesmo com o app fechado e leva o toque
   direto ao mercado da Betfair. É o que fecha o requisito de timing. */

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));

self.addEventListener("push", (event) => {
  if (!event.data) return;
  let d;
  try {
    d = event.data.json();
  } catch {
    d = { title: "ROI Max", body: event.data.text() };
  }
  event.waitUntil(
    self.registration.showNotification(d.title || "ROI Max", {
      body: d.body || "",
      icon: "/icon-192.png",
      badge: "/icon-192.png",
      tag: d.tag,
      renotify: true,
      requireInteraction: true,
      vibrate: [60, 40, 60],
      data: d,
      actions: [
        { action: "open", title: "Abrir na Betfair" },
        { action: "app", title: "Ver no app" },
      ],
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const d = event.notification.data || {};
  // O toque na notificação vai direto ao mercado; "Ver no app" abre o ROI Max.
  const target = event.action === "app" ? d.url || "/" : d.deeplink || d.url || "/";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      if (event.action !== "app") return self.clients.openWindow(target);
      for (const c of list) if ("focus" in c) return c.focus();
      return self.clients.openWindow(target);
    })
  );
});
