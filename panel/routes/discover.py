"""Découverte : Suggestions (accueil), Découverte (catalogue) et Futur.

- /api/suggestions : les carrousels de la page d'accueil (reprendre,
  tendances, au cinéma, populaires, mieux notés, recommandé pour toi).
- /api/discover : catalogue filtrable et paginé (films/séries).
- /api/upcoming : films à venir + gestion des alertes de sortie.
"""
import random

import db
from flask import Blueprint, jsonify, request

import auth
from context import get_tmdb
from routes.library import annotate_library, annotate_series_progress
from tmdb import TMDBError

bp = Blueprint("discover", __name__, url_prefix="/api")

SORTS_FILM = {
    "populaire": "popularity.desc",
    "note": "vote_average.desc",
    "recent": "primary_release_date.desc",
}
SORTS_SERIE = {
    "populaire": "popularity.desc",
    "note": "vote_average.desc",
    "recent": "first_air_date.desc",
}


def _reprendre():
    """Séries en cours à continuer (au moins un épisode vu, pas terminées).

    On renvoie le statut et la progression (épisodes vus/total + prochain
    épisode) pour que la carte affiche le badge « En cours » et « ▸ S x E y »,
    et que le menu rapide sache que la série est déjà suivie.
    """
    rows = db.q(
        """SELECT id, tmdb_id, type, titre, affiche, annee, note_tmdb, statut
           FROM titres WHERE type='serie' AND statut='en_cours'
           ORDER BY maj DESC LIMIT 20"""
    )
    return annotate_series_progress(rows)


@bp.get("/suggestions")
@auth.login_required
def suggestions():
    """Carrousels de l'accueil : personnalisés d'abord, variés, dé-dupliqués.

    - Les rangées « Parce que tu as aimé … » (basées sur des titres vus/favoris,
      films **et** séries) passent en tête et changent à chaque rafraîchissement.
    - En mode « Tout », films et séries sont représentés à parts égales.
    - Les pages/genres sont tirés au hasard pour renouveler les propositions.
    """
    media = request.args.get("media", "all")  # all | movie | tv
    mkeys = ["movie", "tv"] if media == "all" else \
        (["tv"] if media == "tv" else ["movie"])
    tmdb = get_tmdb()
    seen, blocs = set(), []

    def add(cle, titre, items):
        uniq = []
        for it in items or []:
            tid = it.get("tmdb_id")
            if not tid or tid in seen:
                continue
            seen.add(tid)
            uniq.append(it)
        if len(uniq) >= 4:  # on n'affiche pas les rangées trop maigres
            blocs.append({"cle": cle, "titre": titre,
                          "items": annotate_library(uniq[:20])})

    # Reprendre (local) — marqués vus pour ne pas les reproposer ailleurs.
    reprendre = _reprendre()
    for r in reprendre:
        if r.get("tmdb_id"):
            seen.add(r["tmdb_id"])
    if reprendre:
        blocs.append({"cle": "reprendre", "titre": "Reprendre",
                      "local": True, "items": reprendre})

    # Personnalisé EN PREMIER : « Parce que tu as aimé … » (titres vus/favoris,
    # tirés au hasard → propositions renouvelées à chaque rafraîchissement).
    for base in _bases_perso(media, limit=4):
        bmedia = "movie" if base["type"] == "film" else "tv"
        try:
            recos = tmdb.recommendations(bmedia, base["tmdb_id"],
                                         page=random.randint(1, 2))
        except TMDBError:
            continue
        quoi = "regardé la série" if base["type"] == "serie" else "aimé"
        add(f"perso_{base['tmdb_id']}",
            f"Parce que tu as {quoi} « {base['titre']} »", recos)

    def label(mk, txt):
        return (("Séries" if mk == "tv" else "Films") + " · " + txt
                if media == "all" else txt)

    try:
        add("tendances", "Tendances cette semaine", tmdb.trending(media, "week"))
        if "movie" in mkeys:
            add("cinema", "Au cinéma en ce moment",
                tmdb.now_playing(random.randint(1, 3)))
        if "tv" in mkeys and media == "all":
            add("tv_tendances", "Séries tendances", tmdb.trending("tv", "week"))
        # Par genre (tes goûts, mélangés) — pour chaque média demandé.
        for mk in mkeys:
            genres = _top_genres(tmdb, mk, limit=4)
            random.shuffle(genres)
            for gid, gname in genres[:(1 if media == "all" else 3)]:
                add(f"genre_{mk}_{gid}", label(mk, gname),
                    tmdb.discover(media=mk, genre=gid, sort_by="popularity.desc",
                                  page=random.randint(1, 3))["results"])
        # Pépites, populaires et mieux notés — films ET séries.
        for mk in mkeys:
            add(f"pepites_{mk}", label(mk, "Pépites à découvrir"),
                tmdb.discover(media=mk, sort_by="vote_average.desc",
                              vote_count_gte=600,
                              page=random.randint(1, 4))["results"])
            add(f"top_{mk}", label(mk, "Les mieux notés"),
                tmdb.top_rated(mk, page=random.randint(1, 3)))
            add(f"pop_{mk}", label(mk, "Populaires"),
                tmdb.popular(mk, page=random.randint(1, 4)))
        # Cultes d'une décennie (sur le premier média).
        add("annees90", label(mkeys[0], "Cultes des années 90"),
            tmdb.discover(media=mkeys[0], sort_by="vote_average.desc",
                          vote_count_gte=1200, year_gte=1990,
                          year_lte=1999)["results"])
    except TMDBError as exc:
        if not blocs:
            return jsonify(error=str(exc)), 502
    return jsonify(blocs=blocs)


def _bases_perso(media="all", limit=4):
    """Titres de référence pour les recommandations, tirés au hasard.

    Priorité aux titres **vus / en cours / favoris** (ce que l'utilisateur a
    réellement regardé), films et séries mêlés ; complété au besoin par
    n'importe quels titres de la bibliothèque. L'ordre aléatoire fait varier
    les rangées « Parce que tu as aimé … » d'un rafraîchissement à l'autre.
    """
    cond, params = ["tmdb_id IS NOT NULL"], []
    if media in ("movie", "tv"):
        cond.append("type = ?")
        params.append("film" if media == "movie" else "serie")
    where = " AND ".join(cond)
    rows = db.q(
        f"""SELECT tmdb_id, type, titre FROM titres WHERE {where}
            AND (statut IN ('vu', 'en_cours') OR favori = 1)
            ORDER BY RANDOM() LIMIT ?""", params + [limit])
    if len(rows) < limit:  # pas assez de titres vus : on complète librement
        have = {r["tmdb_id"] for r in rows}
        for r in db.q(f"""SELECT tmdb_id, type, titre FROM titres WHERE {where}
                          ORDER BY RANDOM() LIMIT ?""", params + [limit]):
            if r["tmdb_id"] not in have:
                rows.append(r)
                have.add(r["tmdb_id"])
            if len(rows) >= limit:
                break
    return rows[:limit]


def _top_genres(tmdb, media="movie", limit=3):
    """Genres les plus présents dans la bibliothèque (sinon des défauts)."""
    import collections
    counter = collections.Counter()
    for r in db.q("SELECT genres FROM titres"):
        for g in db.jload(r["genres"], []):
            counter[g] += 1
    try:
        gmap = {g["name"]: g["id"] for g in tmdb.genres(media)}
    except TMDBError:
        return []
    chosen = []
    for name, _ in counter.most_common():
        if name in gmap and (gmap[name], name) not in chosen:
            chosen.append((gmap[name], name))
        if len(chosen) >= limit:
            break
    if len(chosen) < limit:  # complète avec des genres grand public par défaut
        for name in ("Action", "Comédie", "Science-Fiction", "Aventure",
                     "Drame", "Thriller", "Animation", "Fantastique"):
            if name in gmap and (gmap[name], name) not in chosen:
                chosen.append((gmap[name], name))
            if len(chosen) >= limit:
                break
    return chosen[:limit]


@bp.get("/discover")
@auth.login_required
def discover():
    """Catalogue large filtrable + paginé (onglet Découverte)."""
    media = "tv" if request.args.get("type") == "serie" else "movie"
    page = max(1, int(request.args.get("page", 1) or 1))
    sorts = SORTS_SERIE if media == "tv" else SORTS_FILM
    sort_by = sorts.get(request.args.get("tri", "populaire"), sorts["populaire"])
    try:
        data = get_tmdb().discover(
            media=media, page=page, sort_by=sort_by,
            genre=request.args.get("genre") or None,
            year=request.args.get("annee") or None,
            country=request.args.get("pays") or None,
            provider=request.args.get("plateforme") or None,
            note_min=request.args.get("note") or None,
        )
    except TMDBError as exc:
        return jsonify(error=str(exc)), 502
    data["results"] = annotate_library(data.get("results", []))
    return jsonify(data)


@bp.get("/providers")
@auth.login_required
def providers():
    """Liste des plateformes de streaming disponibles (filtre Découverte)."""
    media = "tv" if request.args.get("type") == "serie" else "movie"
    try:
        return jsonify(providers=get_tmdb().watch_providers(media))
    except TMDBError as exc:
        return jsonify(error=str(exc)), 502


@bp.get("/roulette")
@auth.login_required
def roulette():
    """Tire au sort des titres : dans la liste « À voir » ou dans le catalogue.

    - source=library : pioche dans les titres marqués « À voir ».
    - source=catalog : pioche au hasard dans le catalogue TMDB.
    """
    source = request.args.get("source", "library")
    try:
        count = min(max(int(request.args.get("count", 6) or 6), 1), 18)
    except ValueError:
        count = 6
    if source == "library":
        rows = db.q(
            """SELECT id, tmdb_id, type, titre, affiche, annee, note_tmdb, statut
               FROM titres WHERE statut = 'a_voir'"""
        )
        random.shuffle(rows)
        return jsonify(results=rows[:count])
    media = "tv" if request.args.get("type") == "serie" else "movie"
    try:
        data = get_tmdb().discover(media=media, page=random.randint(1, 30),
                                   sort_by="popularity.desc")
    except TMDBError as exc:
        return jsonify(error=str(exc)), 502
    items = data.get("results", [])
    random.shuffle(items)
    return jsonify(results=annotate_library(items[:count]))


@bp.get("/similar")
@auth.login_required
def similar():
    """Titres similaires à un titre (pour le carrousel « Parce que tu as aimé »)."""
    tmdb_id = request.args.get("tmdb_id")
    typ = request.args.get("type")
    if not tmdb_id or typ not in ("film", "serie"):
        return jsonify(results=[])
    media = "movie" if typ == "film" else "tv"
    try:
        items = get_tmdb().recommendations(media, int(tmdb_id))
    except (TMDBError, ValueError):
        return jsonify(results=[])
    return jsonify(results=annotate_library(items[:15]))


@bp.get("/collection")
@auth.login_required
def collection():
    """Saga d'un film : les autres films de la même collection (chronologie).

    Pour le carrousel « La saga » sur la fiche d'un film (ex. « Le Labyrinthe »).
    """
    tmdb_id = request.args.get("tmdb_id")
    if not tmdb_id:
        return jsonify(results=[], nom=None)
    tmdb = get_tmdb()
    try:
        detail = tmdb.movie(int(tmdb_id))
        coll = detail.get("collection")
        if not coll or not coll.get("id"):
            return jsonify(results=[], nom=None)
        data = tmdb.collection(coll["id"])
    except (TMDBError, ValueError):
        return jsonify(results=[], nom=None)
    # On retire le film courant de la liste.
    films = [f for f in data["films"] if f.get("tmdb_id") != int(tmdb_id)]
    return jsonify(results=annotate_library(films), nom=data.get("nom"))


@bp.get("/genres")
@auth.login_required
def genres():
    media = "tv" if request.args.get("type") == "serie" else "movie"
    try:
        return jsonify(genres=get_tmdb().genres(media))
    except TMDBError as exc:
        return jsonify(error=str(exc)), 502


# --- Futur / sorties -------------------------------------------------------
@bp.get("/upcoming")
@auth.login_required
def upcoming():
    """Films à venir (avec bande-annonce récupérée à l'ouverture de la fiche)."""
    page = max(1, int(request.args.get("page", 1) or 1))
    try:
        items = get_tmdb().upcoming(page)
    except TMDBError as exc:
        return jsonify(error=str(exc)), 502
    alertes = {a["titre_id"] for a in db.q(
        "SELECT t.tmdb_id AS titre_id FROM alertes a "
        "JOIN titres t ON t.id = a.titre_id")}
    for it in items:
        it["alerte"] = it["tmdb_id"] in alertes
    return jsonify(results=items)
