"""Calcul des statistiques du profil.

Temps total regardé (films + épisodes vus), converti en heures puis en
mois/années ; compteurs (films, séries, épisodes) ; genres, réalisateurs et
acteurs les plus vus ; répartition par année. Le « temps passé » est calculé
automatiquement à partir des durées TMDB × ce qui est marqué vu.
"""
import collections
import json

import db

# Durée moyenne de repli quand TMDB ne fournit pas la durée d'un épisode.
DUREE_EPISODE_DEFAUT = 42
DUREE_FILM_DEFAUT = 100


def _minutes_films():
    rows = db.q(
        """SELECT t.duree, COUNT(v.id) AS vues
           FROM titres t JOIN visionnages v ON v.titre_id = t.id
           WHERE t.type = 'film' GROUP BY t.id"""
    )
    return sum((r["duree"] or DUREE_FILM_DEFAUT) * max(r["vues"], 1) for r in rows)


def _minutes_episodes():
    rows = db.q(
        "SELECT duree, nb_vues FROM episodes WHERE vu = 1"
    )
    return sum((r["duree"] or DUREE_EPISODE_DEFAUT) * max(r["nb_vues"], 1)
               for r in rows)


def duree_lisible(minutes):
    """Convertit des minutes en libellé précis « H h MM » + conversion mois/années."""
    minutes = int(round(minutes))
    h, m = divmod(minutes, 60)
    if h and m:
        texte = f"{h} h {m:02d}"
    elif h:
        texte = f"{h} h"
    else:
        texte = f"{m} min"
    jours = minutes / 1440
    if jours >= 365:
        conv = f"{jours / 365:.1f} an(s)"
    elif jours >= 30:
        conv = f"{jours / 30:.1f} mois"
    elif jours >= 1:
        conv = f"{jours:.1f} jour(s)"
    else:
        conv = f"{minutes} min"
    return {"minutes": minutes, "heures": round(minutes / 60, 1),
            "texte": texte, "converti": conv}


def temps_par_serie():
    rows = db.q(
        """SELECT t.id, t.titre, t.affiche,
                  SUM(COALESCE(e.duree, ?)) AS minutes,
                  COUNT(e.id) AS episodes
           FROM titres t JOIN episodes e ON e.titre_id = t.id
           WHERE t.type = 'serie' AND e.vu = 1
           GROUP BY t.id ORDER BY minutes DESC""",
        (DUREE_EPISODE_DEFAUT,),
    )
    for r in rows:
        r["duree"] = duree_lisible(r["minutes"])
    return rows


def _compte_genres():
    counter = collections.Counter()
    for r in db.q("SELECT genres FROM titres WHERE statut = 'vu' OR id IN "
                  "(SELECT DISTINCT titre_id FROM visionnages)"):
        for g in db.jload(r["genres"], []):
            counter[g] += 1
    return counter.most_common(10)


def resume():
    minutes = _minutes_films() + _minutes_episodes()
    nb_films = db.q1(
        "SELECT COUNT(DISTINCT titre_id) AS n FROM visionnages v "
        "JOIN titres t ON t.id = v.titre_id WHERE t.type = 'film'"
    )["n"]
    nb_series = db.q1(
        "SELECT COUNT(DISTINCT titre_id) AS n FROM episodes WHERE vu = 1"
    )["n"]
    nb_episodes = db.q1(
        "SELECT COALESCE(SUM(MAX(nb_vues,1)),0) AS n FROM episodes WHERE vu = 1"
    )["n"]
    par_annee = db.q(
        """SELECT annee, COUNT(*) AS n FROM titres
           WHERE annee IS NOT NULL AND (statut='vu' OR id IN
                 (SELECT titre_id FROM visionnages))
           GROUP BY annee ORDER BY annee"""
    )
    return {
        "temps_total": duree_lisible(minutes),
        "nb_films": nb_films,
        "nb_series": nb_series,
        "nb_episodes": nb_episodes,
        "genres": [{"nom": g, "n": n} for g, n in _compte_genres()],
        "par_annee": par_annee,
        "series": temps_par_serie(),
    }
