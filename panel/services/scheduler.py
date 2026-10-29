"""Planificateur de fond : détecte les nouveautés et envoie les notifications.

Un thread tourne en arrière-plan et, à intervalle régulier :
- resynchronise les épisodes des séries suivies, de TOUS les comptes (nouvelle
  saison, dates des épisodes à venir) ;
- si Discord est activé, notifie aux super-admins les **nouveaux épisodes**
  diffusés depuis la dernière vérification et les **alertes de sortie** (film
  au cinéma / dispo en streaming).

Chaque notification n'est envoyée qu'une fois (drapeaux ``episodes.notifie`` et
``alertes.vue``, posés seulement si l'envoi a réussi). Le thread ne plante
jamais : une série ou une alerte en erreur est journalisée puis ignorée.
"""
import logging
import threading
import time
from datetime import date, timedelta

import db
import settings_store
from context import get_tmdb
from services import notifications, sync
from tmdb import TMDBError

log = logging.getLogger("cinetheque.scheduler")
_started = False

# Un épisode sorti depuis plus longtemps n'est plus une « nouveauté » : c'est
# un rattrapage (saison complétée après coup, envoi Discord en échec…). Il est
# marqué notifié sans message, au lieu d'une rafale de dizaines de messages.
FENETRE_NOTIF = timedelta(days=7)


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
    # Reprend le rythme du dernier cycle (mémorisé en base) : un redémarrage ou
    # une mise à jour ne relance pas aussitôt des centaines d'appels TMDB.
    try:
        dernier = float(db.get_setting("planif_dernier_cycle") or 0)
    except (TypeError, ValueError):
        dernier = 0
    time.sleep(min(interval, max(20, dernier + interval - time.time())))
    while True:
        try:
            with app.app_context():
                run_checks()
        except Exception as exc:  # noqa: BLE001 - le thread doit survivre à tout
            log.warning("Cycle de notifications échoué : %s", exc)
        finally:
            # Jamais de transaction (donc de verrou d'écriture) laissée ouverte
            # par ce thread, qui garde sa connexion pendant des heures.
            db.rollback_open()
        try:
            db.set_setting("planif_dernier_cycle", str(int(time.time())))
        except Exception as exc:  # noqa: BLE001
            log.warning("Heure du cycle non mémorisée : %s", exc)
        time.sleep(interval)


def run_checks():
    """Un cycle : synchronise les séries de tous les comptes ; les notifications
    (super-admins seulement) ne partent que si Discord est activé."""
    notifier = bool(settings_store.get("notif_discord_enabled"))
    _check_episodes(notifier)
    if notifier:
        _check_alertes()


def _saisons_a_rafraichir(titre_id, saisons):
    """Saisons à recharger : nombre d'épisodes différent de la base, épisodes
    à venir ou sans date, et toujours la dernière. Les saisons terminées et
    complètes ne sont plus rechargées à chaque cycle (~5× moins d'appels)."""
    if not saisons:
        return []
    en_base = {r["saison"]: r["n"] for r in db.q(
        "SELECT saison, COUNT(*) AS n FROM episodes WHERE titre_id = ? GROUP BY saison",
        (titre_id,))}
    a_suivre = {r["saison"] for r in db.q(
        "SELECT DISTINCT saison FROM episodes WHERE titre_id = ? AND (date_diff IS NULL "
        "OR date_diff = '' OR date_diff > ?)", (titre_id, date.today().isoformat()))}
    derniere = max(s["numero"] for s in saisons)
    return [s for s in saisons if s["numero"] == derniere or s["numero"] in a_suivre
            or en_base.get(s["numero"]) != s.get("nb_episodes")]


def _check_episodes(notifier):
    # On inclut les séries déjà **entièrement vues** : quand une nouvelle
    # saison sort (ex. « Beauty in Black » S3 après S1+S2 vues), il faut la
    # détecter, la notifier, et repasser la série « en cours » pour qu'elle
    # revienne dans « Reprendre » sans avoir à la rechercher. Les séries des
    # membres sont synchronisées aussi, mais ne déclenchent PAS de notification.
    series = db.q(
        """SELECT t.id, t.tmdb_id, t.titre, t.affiche_url, t.statut,
                  c.role = 'super_admin' AS notifiable
           FROM titres t JOIN comptes c ON c.id = t.compte_id
           WHERE t.type='serie' AND t.statut IN ('en_cours','a_voir','vu')
           AND t.tmdb_id IS NOT NULL"""
    )
    tmdb = get_tmdb()
    tmdb.cache = False  # n'évince pas du cache ce que l'interface a chargé
    for s in series:
        try:
            _sync_serie(tmdb, s)
            if notifier and s["notifiable"]:
                _notifier_episodes(s)
        except TMDBError:
            continue
        except Exception as exc:  # noqa: BLE001 - ex. série supprimée pendant le cycle
            db.rollback_open()
            log.warning("Série « %s » ignorée pour ce cycle : %s", s["titre"], exc)


def _sync_serie(tmdb, s):
    detail = tmdb.tv_light(s["tmdb_id"])
    saisons = detail.get("saisons", [])
    sync.sync_episodes(s["id"], tmdb, s["tmdb_id"], _saisons_a_rafraichir(s["id"], saisons))
    if detail.get("nb_saisons"):
        db.run("UPDATE titres SET nb_saisons=? WHERE id=?", (detail["nb_saisons"], s["id"]))
    # Une série « vue » qui a désormais des épisodes SORTIS non vus (nouvelle
    # saison diffusée) repasse « en cours » : elle réapparaît dans « Reprendre ».
    if s["statut"] == "vu":
        reste = db.q1(f"SELECT 1 FROM episodes WHERE titre_id=? AND vu=0 "
                      f"AND {sync.ep_diffuse_sql()} LIMIT 1", (s["id"],))
        if reste:
            db.run("UPDATE titres SET statut='en_cours' WHERE id=?", (s["id"],))
    # Renseigne l'URL publique de l'affiche pour les séries ajoutées avant
    # (les notifications peuvent alors inclure le poster).
    if not s["affiche_url"] and detail.get("affiche"):
        db.run("UPDATE titres SET affiche_url=? WHERE id=?", (detail["affiche"], s["id"]))
        s["affiche_url"] = detail["affiche"]


def _notifier_episodes(s):
    today = date.today()
    seuil = (today - FENETRE_NOTIF).isoformat()
    nouveaux = db.q(
        """SELECT id, saison, numero, nom, image, date_diff FROM episodes
           WHERE titre_id=? AND notifie=0 AND date_diff IS NOT NULL
           AND date_diff != '' AND date_diff <= ?""",
        (s["id"], today.isoformat()),
    )
    for e in nouveaux:
        if e["date_diff"] < seuil:
            db.run("UPDATE episodes SET notifie=1 WHERE id=?", (e["id"],))
            continue
        code = f"S{e['saison']:02d}E{e['numero']:02d}"
        titre = f"{s['titre']} — nouvel épisode"
        msg = f"📺 {s['titre']} {code}" + (f" — {e['nom']}" if e["nom"] else "")
        envoye = notifications.notify("episode", titre, msg, {
            "serie": s["titre"], "code": code, "titre": e["nom"] or "",
            "saison": str(e["saison"]), "episode": str(e["numero"]),
            # affiche = poster de la série ; image = vignette de l'épisode.
            "affiche": s["affiche_url"] or "",
            "image": e["image"] or s["affiche_url"] or "",
        })
        if envoye:  # échec (botpanel injoignable) : nouvel essai au cycle suivant
            db.run("UPDATE episodes SET notifie=1 WHERE id=?", (e["id"],))


# Modes qui comptent comme « dispo en streaming » (pas la location ni l'achat).
_MODES_STREAMING = ("Abonnement", "Gratuit", "Avec pubs")


def _check_alertes():
    tmdb = get_tmdb()
    tmdb.cache = False
    # Seules les alertes des comptes super-admin sont notifiées.
    alertes = db.q(
        """SELECT a.id, a.canal, a.titre_id, t.titre, t.tmdb_id, t.type,
                  t.date_sortie, t.affiche_url
           FROM alertes a JOIN titres t ON t.id = a.titre_id
           WHERE a.vue = 0
           AND t.compte_id IN (SELECT id FROM comptes WHERE role='super_admin')"""
    )
    for a in alertes:
        try:
            _alerte(tmdb, a)
        except TMDBError:
            continue
        except Exception as exc:  # noqa: BLE001
            db.rollback_open()
            log.warning("Alerte « %s » ignorée pour ce cycle : %s", a["titre"], exc)


def _alerte(tmdb, a):
    today = date.today().isoformat()
    affiche = a["affiche_url"] or ""
    if a["canal"] == "cine":
        sortie = a["date_sortie"]
        if a["type"] == "film" and a["tmdb_id"]:
            # Date de sortie dans les salles de la région (France), mise à jour
            # en base : elle suit aussi un éventuel report.
            locale = tmdb.sortie_salles(a["tmdb_id"])
            if locale and locale != sortie:
                db.run("UPDATE titres SET date_sortie=? WHERE id=?", (locale, a["titre_id"]))
                sortie = locale
        if sortie and sortie <= today:
            if notifications.notify("cine", f"{a['titre']} — au cinéma",
                                    f"🎬 {a['titre']} est maintenant au cinéma !",
                                    {"titre": a["titre"], "canal": "cinéma",
                                     "affiche": affiche, "image": affiche}):
                db.run("UPDATE alertes SET vue=1 WHERE id=?", (a["id"],))
    elif a["canal"] == "streaming" and a["tmdb_id"]:
        detail = (tmdb.movie(a["tmdb_id"]) if a["type"] == "film"
                  else tmdb.tv(a["tmdb_id"]))
        if not affiche and detail.get("affiche"):
            affiche = detail["affiche"]  # backfill pour un titre ajouté avant
        plateformes = [p for p in detail.get("plateformes") or []
                       if p.get("mode") in _MODES_STREAMING]
        if plateformes:
            noms = ", ".join(p["nom"] for p in plateformes[:3])
            if notifications.notify("streaming", f"{a['titre']} — en streaming",
                                    f"📺 {a['titre']} est dispo sur {noms}.",
                                    {"titre": a["titre"], "plateformes": noms,
                                     "affiche": affiche, "image": affiche}):
                db.run("UPDATE alertes SET vue=1 WHERE id=?", (a["id"],))
