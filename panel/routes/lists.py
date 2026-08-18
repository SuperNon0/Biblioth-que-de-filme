"""Listes : « À voir » (par défaut), « Favoris », et listes personnelles.

Permet de créer des listes, d'y ajouter/retirer des titres, et d'importer
une liste toute prête (ex. « ordre idéal pour voir Marvel ») via une série
de tmdb_id qui sont ajoutés à la bibliothèque puis rangés dans la liste.
"""
import time

from flask import Blueprint, jsonify, request

import auth
import db
from context import get_tmdb
from services import presets, sync
from tmdb import TMDBError

bp = Blueprint("lists", __name__, url_prefix="/api")


def _import_items(nom, entrees):
    """Crée une liste et y range des entrées {tmdb_id, type} dans l'ordre.

    Chaque titre est récupéré depuis TMDB (validé) puis ajouté à la biblio en
    « à voir ». Renvoie (liste_id, nombre ajouté).
    """
    cid = auth.compte_courant_id()
    liste_id = db.run("INSERT INTO listes (compte_id, nom, cree) VALUES (?, ?, ?)",
                      (cid, nom, int(time.time())))
    tmdb = get_tmdb()
    ajoutes = 0
    for rang, e in enumerate(entrees):
        typ = e.get("type", "film")
        try:
            detail = (tmdb.movie(e["tmdb_id"]) if typ == "film"
                      else tmdb.tv(e["tmdb_id"]))
        except (TMDBError, KeyError):
            continue
        titre_id = sync.upsert_titre(detail, "a_voir", cid)
        db.run("INSERT OR IGNORE INTO liste_items (liste_id, titre_id, rang, ajoute) "
               "VALUES (?,?,?,?)", (liste_id, titre_id, rang, int(time.time())))
        ajoutes += 1
    return liste_id, ajoutes


def _liste(row):
    row["systeme_flag"] = bool(row.get("systeme"))
    row["nb"] = db.q1("SELECT COUNT(*) AS n FROM liste_items WHERE liste_id = ?",
                      (row["id"],))["n"]
    return row


@bp.get("/lists")
@auth.login_required
def lists():
    db.ensure_system_lists(auth.compte_courant_id())  # « À voir »/« Favoris » du compte
    rows = db.q("SELECT * FROM listes WHERE compte_id = ? "
                "ORDER BY systeme IS NULL, nom COLLATE NOCASE",
                (auth.compte_courant_id(),))
    return jsonify(listes=[_liste(r) for r in rows])


@bp.post("/lists")
@auth.login_required
def create():
    nom = (request.get_json(silent=True) or {}).get("nom", "").strip()
    if not nom:
        return jsonify(error="Nom de liste requis."), 400
    liste_id = db.run("INSERT INTO listes (compte_id, nom, cree) VALUES (?, ?, ?)",
                      (auth.compte_courant_id(), nom, int(time.time())))
    return jsonify(ok=True, id=liste_id)


@bp.delete("/lists/<int:liste_id>")
@auth.login_required
def delete(liste_id):
    row = db.q1("SELECT systeme FROM listes WHERE id = ? AND compte_id = ?",
                (liste_id, auth.compte_courant_id()))
    if not row:
        return jsonify(error="Liste introuvable."), 404
    if row["systeme"]:
        return jsonify(error="Les listes système ne peuvent pas être supprimées."), 400
    db.run("DELETE FROM listes WHERE id = ? AND compte_id = ?",
           (liste_id, auth.compte_courant_id()))
    return jsonify(ok=True)


@bp.get("/lists/<int:liste_id>")
@auth.login_required
def items(liste_id):
    liste = db.q1("SELECT * FROM listes WHERE id = ? AND compte_id = ?",
                  (liste_id, auth.compte_courant_id()))
    if not liste:
        return jsonify(error="Liste introuvable."), 404
    rows = db.q(
        """SELECT t.* FROM liste_items li JOIN titres t ON t.id = li.titre_id
           WHERE li.liste_id = ? ORDER BY li.rang, li.ajoute""",
        (liste_id,),
    )
    for r in rows:
        r["genres"] = db.jload(r.get("genres"), [])
        r["favori"] = bool(r["favori"])
    return jsonify(liste=liste, titres=rows)


@bp.post("/lists/<int:liste_id>/items")
@auth.login_required
def add_item(liste_id):
    cid = auth.compte_courant_id()
    titre_id = (request.get_json(silent=True) or {}).get("titre_id")
    if not db.q1("SELECT id FROM listes WHERE id = ? AND compte_id = ?", (liste_id, cid)):
        return jsonify(error="Liste introuvable."), 404
    if not db.q1("SELECT id FROM titres WHERE id = ? AND compte_id = ?", (titre_id, cid)):
        return jsonify(error="Titre introuvable."), 404
    rang = db.q1("SELECT COALESCE(MAX(rang),0)+1 AS r FROM liste_items "
                 "WHERE liste_id = ?", (liste_id,))["r"]
    db.run("INSERT OR IGNORE INTO liste_items (liste_id, titre_id, rang, ajoute) "
           "VALUES (?,?,?,?)", (liste_id, titre_id, rang, int(time.time())))
    return jsonify(ok=True)


@bp.delete("/lists/<int:liste_id>/items/<int:titre_id>")
@auth.login_required
def remove_item(liste_id, titre_id):
    if not db.q1("SELECT id FROM listes WHERE id = ? AND compte_id = ?",
                 (liste_id, auth.compte_courant_id())):
        return jsonify(error="Liste introuvable."), 404
    db.run("DELETE FROM liste_items WHERE liste_id = ? AND titre_id = ?",
           (liste_id, titre_id))
    return jsonify(ok=True)


@bp.post("/lists/import")
@auth.login_required
def import_list():
    """Crée une liste à partir d'entrées {tmdb_id, type}, dans l'ordre fourni."""
    data = request.get_json(silent=True) or {}
    nom = (data.get("nom") or "Liste importée").strip()
    entrees = data.get("items") or []
    if not entrees:
        return jsonify(error="Aucun élément à importer."), 400
    liste_id, ajoutes = _import_items(nom, entrees)
    return jsonify(ok=True, id=liste_id, ajoutes=ajoutes)


@bp.get("/lists/presets")
@auth.login_required
def presets_list():
    """Listes toutes prêtes disponibles (Marvel, Star Wars…)."""
    return jsonify(presets=presets.liste())


@bp.post("/lists/import-preset")
@auth.login_required
def import_preset():
    """Importe une liste toute prête par sa clé (ex. « marvel_films »)."""
    cle = (request.get_json(silent=True) or {}).get("cle")
    preset = presets.PRESETS.get(cle)
    if not preset:
        return jsonify(error="Liste prête inconnue."), 404
    liste_id, ajoutes = _import_items(preset["nom"], preset["items"])
    return jsonify(ok=True, id=liste_id, ajoutes=ajoutes)
