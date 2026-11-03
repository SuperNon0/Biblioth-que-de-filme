"""Calcul des statistiques du profil.

Temps total regardé (films + épisodes vus), converti en heures puis en
mois/années ; compteurs (films, séries, épisodes) ; genres, réalisateurs et
acteurs les plus vus ; répartition par année. Le « temps passé » est calculé
automatiquement à partir des durées TMDB × ce qui est marqué vu.
"""
import collections

import db
import genres as genres_fr
from services.sync import ep_diffuse_sql

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
                  COUNT(id) AS episodes
           FROM episodes WHERE titre_id = ? AND vu = 1""",
        (DUREE_EPISODE_DEFAUT, titre_id),
    )
    # « Série vue ×N » : sur les épisodes déjà diffusés (une saison annoncée
    # n'empêche pas une série terminée d'être comptée comme vue).
    diff = db.q1(
        f"""SELECT COUNT(*) AS total, SUM(vu) AS vus, MIN(nb_vues) AS mini
            FROM episodes WHERE titre_id = ? AND {ep_diffuse_sql()}""", (titre_id,))
    minutes = (row and row["minutes"]) or 0
    info = duree_lisible(minutes)
    info["episodes"] = (row and row["episodes"]) or 0
    total = diff["total"] or 0
    info["fois"] = (diff["mini"] or 0) if (total and (diff["vus"] or 0) >= total) else 0
    return info


def _compte_genres(compte_id):
    counter = collections.Counter()
    for r in db.q("SELECT genres FROM titres WHERE compte_id = ? AND (statut = 'vu' "
                  "OR id IN (SELECT DISTINCT titre_id FROM visionnages))", (compte_id,)):
        # Genres doubles des séries répartis dans leurs deux genres, en français
        # (« Action & Adventure » compte dans Action et dans Aventure).
        for g in genres_fr.normaliser(db.jload(r["genres"], [])):
            counter[g] += 1
    return counter.most_common(10)


def _top_series_temps(compte_id, limit=8):
    """Séries les plus chronophages (temps vu, revisionnages inclus)."""
    rows = db.q(
        f"""SELECT t.id, t.titre, t.affiche,
                   SUM(COALESCE(e.duree, {DUREE_EPISODE_DEFAUT}) * MAX(e.nb_vues, 1)) AS minutes
            FROM episodes e JOIN titres t ON t.id = e.titre_id
            WHERE e.vu = 1 AND t.compte_id = ?
            GROUP BY t.id ORDER BY minutes DESC LIMIT ?""",
        (compte_id, limit))
    out = []
    for r in rows:
        d = duree_lisible(r["minutes"] or 0)
        out.append({"id": r["id"], "titre": r["titre"], "affiche": r["affiche"],
                    "minutes": d["minutes"], "texte": d["texte"], "converti": d["converti"]})
    return out


def _revisionnages(compte_id):
    """Compteurs de re-visionnages : films revus ≥2 fois, séries revues ≥2 fois."""
    # type='film' : d'anciennes séries portent des visionnages (avant le suivi
    # par épisode) qui ne doivent pas compter comme « films revus ».
    films = db.q1(
        """SELECT COUNT(*) AS n FROM (
             SELECT v.titre_id FROM visionnages v JOIN titres t ON t.id = v.titre_id
             WHERE t.compte_id = ? AND t.type = 'film'
             GROUP BY v.titre_id HAVING COUNT(*) >= 2)""",
        (compte_id,))["n"]
    # Série revue = tous les épisodes diffusés vus au moins 2 fois.
    series = db.q1(
        f"""SELECT COUNT(*) AS n FROM (
             SELECT e.titre_id FROM episodes e JOIN titres t ON t.id = e.titre_id
             WHERE t.compte_id = ? AND {ep_diffuse_sql("e")} GROUP BY e.titre_id
             HAVING MIN(e.nb_vues) >= 2 AND SUM(CASE WHEN e.vu=0 THEN 1 ELSE 0 END) = 0)""",
        (compte_id,))["n"]
    return {"films": films, "series": series}


def _records(compte_id):
    """Film le plus revu et série la plus revue (pour la section « records »)."""
    film = db.q1(
        """SELECT t.titre, t.affiche, COUNT(v.id) AS n
           FROM visionnages v JOIN titres t ON t.id = v.titre_id
           WHERE t.compte_id = ? AND t.type = 'film'
           GROUP BY t.id ORDER BY n DESC LIMIT 1""",
        (compte_id,))
    # Sans filtre « e.vu = 1 » (qui rendait le HAVING sans effet : 1 épisode
    # vu 9 fois sur 53 faisait « série revue ×9 ») : série entièrement vue.
    serie = db.q1(
        f"""SELECT t.titre, t.affiche, MIN(e.nb_vues) AS n
            FROM episodes e JOIN titres t ON t.id = e.titre_id
            WHERE t.compte_id = ? AND {ep_diffuse_sql("e")}
            GROUP BY t.id HAVING SUM(CASE WHEN e.vu=0 THEN 1 ELSE 0 END) = 0
            ORDER BY n DESC LIMIT 1""",
        (compte_id,))
    def fmt(r):
        return {"titre": r["titre"], "affiche": r["affiche"], "n": r["n"]} if r and r["n"] else None
    return {"film_plus_revu": fmt(film), "serie_plus_revue": fmt(serie)}


def resume(compte_id):
    min_films = _minutes_films(compte_id)
    min_series = _minutes_episodes(compte_id)
    minutes = min_films + min_series
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
        # Stat 1 — répartition films / séries (nombre + temps).
        "repartition": {"films_n": nb_films, "series_n": nb_series,
                        "films_min": min_films, "series_min": min_series,
                        "films_texte": duree_lisible(min_films)["texte"],
                        "series_texte": duree_lisible(min_series)["texte"]},
        # Stat 4 — top séries chronophages.
        "top_series_temps": _top_series_temps(compte_id),
        # Stat 5 — total de re-visionnages.
        "revisionnages": _revisionnages(compte_id),
        # Stat 16 — records (film le plus revu, série la plus revue).
        "records": _records(compte_id),
    }
