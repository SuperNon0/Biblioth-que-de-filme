/* Service worker de cinéthèque (PWA).
   Met en cache la coquille de l'app pour un démarrage rapide et un affichage
   même hors ligne. Les appels /api/ et /media/ ne sont jamais mis en cache. */
const CACHE = "cinetheque-v39";

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
    // Pages : la coquille en cache s'affiche INSTANTANÉMENT au lancement, tout
    // en revalidant via le réseau. On laisse au réseau un court délai de grâce
    // (1,2 s) : s'il répond vite (cas d'une mise à jour), on sert la version
    // fraîche ; sinon on sert le cache tout de suite (plus de latence), et le
    // cache est mis à jour en arrière-plan pour le prochain lancement.
    e.respondWith((async () => {
      const cache = await caches.open(CACHE);
      const cached = await cache.match(e.request);
      const net = fetch(e.request).then((resp) => {
        if (resp && resp.ok && resp.type === "basic") {
          cache.put(e.request, resp.clone()).catch(() => {});
        }
        return resp;
      }).catch(() => null);
      if (cached) {
        const fast = await Promise.race([
          net, new Promise((r) => setTimeout(() => r("timeout"), 1200)),
        ]);
        return (fast && fast !== "timeout") ? fast : cached;
      }
      return (await net) || (await cache.match("/")) || fetch(e.request);
    })());
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
