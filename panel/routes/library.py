"""Bibliothèque : recherche TMDB, ajout, listing filtré, statuts.

Le cœur de l'app : chercher un titre, l'ajouter, lister sa collection avec
tris/filtres, changer le statut ou le favori, supprimer.
"""
import json
import time

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


def _row(t):
    """Sérialise une ligne de titre pour le front."""
    t["genres"] = db.jload(t.get("genres"), [])
    t["plateformes"] = db.jload(t.get("plateformes"), [])
    t["favori"] = bool(t.get("favori"))
    return t


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
    else:
        db.run("""UPDATE episodes SET vu = 1,
                  nb_vues = CASE WHEN nb_vues < 1 THEN 1 ELSE nb_vues END
                  WHERE titre_id = ?""", (titre_id,))


def annotate_library(items):
    """Ajoute le statut local + l'id aux résultats TMDB déjà en bibliothèque.

    Permet au front d'afficher le badge de statut sur les cartes et le menu
    rapide (« déjà dans ta bibliothèque : … »).
    """
    if not items:
        return items
    lib = {(r["tmdb_id"], r["type"]): r for r in db.q(
        """SELECT id, tmdb_id, type, statut,
                  (SELECT COUNT(*) FROM visionnages v WHERE v.titre_id = t.id) AS nb_vues
           FROM titres t WHERE tmdb_id IS NOT NULL""")}
    for it in items:
        row = lib.get((it.get("tmdb_id"), it.get("type")))
        if row:
            it["statut"] = row["statut"]
            it["local_id"] = row["id"]
            it["nb_vues"] = row["nb_vues"]
    return items


@bp.get("/search")
@auth.login_required
def search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify(results=[])
    try:
        return jsonify(results=annotate_library(get_tmdb().search(query)))
    except TMDBError as exc:
        return jsonify(error=str(exc)), 502


@bp.get("/library")
@auth.login_required
def library():
    """Liste la bibliothèque avec filtres (statut, type, genre) et tri."""
    where, params = ["1=1"], []
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
        f"SELECT * FROM titres WHERE {' AND '.join(where)} ORDER BY {order}",
        params,
    )
    # Progression des séries (épisodes vus / total) pour la barre sur l'affiche.
    series_ids = [r["id"] for r in rows if r["type"] == "serie"]
    prog = {}
    if series_ids:
        marks = ",".join("?" * len(series_ids))
        for p in db.q(f"""SELECT titre_id, COUNT(*) AS total, SUM(vu) AS vus
                          FROM episodes WHERE titre_id IN ({marks})
                          GROUP BY titre_id""", series_ids):
            prog[p["titre_id"]] = p
    # Nombre de visionnages des films (pour afficher « vu ×N »).
    film_ids = [r["id"] for r in rows if r["type"] == "film"]
    vues = {}
    if film_ids:
        marks = ",".join("?" * len(film_ids))
        for v in db.q(f"""SELECT titre_id, COUNT(*) AS n FROM visionnages
                          WHERE titre_id IN ({marks}) GROUP BY titre_id""", film_ids):
            vues[v["titre_id"]] = v["n"]
    out = []
    for r in rows:
        row = _row(r)
        if row["type"] == "serie" and row["id"] in prog:
            row["total_ep"] = prog[row["id"]]["total"]
            row["vus_ep"] = prog[row["id"]]["vus"] or 0
        elif row["type"] == "film":
            row["nb_vues"] = vues.get(row["id"], 0)
        out.append(row)
    return jsonify(titres=out)


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
        statut = "a_voir"
    tmdb = get_tmdb()
    try:
        detail = tmdb.movie(tmdb_id) if typ == "film" else tmdb.tv(tmdb_id)
    except TMDBError as exc:
        return jsonify(error=str(exc)), 502
    titre_id = sync.upsert_titre(detail, statut)
    # Applique le statut choisi même si le titre existait déjà (upsert ne le
    # change pas à la mise à jour) — utile depuis le menu rapide.
    db.run("UPDATE titres SET statut = ? WHERE id = ?", (statut, titre_id))
    if typ == "serie":
        try:
            sync.sync_episodes(titre_id, tmdb, tmdb_id, detail.get("saisons", []))
            # Baseline anti-spam : les épisodes déjà diffusés ne déclenchent pas
            # de notification « nouvel épisode ». Seuls les futurs le feront.
            from datetime import date
            db.run("UPDATE episodes SET notifie=1 WHERE titre_id=? AND "
                   "date_diff IS NOT NULL AND date_diff <= ?",
                   (titre_id, date.today().isoformat()))
        except TMDBError:
            pass  # les épisodes se compléteront à l'ouverture de la fiche
    if statut == "vu":
        _mark_seen(titre_id, typ)
    return jsonify(ok=True, id=titre_id)


@bp.post("/library/manual")
@auth.login_required
def add_manual():
    """Ajout manuel d'un titre absent de TMDB."""
    data = request.get_json(silent=True) or {}
    titre = (data.get("titre") or "").strip()
    typ = data.get("type")
    if not titre or typ not in ("film", "serie"):
        return jsonify(error="Titre et type requis."), 400
    now = int(time.time())
    titre_id = db.run(
        """INSERT INTO titres (type, titre, annee, resume, duree, statut,
                               ajout_manuel, date_ajout, maj)
           VALUES (?,?,?,?,?,?,1,?,?)""",
        (typ, titre, data.get("annee"), data.get("resume"),
         data.get("duree"), data.get("statut", "a_voir"), now, now),
    )
    return jsonify(ok=True, id=titre_id)


@bp.patch("/library/<int:titre_id>")
@auth.login_required
def update(titre_id):
    """Change le statut ou le favori d'un titre."""
    data = request.get_json(silent=True) or {}
    row = db.q1("SELECT id, type FROM titres WHERE id = ?", (titre_id,))
    if not row:
        return jsonify(error="Titre introuvable."), 404
    if "statut" in data and data["statut"] in STATUTS:
        db.run("UPDATE titres SET statut = ? WHERE id = ?",
               (data["statut"], titre_id))
        if data["statut"] == "vu":
            _mark_seen(titre_id, row["type"])
    if "favori" in data:
        db.run("UPDATE titres SET favori = ? WHERE id = ?",
               (1 if data["favori"] else 0, titre_id))
    return jsonify(ok=True)


@bp.delete("/library/<int:titre_id>")
@auth.login_required
def delete(titre_id):
    db.run("DELETE FROM titres WHERE id = ?", (titre_id,))
    return jsonify(ok=True)


@bp.get("/to-add")
@auth.login_required
def to_add():
    """Suggestions de films connus/classiques à ajouter (remplir vite).

    Renvoie des populaires/mieux notés en excluant ce qui est déjà en base.
    """
    try:
        pool = get_tmdb().top_rated("movie") + get_tmdb().popular("movie")
    except TMDBError as exc:
        return jsonify(error=str(exc)), 502
    connus = {r["tmdb_id"] for r in
              db.q("SELECT tmdb_id FROM titres WHERE tmdb_id IS NOT NULL")}
    seen, out = set(), []
    for r in pool:
        if r["tmdb_id"] in connus or r["tmdb_id"] in seen:
            continue
        seen.add(r["tmdb_id"])
        out.append(r)
    return jsonify(results=out[:30])
