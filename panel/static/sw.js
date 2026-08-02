/* Service worker de cinéthèque (PWA).
   Met en cache la coquille de l'app pour un démarrage rapide et un affichage
   même hors ligne. Les appels /api/ et /media/ ne sont jamais mis en cache. */
const CACHE = "cinetheque-v1";
const SHELL = ["/", "/static/style.css", "/static/app.js", "/static/fonts.css",
               "/static/favicon.svg", "/static/logo.svg"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" ||
      url.pathname.startsWith("/api/") || url.pathname.startsWith("/media/")) {
    return;
  }
  e.respondWith(
    caches.match(e.request).then((cached) => {
      const network = fetch(e.request).then((resp) => {
        caches.open(CACHE).then((c) => c.put(e.request, resp.clone())).catch(() => {});
        return resp;
      }).catch(() => cached);
      return cached || network;
    })
  );
});
