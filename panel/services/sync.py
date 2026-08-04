"""Synchronisation TMDB → base de données.

Traduit une fiche TMDB (film ou série) en lignes de la base : insertion du
titre, mise en cache de l'affiche, et pour les séries, remplissage des
épisodes saison par saison (nom, résumé, image, durée, date de diffusion).
"""
import json
import threading
import time

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


def _cache_affiche(url):
    if not url:
        return None
    name = posters.cache(current_app, url)
    return posters.local_url(name) or url


def upsert_titre(detail, statut="a_voir"):
    """Insère (ou récupère) un titre depuis une fiche TMDB détaillée.

    Renvoie l'identifiant local du titre.
    """
    existing = db.q1(
        "SELECT id FROM titres WHERE tmdb_id = ? AND type = ?",
        (detail.get("tmdb_id"), detail["type"]),
    )
    now = int(time.time())
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
    )
    if existing:
        db.run(
            """UPDATE titres SET titre=?, annee=?, date_sortie=?, resume=?,
               genres=?, duree=?, affiche=COALESCE(?, affiche), fond=?,
               bande_annonce=?, note_tmdb=?, pays=?, plateformes=?, casting=?,
               equipe=?, nb_saisons=COALESCE(?, nb_saisons), maj=? WHERE id=?""",
            fields[2:] + (now, existing["id"]),
        )
        return existing["id"]
    return db.run(
        """INSERT INTO titres
           (tmdb_id, type, titre, annee, date_sortie, resume, genres, duree,
            affiche, fond, bande_annonce, note_tmdb, pays, plateformes, casting,
            equipe, nb_saisons, statut, date_ajout, maj)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        fields + (statut, now, now),
    )


def sync_episodes(titre_id, tmdb, tmdb_id, saisons):
    """Remplit/complète les épisodes d'une série pour toutes ses saisons.

    Conserve l'état « vu » existant : on n'écrase que les métadonnées.
    Résilient : si l'appel d'une saison échoue (réseau/timeout), on passe à la
    suivante au lieu de tout interrompre — évite de n'avoir que la saison 1.
    Renvoie le nombre de saisons effectivement récupérées.
    """
    ok = 0
    for saison in saisons:
        num = saison["numero"]
        try:
            episodes = tmdb.season(tmdb_id, num)
        except TMDBError:
            continue  # une saison qui échoue ne bloque pas les autres
        ok += 1
        for ep in episodes:
            db.run(
                """INSERT INTO episodes
                   (titre_id, saison, numero, nom, resume, image, duree, date_diff)
                   VALUES (?,?,?,?,?,?,?,?)
                   ON CONFLICT(titre_id, saison, numero) DO UPDATE SET
                     nom=excluded.nom, resume=excluded.resume,
                     image=excluded.image, duree=excluded.duree,
                     date_diff=excluded.date_diff""",
                (titre_id, ep["saison"], ep["numero"], ep["nom"],
                 ep["resume"], ep["image"], ep["duree"], ep["date_diff"]),
            )
    return ok
