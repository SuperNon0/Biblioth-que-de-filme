"""Découverte : Suggestions (accueil), Découverte (catalogue) et Futur.

- /api/suggestions : les carrousels de la page d'accueil (reprendre,
  tendances, au cinéma, populaires, mieux notés, recommandé pour toi).
- /api/discover : catalogue filtrable et paginé (films/séries).
- /api/upcoming : films à venir + gestion des alertes de sortie.
"""
import random
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from functools import partial

import db
from flask import Blueprint, jsonify, request

import auth
import genres as genres_fr
from context import get_tmdb
from routes import prefs as prefs_mod
from routes.library import annotate_library, annotate_series_progress, mes_plateformes
from tmdb import TMDBError, canon_platform

bp = Blueprint("discover", __name__, url_prefix="/api")

# Appels TMDB lancés en parallèle (on attend le réseau, pas le processeur) :
# l'accueil enchaînait ~18 requêtes l'une après l'autre (~1,2 s en prod).
POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="tmdb")

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

    Ordre : le **dernier épisode regardé en premier** (comme l'historique), pour
    retrouver tout de suite la série qu'on suit sans avoir à la rechercher. Les
    séries sans date de visionnage connue (données anciennes) passent ensuite,
    départagées par la dernière mise à jour.
    """
    rows = db.q(
        """SELECT t.id, t.tmdb_id, t.type, t.titre, t.affiche, t.fond, t.annee,
                  t.note_tmdb, t.statut, t.date_ajout,
                  MAX(e.derniere_vue) AS derniere_activite
           FROM titres t
           LEFT JOIN episodes e ON e.titre_id = t.id AND e.vu = 1
           WHERE t.type='serie' AND t.statut='en_cours' AND t.compte_id = ?
           GROUP BY t.id
           ORDER BY derniere_activite DESC, t.maj DESC
           LIMIT 20""",
        (auth.compte_courant_id(),)
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
            # (id, type) : un film et une série peuvent avoir le même id TMDB.
            key = (it.get("tmdb_id"), it.get("type"))
            if not key[0] or key in seen:
                continue
            seen.add(key)
            uniq.append(it)
        if len(uniq) >= 4:  # on n'affiche pas les rangées trop maigres
            blocs.append({"cle": cle, "titre": titre, "items": uniq[:20]})

    # Rangées choisies dans les paramètres (A3) : ordre et rangées masquées.
    choix = prefs_mod.lire(auth.compte_courant_id())["rangees"]
    ordre = {r["id"]: i for i, r in enumerate(choix)}
    actives = {r["id"] for r in choix if r["on"]}

    # Reprendre (local) — marqués vus pour ne pas les reproposer ailleurs.
    reprendre = _reprendre() if "reprendre" in actives else []
    for r in reprendre:
        if r.get("tmdb_id"):
            seen.add((r["tmdb_id"], r["type"]))

    def label(mk, txt):
        return (("Séries" if mk == "tv" else "Films") + " · " + txt
                if media == "all" else txt)

    def results(fn, **kw):
        return lambda: fn(**kw)["results"]

    # Rangées dans l'ordre d'origine : (sorte, clé, titre, appel TMDB). Les
    # tirages au hasard (pages, genres) se font ici ; les appels partent en
    # parallèle. Personnalisé d'abord : « Parce que tu as aimé … » (titres
    # vus/favoris, tirés au hasard → renouvelés à chaque rafraîchissement).
    rangees = []
    if "perso" in actives:
        for base in _bases_perso(media, limit=4):
            bmedia = "movie" if base["type"] == "film" else "tv"
            quoi = "regardé la série" if base["type"] == "serie" else "aimé"
            rangees.append(("perso", f"perso_{base['tmdb_id']}",
                            f"Parce que tu as {quoi} « {base['titre']} »",
                            partial(tmdb.recommendations, bmedia, base["tmdb_id"],
                                    page=random.randint(1, 2))))
    rangees.append(("tendances", "tendances", "Tendances cette semaine",
                    partial(tmdb.trending, media, "week")))
    if "movie" in mkeys:
        rangees.append(("cinema", "cinema", "Au cinéma en ce moment",
                        partial(tmdb.now_playing, random.randint(1, 3))))
        rangees.append(("bientot", "bientot", "Bientôt au cinéma",
                        partial(_sorties, tmdb, 2)))
    if "tv" in mkeys and media == "all":
        rangees.append(("tv_tendances", "tv_tendances", "Séries tendances",
                        partial(tmdb.trending, "tv", "week")))
    # Par genre (tes goûts, mélangés) — pour chaque média demandé.
    if "genres" in actives:
        for mk in mkeys:
            genres = _top_genres(tmdb, mk, limit=4)
            random.shuffle(genres)
            for gid, gname in genres[:(1 if media == "all" else 3)]:
                rangees.append(("genres", f"genre_{mk}_{gid}",
                                label(mk, genres_fr.libelle(gname)),
                                results(tmdb.discover, media=mk, genre=gid,
                                        sort_by="popularity.desc",
                                        page=random.randint(1, 3))))
    # Pépites, populaires et mieux notés — films ET séries.
    for mk in mkeys:
        rangees.append(("pepites", f"pepites_{mk}", label(mk, "Pépites à découvrir"),
                        results(tmdb.discover, media=mk, sort_by="vote_average.desc",
                                vote_count_gte=600, page=random.randint(1, 4))))
        rangees.append(("top", f"top_{mk}", label(mk, "Les mieux notés"),
                        partial(tmdb.top_rated, mk, page=random.randint(1, 3))))
        rangees.append(("pop", f"pop_{mk}", label(mk, "Populaires"),
                        partial(tmdb.popular, mk, page=random.randint(1, 4))))
    # Cultes d'une décennie (sur le premier média).
    rangees.append(("annees90", "annees90", label(mkeys[0], "Cultes des années 90"),
                    results(tmdb.discover, media=mkeys[0], sort_by="vote_average.desc",
                            vote_count_gte=1200, year_gte=1990, year_lte=1999)))
    rangees = [r for r in rangees if r[0] in actives]
    rangees.sort(key=lambda r: ordre.get(r[0], 99))  # tri stable : l'ordre d'origine reste

    taches = [(sorte, cle, titre, POOL.submit(appel)) for sorte, cle, titre, appel in rangees]
    if reprendre:
        taches.append(("reprendre", "reprendre", "Reprendre", None))
        taches.sort(key=lambda t: ordre.get(t[0], 99))
    erreur = None
    for sorte, cle, titre, tache in taches:  # repris DANS L'ORDRE (dédoublonnage)
        if tache is None:
            blocs.append({"cle": "reprendre", "titre": "Reprendre",
                          "local": True, "items": reprendre})
            continue
        try:
            add(cle, titre, tache.result())
        except TMDBError as exc:  # une rangée en échec n'empêche pas les autres
            erreur = erreur or exc
    if not blocs and erreur:
        return jsonify(error=str(erreur)), 502
    # Statut/progression locale : une seule annotation pour toutes les rangées.
    annotate_library([it for b in blocs if not b.get("local") for it in b["items"]])
    _poser_alertes([it for b in blocs if b["cle"] == "bientot" for it in b["items"]])
    return jsonify(blocs=blocs)


def _bases_perso(media="all", limit=4):
    """Titres de référence pour les recommandations, tirés au hasard.

    Priorité aux titres **vus / en cours / favoris** (ce que l'utilisateur a
    réellement regardé), films et séries mêlés ; complété au besoin par
    n'importe quels titres de la bibliothèque. L'ordre aléatoire fait varier
    les rangées « Parce que tu as aimé … » d'un rafraîchissement à l'autre.
    """
    cond, params = ["tmdb_id IS NOT NULL", "compte_id = ?"], [auth.compte_courant_id()]
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
    for r in db.q("SELECT genres FROM titres WHERE compte_id = ?",
                  (auth.compte_courant_id(),)):
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
    """Catalogue large filtrable + paginé (onglet Découverte).

    Filtres en plus des classiques : ``depuis`` (année minimale, « 2020 et + »),
    ``duree_max`` (minutes, « moins de 2 h », films) et ``mes=1`` (seulement ce
    qui est inclus dans MES plateformes, avec le badge de la plateforme)."""
    media = "tv" if request.args.get("type") == "serie" else "movie"
    page = max(1, request.args.get("page", 1, type=int) or 1)
    sorts = SORTS_SERIE if media == "tv" else SORTS_FILM
    sort_by = sorts.get(request.args.get("tri", "populaire"), sorts["populaire"])
    tmdb = get_tmdb()
    filtres = dict(
        media=media, page=page, sort_by=sort_by,
        genre=request.args.get("genre") or None,
        year=request.args.get("annee") or None,
        country=request.args.get("pays") or None,
        note_min=request.args.get("note") or None,
        year_gte=request.args.get("depuis", type=int) or None,
        runtime_lte=(request.args.get("duree_max", type=int) or None) if media == "movie" else None,
    )
    try:
        if request.args.get("mes") == "1":
            data = _discover_mes_plateformes(tmdb, filtres)
        else:
            data = tmdb.discover(provider=request.args.get("plateforme") or None, **filtres)
    except TMDBError as exc:
        return jsonify(error=str(exc)), 502
    data["results"] = annotate_library(data.get("results", []))
    return jsonify(data)


def _ids_mes_plateformes(tmdb, media):
    """{nom canonique: {nom, logo, ids}} de mes plateformes (variantes incluses,
    ex. Netflix + « Netflix basic with Ads »)."""
    mes = mes_plateformes()
    out = {}
    for p in tmdb.watch_providers(media):
        nom = canon_platform(p["nom"])
        if nom.lower() in mes and p.get("id"):
            e = out.setdefault(nom.lower(), {"nom": nom, "logo": p["logo"], "ids": []})
            e["ids"].append(str(p["id"]))
    return out


def _discover_mes_plateformes(tmdb, filtres):
    """Découverte limitée à mes plateformes : une recherche par plateforme (en
    parallèle), fusionnées en alternance, chaque titre avec son badge."""
    plats = list(_ids_mes_plateformes(tmdb, filtres["media"]).values())
    if not plats:
        return {"results": [], "page": 1, "total_pages": 1, "sans_plateformes": True}
    taches = [(p, POOL.submit(partial(tmdb.discover, provider="|".join(p["ids"]),
                                      inclus=True, **filtres))) for p in plats]
    listes, total = [], 1
    for p, tache in taches:
        data = tache.result()
        total = max(total, data.get("total_pages", 1))
        listes.append([dict(r, dispo={"nom": p["nom"], "logo": p["logo"]})
                       for r in data.get("results", [])])
    vus, fusion = set(), []
    for rang in range(max(len(x) for x in listes)):
        for liste in listes:
            if rang < len(liste) and liste[rang]["tmdb_id"] not in vus:
                vus.add(liste[rang]["tmdb_id"])
                fusion.append(liste[rang])
    return {"results": fusion, "page": filtres["page"], "total_pages": total}


@bp.get("/search/person")
@auth.login_required
def search_person():
    """Acteurs / réalisateurs par nom (recherche de la bibliothèque, B5)."""
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify(results=[])
    try:
        return jsonify(results=get_tmdb().search_person(q))
    except TMDBError as exc:
        return jsonify(error=str(exc)), 502


@bp.get("/providers")
@auth.login_required
def providers():
    """Liste des plateformes de streaming disponibles (filtre Découverte)."""
    media = "tv" if request.args.get("type") == "serie" else "movie"
    try:
        return jsonify(providers=get_tmdb().watch_providers(media))
    except TMDBError as exc:
        return jsonify(error=str(exc)), 502


@bp.get("/providers/all")
@auth.login_required
def providers_all():
    """Toutes les plateformes (films ET séries fusionnés, dédoublonnées par nom),
    triées par priorité d'affichage — pour le choix « mes plateformes » des
    réglages."""
    tmdb = get_tmdb()
    from tmdb import canon_platform
    try:
        merged = {}
        for media in ("movie", "tv"):
            for p in tmdb.watch_providers(media):
                name = canon_platform(p["nom"])      # fusionne les variantes (ex. « Netflix … »)
                key = name.lower()
                cur = merged.get(key)
                if not cur or p.get("prio", 999) < cur.get("prio", 999):
                    merged[key] = {"nom": name, "logo": p["logo"], "prio": p.get("prio", 999)}
    except TMDBError as exc:
        return jsonify(error=str(exc)), 502
    out = sorted(merged.values(), key=lambda x: x.get("prio", 999))
    return jsonify(providers=[{"nom": p["nom"], "logo": p["logo"]} for p in out])


@bp.get("/roulette")
@auth.login_required
def roulette():
    """Tire au sort des titres : dans la liste « À voir » ou dans le catalogue.

    - source=library : pioche dans les titres marqués « À voir ».
    - source=catalog : pioche au hasard dans le catalogue TMDB.
    """
    source = request.args.get("source", "library")
    try:
        count = min(max(int(request.args.get("count", 6) or 6), 1), 24)
    except ValueError:
        count = 6
    if source == "library":
        rows = db.q(
            """SELECT id, tmdb_id, type, titre, affiche, annee, note_tmdb, statut
               FROM titres WHERE statut = 'a_voir' AND compte_id = ?""",
            (auth.compte_courant_id(),)
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
        liste = get_tmdb().genres(media)
    except TMDBError as exc:
        return jsonify(error=str(exc)), 502
    # Genres des séries restés en anglais (« War & Politics »…) : en français.
    return jsonify(genres=[dict(g, name=genres_fr.libelle(g.get("name"))) for g in liste])


# --- Futur / sorties -------------------------------------------------------
# Pages de sorties lues au plus : TMDB en donne ~5 à 10 pour la France.
PAGES_SORTIES = 10
PAR_PAGE = 20


def _sorties(tmdb, max_pages=PAGES_SORTIES):
    """Prochaines sorties au cinéma : toutes les pages (en parallèle), sans les
    films déjà sortis, de la plus proche à la plus lointaine."""
    premiere = tmdb.upcoming_page(1)
    pages = [premiere["results"]]
    suite = [POOL.submit(tmdb.upcoming_page, n)
             for n in range(2, min(premiere["total_pages"], max_pages) + 1)]
    for tache in suite:
        try:
            pages.append(tache.result()["results"])
        except TMDBError:
            pass  # une page en échec : on garde les autres
    today = date.today().isoformat()
    vus, out = set(), []
    for page in pages:
        for it in page:
            # Pas de date ou déjà sorti (ex. un vieux film ressorti) : écarté.
            if it["tmdb_id"] in vus or not it.get("date_sortie") or it["date_sortie"] < today:
                continue
            vus.add(it["tmdb_id"])
            out.append(it)
    out.sort(key=lambda x: x["date_sortie"])
    return out


def _poser_alertes(items):
    """Marque ``alerte`` sur les films à venir pour lesquels j'ai une alerte."""
    if not items:
        return items
    alertes = {a["tmdb_id"] for a in db.q(
        "SELECT t.tmdb_id FROM alertes a JOIN titres t ON t.id = a.titre_id "
        "WHERE t.compte_id = ? AND t.type = 'film'", (auth.compte_courant_id(),))}
    for it in items:
        it["alerte"] = it["tmdb_id"] in alertes
    return items


@bp.get("/upcoming")
@auth.login_required
def upcoming():
    """Films à venir, triés par date, sans ceux déjà sortis (agenda « Futur »).

    Sans ``page`` : toutes les sorties. Avec ``page`` : 20 par page (connecteur
    MCP), avec ``total_pages``."""
    try:
        items = _sorties(get_tmdb())
    except TMDBError as exc:
        return jsonify(error=str(exc)), 502
    page = request.args.get("page", type=int)
    total = max(1, (len(items) + PAR_PAGE - 1) // PAR_PAGE)
    if page:
        page = min(max(1, page), total)
        items = items[(page - 1) * PAR_PAGE: page * PAR_PAGE]
    annotate_library(items)  # id local : la cloche peut retirer l'alerte (D3)
    return jsonify(results=_poser_alertes(items), page=page or 1,
                   total_pages=total if page else 1)
