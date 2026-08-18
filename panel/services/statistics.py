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


def _minutes_films(compte_id):
    rows = db.q(
        """SELECT t.duree, COUNT(v.id) AS vues
           FROM titres t JOIN visionnages v ON v.titre_id = t.id
           WHERE t.type = 'film' AND t.compte_id = ? GROUP BY t.id""",
        (compte_id,)
    )
    return sum((r["duree"] or DUREE_FILM_DEFAUT) * max(r["vues"], 1) for r in rows)


def _minutes_episodes(compte_id):
    rows = db.q(
        """SELECT e.duree, e.nb_vues FROM episodes e JOIN titres t ON t.id = e.titre_id
           WHERE e.vu = 1 AND t.compte_id = ?""", (compte_id,)
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


def temps_serie(titre_id):
    """Temps passé (minutes vues, revisionnages inclus) sur une série précise,
    pour l'afficher sur sa fiche. Renvoie le libellé, le nombre d'épisodes vus,
    et ``fois`` = nombre de fois où la série entière a été vue (comme « vu ×N »
    pour les films) — le min des revisionnages, uniquement si elle est complète."""
    row = db.q1(
        """SELECT SUM(COALESCE(duree, ?) * MAX(nb_vues, 1)) AS minutes,
                  COUNT(id) AS episodes, MIN(nb_vues) AS mini
           FROM episodes WHERE titre_id = ? AND vu = 1""",
        (DUREE_EPISODE_DEFAUT, titre_id),
    )
    total = db.q1("SELECT COUNT(*) AS n FROM episodes WHERE titre_id = ?",
                  (titre_id,))["n"] or 0
    minutes = (row and row["minutes"]) or 0
    seen = (row and row["episodes"]) or 0
    info = duree_lisible(minutes)
    info["episodes"] = seen
    info["fois"] = (row["mini"] or 0) if (total and seen >= total) else 0
    return info


def _compte_genres(compte_id):
    counter = collections.Counter()
    for r in db.q("SELECT genres FROM titres WHERE compte_id = ? AND (statut = 'vu' "
                  "OR id IN (SELECT DISTINCT titre_id FROM visionnages))", (compte_id,)):
        for g in db.jload(r["genres"], []):
            counter[g] += 1
    return counter.most_common(10)


def resume(compte_id):
    minutes = _minutes_films(compte_id) + _minutes_episodes(compte_id)
    nb_films = db.q1(
        "SELECT COUNT(DISTINCT titre_id) AS n FROM visionnages v "
        "JOIN titres t ON t.id = v.titre_id WHERE t.type = 'film' AND t.compte_id = ?",
        (compte_id,)
    )["n"]
    nb_series = db.q1(
        "SELECT COUNT(DISTINCT e.titre_id) AS n FROM episodes e "
        "JOIN titres t ON t.id = e.titre_id WHERE e.vu = 1 AND t.compte_id = ?",
        (compte_id,)
    )["n"]
    nb_episodes = db.q1(
        "SELECT COALESCE(SUM(MAX(e.nb_vues,1)),0) AS n FROM episodes e "
        "JOIN titres t ON t.id = e.titre_id WHERE e.vu = 1 AND t.compte_id = ?",
        (compte_id,)
    )["n"]
    par_annee = db.q(
        """SELECT annee, COUNT(*) AS n FROM titres
           WHERE compte_id = ? AND annee IS NOT NULL AND (statut='vu' OR id IN
                 (SELECT titre_id FROM visionnages))
           GROUP BY annee ORDER BY annee""",
        (compte_id,)
    )
    return {
        "temps_total": duree_lisible(minutes),
        "nb_films": nb_films,
        "nb_series": nb_series,
        "nb_episodes": nb_episodes,
        "genres": [{"nom": g, "n": n} for g, n in _compte_genres(compte_id)],
        "par_annee": par_annee,
    }
