"""Découverte : Suggestions (accueil), Découverte (catalogue) et Futur.

- /api/suggestions : les carrousels de la page d'accueil (reprendre,
  tendances, au cinéma, populaires, mieux notés, recommandé pour toi).
- /api/discover : catalogue filtrable et paginé (films/séries).
- /api/upcoming : films à venir + gestion des alertes de sortie.
"""
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
    """Les carrousels de la page d'accueil, façon FilmNoir/Letterboxd."""
    media = request.args.get("media", "all")  # all | movie | tv
    tmdb = get_tmdb()
    blocs = []
    reprendre = _reprendre()
    if reprendre:
        blocs.append({"cle": "reprendre", "titre": "Reprendre",
                      "local": True, "items": reprendre})
    try:
        blocs += [
            {"cle": "tendances", "titre": "Tendances cette semaine",
             "items": tmdb.trending(media, "week")},
            {"cle": "cinema", "titre": "Au cinéma en ce moment",
             "items": tmdb.now_playing()},
            {"cle": "populaires", "titre": "Populaires",
             "items": tmdb.popular("movie" if media != "tv" else "tv")},
            {"cle": "notes", "titre": "Mieux notés",
             "items": tmdb.top_rated("movie" if media != "tv" else "tv")},
        ]
        recos = _recommande(tmdb)
        if recos:
            blocs.append({"cle": "pour_toi", "titre": "Recommandé pour toi",
                          "items": recos})
    except TMDBError as exc:
        if not blocs:
            return jsonify(error=str(exc)), 502
    return jsonify(blocs=blocs)


def _recommande(tmdb):
    """Recommandations basées sur les favoris/derniers titres de la biblio."""
    bases = db.q(
        """SELECT tmdb_id, type FROM titres
           WHERE tmdb_id IS NOT NULL ORDER BY favori DESC, maj DESC LIMIT 3"""
    )
    seen, out = set(), []
    for b in bases:
        media = "movie" if b["type"] == "film" else "tv"
        try:
            for r in tmdb.recommendations(media, b["tmdb_id"]):
                if r["tmdb_id"] not in seen:
                    seen.add(r["tmdb_id"])
                    out.append(r)
        except TMDBError:
            continue
    return out[:20]


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
