"""Planificateur de fond : détecte les nouveautés et envoie les notifications.

Un thread tourne en arrière-plan et, à intervalle régulier :
- resynchronise les épisodes des séries « en cours / à voir » et notifie les
  **nouveaux épisodes** diffusés depuis la dernière vérification ;
- notifie les **alertes de sortie** (film au cinéma / dispo en streaming).

Chaque notification n'est envoyée qu'une fois (drapeaux ``episodes.notifie`` et
``alertes.vue``). Le thread ne plante jamais : toute erreur est journalisée.
"""
import logging
import threading
import time
from datetime import date

import db
import settings_store
from context import get_tmdb
from services import notifications, sync
from tmdb import TMDBError

log = logging.getLogger("cinetheque.scheduler")
_started = False


def start(app, interval_hours=6):
    """Démarre le thread de vérification (une seule fois)."""
    global _started
    if _started:
        return
    _started = True
    thread = threading.Thread(target=_loop, args=(app, interval_hours * 3600),
                              daemon=True, name="cinetheque-scheduler")
    thread.start()


def _loop(app, interval):
    time.sleep(20)  # laisse l'app finir de démarrer
    while True:
        try:
            with app.app_context():
                run_checks()
        except Exception as exc:  # noqa: BLE001 - le thread doit survivre à tout
            log.warning("Cycle de notifications échoué : %s", exc)
        time.sleep(interval)


def run_checks():
    """Un cycle : n'exécute rien si les notifications Discord ne sont pas activées."""
    if not settings_store.get("notif_discord_enabled"):
        return
    _check_episodes()
    _check_alertes()


def _check_episodes():
    today = date.today().isoformat()
    series = db.q(
        """SELECT id, tmdb_id, titre FROM titres
           WHERE type='serie' AND statut IN ('en_cours','a_voir')
           AND tmdb_id IS NOT NULL"""
    )
    tmdb = get_tmdb()
    for s in series:
        try:
            detail = tmdb.tv(s["tmdb_id"])
            sync.sync_episodes(s["id"], tmdb, s["tmdb_id"], detail.get("saisons", []))
        except TMDBError:
            continue
        nouveaux = db.q(
            """SELECT id, saison, numero, nom FROM episodes
               WHERE titre_id=? AND notifie=0 AND date_diff IS NOT NULL
               AND date_diff != '' AND date_diff <= ?""",
            (s["id"], today),
        )
        for e in nouveaux:
            code = f"S{e['saison']:02d}E{e['numero']:02d}"
            titre = f"{s['titre']} — nouvel épisode"
            msg = f"📺 {s['titre']} {code}" + (f" — {e['nom']}" if e["nom"] else "")
            notifications.notify("episode", titre, msg, {
                "serie": s["titre"], "code": code, "titre": e["nom"] or "",
                "saison": str(e["saison"]), "episode": str(e["numero"]),
            })
            db.run("UPDATE episodes SET notifie=1 WHERE id=?", (e["id"],))


def _check_alertes():
    today = date.today().isoformat()
    tmdb = get_tmdb()
    alertes = db.q(
        """SELECT a.id, a.canal, t.titre, t.tmdb_id, t.type, t.date_sortie
           FROM alertes a JOIN titres t ON t.id = a.titre_id
           WHERE a.vue = 0"""
    )
    for a in alertes:
        if a["canal"] == "cine":
            if a["date_sortie"] and a["date_sortie"] <= today:
                notifications.notify("cine", f"{a['titre']} — au cinéma",
                                     f"🎬 {a['titre']} est maintenant au cinéma !",
                                     {"titre": a["titre"], "canal": "cinéma"})
                db.run("UPDATE alertes SET vue=1 WHERE id=?", (a["id"],))
        elif a["canal"] == "streaming" and a["tmdb_id"]:
            try:
                detail = (tmdb.movie(a["tmdb_id"]) if a["type"] == "film"
                          else tmdb.tv(a["tmdb_id"]))
            except TMDBError:
                continue
            plateformes = detail.get("plateformes") or []
            if plateformes:
                noms = ", ".join(p["nom"] for p in plateformes[:3])
                notifications.notify("streaming", f"{a['titre']} — en streaming",
                                     f"📺 {a['titre']} est dispo sur {noms}.",
                                     {"titre": a["titre"], "plateformes": noms})
                db.run("UPDATE alertes SET vue=1 WHERE id=?", (a["id"],))
