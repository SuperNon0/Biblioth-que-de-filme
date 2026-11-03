/* =========================================================================
   cinéthèque — démarrage, chargé en dernier : historique (bouton retour),
   préférences, première page d'après l'adresse, données de fond et
   service worker (démarrage rapide, hors ligne).
   ========================================================================= */
"use strict";

Couches.init();
if ("scrollRestoration" in history) history.scrollRestoration = "manual";
appliquerPrefs();

{
  const { page, sous } = lireHash();
  Nav.aller(page || "accueil", { sous });
}

chargerMesPlateformes();
afficherVersion();
majSideListes();
// Ma bibliothèque (compteur du menu, recherche Ctrl K) : quand le navigateur souffle.
(window.requestIdleCallback || ((f) => setTimeout(f, 1200)))(() => MaBiblio.charger().catch(() => {}));

// « Voir en tant que » : revenir à son propre compte.
$("#imp-stop")?.addEventListener("click", (e) => occupe(e.currentTarget, async () => {
  try {
    await api("/api/impersonate/stop", { method: "POST" });
    await purgeShell();
    location.reload();
  } catch (err) { toastErr(err); }
}));

if ("serviceWorker" in navigator) {
  addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
}
