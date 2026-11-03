"""Bibliothèque : recherche TMDB, ajout, listing filtré, statuts.

Le cœur de l'app : chercher un titre, l'ajouter, lister sa collection avec
tris/filtres, changer le statut ou le favori, supprimer.
"""
import json
import threading
import time
from datetime import date

from flask import Blueprint, jsonify, request

import auth
import db
from context import get_tmdb
from services import sync
from tmdb import TMDBError

bp = Blueprint("library", __name__, url_prefix="/api")

STATUTS = {"vu", "a_voir", "en_cours"}
TRIS = {
    "ajout": "date_ajout DESC",
    "titre": "titre COLLATE NOCASE ASC",
    "annee": "annee DESC",
    "note": "note_tmdb DESC",
}


# Colonnes d'une CARTE (grilles bibliothèque/listes, MCP). La fiche complète
# (casting, équipe, résumé, plateformes…) se charge à l'ouverture via
# /api/title/<id> : renvoyer `SELECT *` faisait ~6 Ko par titre, soit ~3 Mo
# pour une bibliothèque de 500 titres à chaque affichage sur téléphone.
CARTE_COLS = ("id", "tmdb_id", "type", "titre", "annee", "affiche", "note_tmdb",
              "genres", "statut", "favori", "date_ajout", "nb_saisons")


def carte_cols(alias=""):
    """Liste SQL des colonnes de carte (préfixées par l'alias de table)."""
    return ", ".join(f"{alias}{c}" for c in CARTE_COLS)


def _row(t):
    """Sérialise une ligne de titre pour le front."""
    t["genres"] = db.jload(t.get("genres"), [])
    if "plateformes" in t:
        t["plateformes"] = db.jload(t.get("plateformes"), [])
    t["favori"] = bool(t.get("favori"))
    return t


def annotate_cards(rows):
    """Prépare des lignes de titres pour les cartes : genres décodés, « vu ×N »
    des films (nombre de visionnages) et progression des séries."""
    out = [_row(r) for r in rows]
    film_ids = [r["id"] for r in out if r["type"] == "film"]
    vues = {}
    if film_ids:
        marks = ",".join("?" * len(film_ids))
        for v in db.q(f"""SELECT titre_id, COUNT(*) AS n FROM visionnages
                          WHERE titre_id IN ({marks}) GROUP BY titre_id""", film_ids):
            vues[v["titre_id"]] = v["n"]
    # Progression + prochain épisode des séries (barre + « où j'en suis »).
    annotate_series_progress(out)
    for row in out:
        if row["type"] == "film":
            row["nb_vues"] = vues.get(row["id"], 0)
    return out


def _mark_seen(titre_id, typ):
    """Fait qu'un titre marqué « vu » compte dans les statistiques.

    - Film : ajoute un visionnage « déjà vu » (date NULL) s'il n'y en a aucun,
      donc sans forcer de date. Les re-visionnages s'ajoutent depuis la fiche.
    - Série : marque tous les épisodes comme vus (comptent dans le temps passé).
    """
    if typ == "film":
        if not db.q1("SELECT 1 FROM visionnages WHERE titre_id = ? LIMIT 1", (titre_id,)):
            db.run("INSERT OR IGNORE INTO visionnages (titre_id, date, cree) VALUES (?,?,?)",
                   (titre_id, time.strftime("%Y-%m-%d"), int(time.time())))
            db.log_event(titre_id, "film")
    else:
        # Épisodes déjà diffusés seulement : une saison à venir cochée d'avance
        # ne reviendrait jamais dans « Reprendre » à sa sortie.
        db.run(f"""UPDATE episodes SET vu = 1,
                   nb_vues = CASE WHEN nb_vues < 1 THEN 1 ELSE nb_vues END
                   WHERE titre_id = ? AND {sync.ep_diffuse_sql()}""", (titre_id,))


def annotate_series_progress(rows):
    """Ajoute à des lignes de séries : progression (``total_ep``/``vus_ep``) et
    prochain épisode (``next_saison``/``next_numero``) — pour « où j'en suis ».

    Le « prochain épisode » gère aussi le **re-visionnage** : s'il ne reste aucun
    épisode non vu, on propose le premier épisode **moins revu que le maximum**
    (``revoit=True``), pour pouvoir enchaîner une série déjà vue."""
    ids = [r["id"] for r in rows if r.get("type") == "serie"]
    if not ids:
        return rows
    marks = ",".join("?" * len(ids))
    eps_by = {}
    for e in db.q(f"""SELECT titre_id, saison, numero, vu, nb_vues, date_diff FROM episodes
                      WHERE titre_id IN ({marks})
                      ORDER BY titre_id, saison, numero""", ids):
        eps_by.setdefault(e["titre_id"], []).append(e)
    today = date.today().isoformat()
    for r in rows:
        if r.get("type") != "serie":
            continue
        tous = eps_by.get(r["id"])
        if not tous:
            continue
        # Progression sur les épisodes DÉJÀ DIFFUSÉS : une saison annoncée ne
        # fait pas d'une série terminée une série « en cours ».
        eps = [e for e in sync.flag_diffuses(tous, today) if e["diffuse"]]
        if len(eps) < len(tous):
            r["a_venir"] = len(tous) - len(eps)
        if not eps:
            continue
        total = len(eps)
        vus = sum(1 for e in eps if e["vu"])
        maxi = max((e["nb_vues"] or 0) for e in eps)
        mini = min((e["nb_vues"] or 0) for e in eps)
        r["total_ep"] = total
        r["vus_ep"] = vus
        # Prochain épisode : d'abord un non-vu (1er visionnage) ; sinon, le
        # premier moins revu que le max (re-visionnage en cours).
        nxt = next((e for e in eps if not e["vu"]), None)
        if nxt is None and maxi > 0:
            nxt = next((e for e in eps if (e["nb_vues"] or 0) < maxi), None)
            if nxt is not None:
                r["revoit"] = True
        if nxt is not None:
            r["next_saison"] = nxt["saison"]
            r["next_numero"] = nxt["numero"]
        # Série entièrement vue N fois (min des revisionnages) → « ↻ ×N ».
        if total and vus >= total:
            r["nb_vues"] = mini
    return rows


def annotate_library(items):
    """Ajoute le statut local + l'id aux résultats TMDB déjà en bibliothèque.

    Permet au front d'afficher le badge de statut sur les cartes et le menu
    rapide (« déjà dans ta bibliothèque : … »).
    """
    if not items:
        return items
    lib = {(r["tmdb_id"], r["type"]): r for r in db.q(
        """SELECT id, tmdb_id, type, statut, date_ajout,
                  (SELECT COUNT(*) FROM visionnages v WHERE v.titre_id = t.id) AS nb_vues
           FROM titres t WHERE tmdb_id IS NOT NULL AND compte_id = ?""",
        (auth.compte_courant_id(),))}
    for it in items:
        row = lib.get((it.get("tmdb_id"), it.get("type")))
        if row:
            it["statut"] = row["statut"]
            it["local_id"] = row["id"]
            it["nb_vues"] = row["nb_vues"]
            it["date_ajout"] = row["date_ajout"]
    # Progression des séries (X/Y, prochain épisode, re-visionnage) sur TOUS les
    # écrans qui affichent des résultats TMDB (suggestions, découverte, similaires,
    # sagas, page acteur…), pour que le menu rapide montre « En cours » et
    # « Épisode suivant » partout. annotate_series_progress attend la clé « id ».
    in_lib = [it for it in items if it.get("local_id")]
    for it in in_lib:
        it["id"] = it["local_id"]
    annotate_series_progress(in_lib)
    for it in in_lib:
        it.pop("id", None)
    return items


@bp.get("/search")
@auth.login_required
def search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify(results=[])
    try:
        # annotate_library annote aussi la progression des séries (X/Y, prochain
        # épisode) → le menu rapide « épisode suivant » marche depuis la recherche.
        items = annotate_library(get_tmdb().search(query))
    except TMDBError as exc:
        return jsonify(error=str(exc)), 502
    return jsonify(results=items)


@bp.get("/library")
@auth.login_required
def library():
    """Liste la bibliothèque avec filtres (statut, type, genre) et tri."""
    where, params = ["compte_id = ?"], [auth.compte_courant_id()]
    statut = request.args.get("statut")
    if statut in STATUTS:
        where.append("statut = ?")
        params.append(statut)
    typ = request.args.get("type")
    if typ in ("film", "serie"):
        where.append("type = ?")
        params.append(typ)
    genre = request.args.get("genre")
    if genre:
        where.append("genres LIKE ?")
        params.append(f'%"{genre}"%')
    if request.args.get("favori") == "1":
        where.append("favori = 1")
    recherche = request.args.get("q", "").strip()
    if recherche:
        where.append("titre LIKE ?")
        params.append(f"%{recherche}%")
    order = TRIS.get(request.args.get("tri", "ajout"), TRIS["ajout"])
    rows = db.q(
        f"SELECT {carte_cols()} FROM titres WHERE {' AND '.join(where)} ORDER BY {order}",
        params,
    )
    return jsonify(titres=annotate_cards(rows))


@bp.post("/library")
@auth.login_required
def add():
    """Ajoute un titre depuis TMDB (par tmdb_id + type) à la bibliothèque."""
    data = request.get_json(silent=True) or {}
    tmdb_id, typ = data.get("tmdb_id"), data.get("type")
    statut = data.get("statut", "a_voir")
    if typ not in ("film", "serie") or not tmdb_id:
        return jsonify(error="Titre invalide."), 400
    if statut not in STATUTS:
        return jsonify(error="Statut invalide (a_voir, en_cours ou vu)."), 400
    tmdb = get_tmdb()
    try:
        detail = tmdb.movie(tmdb_id) if typ == "film" else tmdb.tv(tmdb_id)
    except TMDBError as exc:
        return jsonify(error=str(exc)), 502
    titre_id = sync.upsert_titre(detail, statut, auth.compte_courant_id())
    # Applique le statut choisi même si le titre existait déjà (upsert ne le
    # change pas à la mise à jour) — utile depuis le menu rapide. Sans statut
    # explicite, un titre déjà présent garde le sien : « ajoute Inception »
    # ne doit pas remettre « à voir » un film déjà vu.
    if "statut" in data:
        db.run("UPDATE titres SET statut = ? WHERE id = ?", (statut, titre_id))
    if typ == "serie":
        # Les épisodes (un appel TMDB par saison) se remplissent en arrière-plan
        # pour que l'ajout réponde instantanément, même pour les longues séries.
        _sync_episodes_bg(tmdb, titre_id, tmdb_id, detail.get("saisons", []), statut)
    elif statut == "vu":
        _mark_seen(titre_id, typ)
    return jsonify(ok=True, id=titre_id)


def _sync_episodes_bg(tmdb, titre_id, tmdb_id, saisons, statut):
    """Remplit les épisodes d'une série dans un thread détaché (non bloquant).

    Le client TMDB et ``db`` ne dépendent pas du contexte de requête : on peut
    donc travailler hors requête. La fiche affiche « chargement… » tant que
    ``sync.is_syncing`` est vrai.
    """
    from datetime import date

    sync.mark_syncing(titre_id)

    def worker():
        try:
            sync.sync_episodes(titre_id, tmdb, tmdb_id, saisons)
            # Baseline anti-spam : les épisodes déjà diffusés ne déclenchent pas
            # de notification « nouvel épisode ». Seuls les futurs le feront.
            db.run("UPDATE episodes SET notifie=1 WHERE titre_id=? AND "
                   "date_diff IS NOT NULL AND date_diff <= ?",
                   (titre_id, date.today().isoformat()))
            if statut == "vu":
                _mark_seen(titre_id, "serie")
                db.run("UPDATE titres SET statut='vu' WHERE id=?", (titre_id,))
        except TMDBError:
            pass  # les épisodes se compléteront à l'ouverture de la fiche
        finally:
            sync.done_syncing(titre_id)

    threading.Thread(target=worker, daemon=True).start()


@bp.post("/library/manual")
@auth.login_required
def add_manual():
    """Ajout manuel d'un titre absent de TMDB."""
    data = request.get_json(silent=True) or {}
    titre = (data.get("titre") or "").strip()
    typ = data.get("type")
    if not titre or typ not in ("film", "serie"):
        return jsonify(error="Titre et type requis."), 400
    statut = data.get("statut") if data.get("statut") in STATUTS else "a_voir"
    try:
        annee = int(data["annee"]) if data.get("annee") not in (None, "") else None
        duree = int(data["duree"]) if data.get("duree") not in (None, "") else None
    except (TypeError, ValueError):
        return jsonify(error="Année et durée doivent être des nombres."), 400
    now = int(time.time())
    titre_id = db.run(
        """INSERT INTO titres (compte_id, type, titre, annee, resume, duree, statut,
                               ajout_manuel, date_ajout, maj)
           VALUES (?,?,?,?,?,?,?,1,?,?)""",
        (auth.compte_courant_id(), typ, titre, annee, data.get("resume"),
         duree, statut, now, now),
    )
    if typ == "film" and statut == "vu":
        # Sans visionnage, un film « vu » ne compte pas dans les statistiques.
        db.run("INSERT INTO visionnages (titre_id, date, cree) VALUES (?,?,?)",
               (titre_id, None, now))
    return jsonify(ok=True, id=titre_id)


@bp.patch("/library/<int:titre_id>")
@auth.login_required
def update(titre_id):
    """Change le statut ou le favori d'un titre."""
    data = request.get_json(silent=True) or {}
    cid = auth.compte_courant_id()
    row = db.q1("SELECT id, type FROM titres WHERE id = ? AND compte_id = ?", (titre_id, cid))
    if not row:
        return jsonify(error="Titre introuvable."), 404
    if "statut" in data and data["statut"] not in STATUTS:
        return jsonify(error="Statut invalide (a_voir, en_cours ou vu)."), 400
    if "statut" in data:
        db.run("UPDATE titres SET statut = ? WHERE id = ? AND compte_id = ?",
               (data["statut"], titre_id, cid))
        if data["statut"] == "vu":
            _mark_seen(titre_id, row["type"])
    if "favori" in data:
        db.run("UPDATE titres SET favori = ? WHERE id = ? AND compte_id = ?",
               (1 if data["favori"] else 0, titre_id, cid))
        if not data["favori"]:
            # Ancien ajout manuel dans « Favoris » : le titre y restait affiché
            # alors que le cœur était décoché.
            db.run("DELETE FROM liste_items WHERE titre_id = ? AND liste_id IN "
                   "(SELECT id FROM listes WHERE compte_id = ? AND systeme = 'favoris')",
                   (titre_id, cid))
    return jsonify(ok=True)


@bp.delete("/library/<int:titre_id>")
@auth.login_required
def delete(titre_id):
    row = db.q1("SELECT titre FROM titres WHERE id = ? AND compte_id = ?",
                (titre_id, auth.compte_courant_id()))
    if not row:
        return jsonify(error="Titre introuvable."), 404
    db.run("DELETE FROM titres WHERE id = ? AND compte_id = ?",
           (titre_id, auth.compte_courant_id()))
    db.audit("supprimer_titre", acteur=auth.acteur(), cible=row["titre"])
    return jsonify(ok=True)


@bp.get("/to-add")
@auth.login_required
def to_add():
    """Suggestions de films connus/classiques à ajouter (remplir vite).

    Renvoie des populaires/mieux notés en excluant ce qui est déjà en base.
    """
    from routes.discover import POOL  # import local : discover importe ce module
    tmdb = get_tmdb()
    top, pop = POOL.submit(tmdb.top_rated, "movie"), POOL.submit(tmdb.popular, "movie")
    try:
        pool = top.result() + pop.result()
    except TMDBError as exc:
        return jsonify(error=str(exc)), 502
    connus = {r["tmdb_id"] for r in
              db.q("SELECT tmdb_id FROM titres WHERE tmdb_id IS NOT NULL AND type = 'film' "
                   "AND compte_id = ?", (auth.compte_courant_id(),))}
    seen, out = set(), []
    for r in pool:
        if r["tmdb_id"] in connus or r["tmdb_id"] in seen:
            continue
        seen.add(r["tmdb_id"])
        out.append(r)
    return jsonify(results=out[:30])
