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
    """Séries en cours à continuer (au moins un épisode vu, pas terminées)."""
    return db.q(
        """SELECT id, tmdb_id, type, titre, affiche, annee, note_tmdb
           FROM titres WHERE type='serie' AND statut='en_cours'
           ORDER BY maj DESC LIMIT 20"""
    )


@bp.get("/suggestions")
@auth.login_required
def suggestions():
    """Carrousels de l'accueil, variés et dé-dupliqués (chaque titre une fois)."""
    media = request.args.get("media", "all")  # all | movie | tv
    mkey = "tv" if media == "tv" else "movie"
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
            blocs.append({"cle": cle, "titre": titre, "items": uniq[:20]})

    # Reprendre (local) — marqués vus pour ne pas les reproposer ailleurs.
    reprendre = _reprendre()
    for r in reprendre:
        if r.get("tmdb_id"):
            seen.add(r["tmdb_id"])
    if reprendre:
        blocs.append({"cle": "reprendre", "titre": "Reprendre",
                      "local": True, "items": reprendre})

    try:
        add("tendances", "Tendances cette semaine", tmdb.trending(media, "week"))
        if mkey == "movie":
            add("cinema", "Au cinéma en ce moment", tmdb.now_playing())
        # Personnalisé : « Parce que tu as aimé … » (par titre précis).
        for base in _bases_perso():
            bmedia = "movie" if base["type"] == "film" else "tv"
            try:
                recos = tmdb.recommendations(bmedia, base["tmdb_id"])
            except TMDBError:
                continue
            add(f"perso_{base['tmdb_id']}",
                f"Parce que tu as aimé « {base['titre']} »", recos)
        # Par genre (tes goûts, sinon des genres par défaut).
        for gid, gname in _top_genres(tmdb, mkey):
            add(f"genre_{gid}", gname,
                tmdb.discover(media=mkey, genre=gid,
                              sort_by="popularity.desc")["results"])
        # Pépites : très bien notées mais moins mainstream.
        add("pepites", "Pépites à découvrir",
            tmdb.discover(media=mkey, sort_by="vote_average.desc",
                          vote_count_gte=800)["results"])
        # Cultes d'une décennie.
        add("annees90", "Cultes des années 90",
            tmdb.discover(media=mkey, sort_by="vote_average.desc",
                          vote_count_gte=1500, year_gte=1990, year_lte=1999)["results"])
        add("populaires", "Populaires", tmdb.popular(mkey))
    except TMDBError as exc:
        if not blocs:
            return jsonify(error=str(exc)), 502
    return jsonify(blocs=blocs)


def _bases_perso(limit=2):
    """Titres de référence pour les recommandations personnalisées."""
    return db.q(
        """SELECT tmdb_id, type, titre FROM titres WHERE tmdb_id IS NOT NULL
           ORDER BY favori DESC, maj DESC LIMIT ?""", (limit,))


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
    if not chosen:
        for name in ("Action", "Comédie", "Science-Fiction", "Aventure"):
            if name in gmap:
                chosen.append((gmap[name], name))
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
        )
    except TMDBError as exc:
        return jsonify(error=str(exc)), 502
    return jsonify(data)


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
    return jsonify(results=items[:count])


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
