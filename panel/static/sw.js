/* Service worker de cinéthèque (PWA).
   Met en cache la coquille de l'app pour un démarrage rapide et un affichage
   même hors ligne. Les appels /api/ et /media/ ne sont jamais mis en cache. */
const CACHE = "cinetheque-v32";

self.addEventListener("install", () => self.skipWaiting());

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
  const isHTML = e.request.mode === "navigate" ||
    (e.request.headers.get("accept") || "").includes("text/html");
  if (isHTML) {
    // Pages : réseau d'abord (toujours à jour), cache seulement en secours hors ligne.
    e.respondWith(
      fetch(e.request).then((resp) => {
        caches.open(CACHE).then((c) => c.put(e.request, resp.clone())).catch(() => {});
        return resp;
      }).catch(() => caches.match(e.request).then((c) => c || caches.match("/")))
    );
    return;
  }
  // Autres ressources (versionnées via ?v=) : cache d'abord, réseau en secours.
  e.respondWith(
    caches.match(e.request).then((cached) => cached ||
      fetch(e.request).then((resp) => {
        caches.open(CACHE).then((c) => c.put(e.request, resp.clone())).catch(() => {});
        return resp;
      }))
  );
});
