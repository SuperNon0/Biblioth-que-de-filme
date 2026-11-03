"""Synchronisation TMDB → base de données.

Traduit une fiche TMDB (film ou série) en lignes de la base : insertion du
titre, mise en cache de l'affiche, et pour les séries, remplissage des
épisodes saison par saison (nom, résumé, image, durée, date de diffusion).
"""
import json
import threading
import time
from datetime import date

from flask import current_app

import db
from services import posters
from tmdb import TMDBError

# Séries dont les épisodes se remplissent en arrière-plan (ajout non bloquant).
# Permet à la fiche de montrer « chargement… » au lieu de re-synchroniser.
_syncing = set()
_syncing_lock = threading.Lock()


def mark_syncing(titre_id):
    with _syncing_lock:
        _syncing.add(titre_id)


def done_syncing(titre_id):
    with _syncing_lock:
        _syncing.discard(titre_id)


def is_syncing(titre_id):
    with _syncing_lock:
        return titre_id in _syncing


# ── Épisodes « diffusés » ────────────────────────────────────────────────────
# Un épisode à venir ne doit ni être coché par « Vu » (série, saison), ni
# compter dans la progression : sinon la nouvelle saison, une fois sortie, ne
# revient jamais dans « Reprendre ». Règle : date connue → diffusé si passée ;
# date inconnue (TMDB « TBA ») → diffusé seulement si un épisode SUIVANT est
# déjà sorti, ou si la série n'a aucune date (vieilles fiches incomplètes).
def flag_diffuses(eps, today=None):
    """Pose ``diffuse`` (bool) sur les épisodes d'UNE série, triés par
    (saison, numéro). Renvoie la liste."""
    today = today or date.today().isoformat()
    sans_dates = not any(e.get("date_diff") for e in eps)
    suivant_sorti = False
    for e in reversed(eps):
        d = e.get("date_diff")
        if d:
            e["diffuse"] = d <= today
            suivant_sorti = suivant_sorti or e["diffuse"]
        else:
            e["diffuse"] = suivant_sorti or sans_dates
    return eps


def ep_diffuse_sql(e="episodes"):
    """Même règle en SQL : expression vraie si l'épisode (table ou alias ``e``)
    est déjà diffusé. Sans paramètre (date du jour calculée par SQLite)."""
    jour = "date('now','localtime')"

    def connue(t):
        return f"({t}.date_diff IS NOT NULL AND {t}.date_diff != '')"
    suivant = (f"EXISTS (SELECT 1 FROM episodes _s WHERE _s.titre_id = {e}.titre_id "
               f"AND {connue('_s')} AND _s.date_diff <= {jour} AND (_s.saison > {e}.saison "
               f"OR (_s.saison = {e}.saison AND _s.numero > {e}.numero)))")
    aucune = (f"NOT EXISTS (SELECT 1 FROM episodes _d WHERE _d.titre_id = {e}.titre_id "
              f"AND {connue('_d')})")
    return (f"(({connue(e)} AND {e}.date_diff <= {jour}) "
            f"OR (NOT {connue(e)} AND ({suivant} OR {aucune})))")


def _cache_affiche(url):
    if not url:
        return None
    name = posters.cache(current_app, url)
    return posters.local_url(name) or url


def upsert_titre(detail, statut="a_voir", compte_id=None):
    """Insère (ou récupère) un titre depuis une fiche TMDB détaillée.

    Le titre appartient à ``compte_id`` (cloisonnement) : l'unicité et la
    recherche d'existant sont faites PAR compte. Renvoie l'identifiant local.
    """
    existing = db.q1(
        "SELECT id FROM titres WHERE tmdb_id = ? AND type = ? AND compte_id IS ?",
        (detail.get("tmdb_id"), detail["type"], compte_id),
    )
    now = int(time.time())
    # affiche = chemin local mis en cache (pour l'app) ; affiche_url = l'URL TMDB
    # publique d'origine (pour les notifications Discord, joignables par Discord).
    affiche = _cache_affiche(detail.get("affiche"))
    fields = (
        detail.get("tmdb_id"), detail["type"], detail["titre"],
        detail.get("annee"), detail.get("date_sortie"), detail.get("resume"),
        json.dumps(detail.get("genres", []), ensure_ascii=False),
        detail.get("duree"), affiche, detail.get("fond"),
        detail.get("bande_annonce"), detail.get("note_tmdb"),
        detail.get("pays"),
        json.dumps(detail.get("plateformes", []), ensure_ascii=False),
        json.dumps(detail.get("casting", []), ensure_ascii=False),
        json.dumps(detail.get("equipe", []), ensure_ascii=False),
        detail.get("nb_saisons"),  # séries : sert à détecter une sync incomplète
        detail.get("affiche"),     # URL TMDB publique (notifs Discord)
    )
    if existing:
        db.run(
            """UPDATE titres SET titre=?, annee=?, date_sortie=?, resume=?,
               genres=?, duree=?, affiche=COALESCE(?, affiche), fond=?,
               bande_annonce=?, note_tmdb=?, pays=?, plateformes=?, casting=?,
               equipe=?, nb_saisons=COALESCE(?, nb_saisons),
               affiche_url=COALESCE(?, affiche_url), maj=? WHERE id=?""",
            fields[2:] + (now, existing["id"]),
        )
        return existing["id"]
    return db.run(
        """INSERT INTO titres
           (tmdb_id, type, titre, annee, date_sortie, resume, genres, duree,
            affiche, fond, bande_annonce, note_tmdb, pays, plateformes, casting,
            equipe, nb_saisons, affiche_url, compte_id, statut, date_ajout, maj)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        fields + (compte_id, statut, now, now),
    )


def sync_episodes(titre_id, tmdb, tmdb_id, saisons):
    """Remplit/complète les épisodes d'une série pour toutes ses saisons.

    Conserve l'état « vu » existant : on n'écrase que les métadonnées.
    Résilient : si l'appel d'une saison échoue (réseau/timeout), on passe à la
    suivante au lieu de tout interrompre — évite de n'avoir que la saison 1.
    Renvoie le nombre de saisons effectivement récupérées.
    """
    # Première synchro (ajout par liste, alerte, import…) : on retient qu'elle
    # l'est pour poser ensuite la baseline anti-spam des notifications.
    premiere = db.q1("SELECT 1 FROM episodes WHERE titre_id = ? LIMIT 1",
                     (titre_id,)) is None
    ok = 0
    conn = db.connect()
    for saison in saisons:
        num = saison["numero"]
        try:
            episodes = tmdb.season(tmdb_id, num)
        except TMDBError:
            continue  # une saison qui échoue ne bloque pas les autres
        ok += 1
        # Une transaction par saison (et non un commit par épisode), et les
        # lignes inchangées ne sont pas réécrites : la resynchro de toute la
        # bibliothèque tient le verrou d'écriture ~6× moins longtemps.
        with conn:
            conn.executemany(
                """INSERT INTO episodes
                   (titre_id, saison, numero, nom, resume, image, duree, date_diff)
                   VALUES (?,?,?,?,?,?,?,?)
                   ON CONFLICT(titre_id, saison, numero) DO UPDATE SET
                     nom=excluded.nom, resume=excluded.resume,
                     image=excluded.image, duree=excluded.duree,
                     date_diff=excluded.date_diff
                   WHERE episodes.nom IS NOT excluded.nom
                      OR episodes.resume IS NOT excluded.resume
                      OR episodes.image IS NOT excluded.image
                      OR episodes.duree IS NOT excluded.duree
                      OR episodes.date_diff IS NOT excluded.date_diff""",
                [(titre_id, ep["saison"], ep["numero"], ep["nom"], ep["resume"],
                  ep["image"], ep["duree"], ep["date_diff"]) for ep in episodes])
            nums = [ep["numero"] for ep in episodes if ep["saison"] == num]
            if nums:
                # Épisodes que TMDB a retirés ou renumérotés : jamais vus, ils
                # empêchaient la série de passer « vue ». Les vus restent.
                conn.execute(
                    f"DELETE FROM episodes WHERE titre_id = ? AND saison = ? AND vu = 0 "
                    f"AND nb_vues = 0 AND numero NOT IN ({','.join('?' * len(nums))})",
                    (titre_id, num, *nums))
    if premiere:
        # Baseline anti-spam : les épisodes déjà diffusés ne déclenchent pas de
        # notification « nouvel épisode » (sinon rafale de toute la série).
        db.run("UPDATE episodes SET notifie=1 WHERE titre_id=? AND "
               "date_diff IS NOT NULL AND date_diff <= ?",
               (titre_id, date.today().isoformat()))
    return ok
