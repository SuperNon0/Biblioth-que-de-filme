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


# Une entrée = un appel TMDB : plafond par import (quota de la clé commune).
IMPORT_MAX = 200


def _fiche(tmdb, entree):
    typ = entree.get("type", "film")
    return tmdb.movie(entree["tmdb_id"]) if typ == "film" else tmdb.tv(entree["tmdb_id"])


def _import_items(nom, entrees):
    """Crée une liste et y range des entrées {tmdb_id, type} dans l'ordre.

    Chaque titre est récupéré depuis TMDB (validé) puis ajouté à la biblio en
    « à voir ». Les fiches sont demandées en parallèle (une liste Marvel prenait
    ~12 s), et les épisodes des séries se remplissent en arrière-plan.
    Renvoie (liste_id, nombre ajouté).
    """
    from routes.discover import POOL
    from routes.library import _sync_episodes_bg
    cid = auth.compte_courant_id()
    liste_id = db.run("INSERT INTO listes (compte_id, nom, cree) VALUES (?, ?, ?)",
                      (cid, nom, int(time.time())))
    tmdb = get_tmdb()
    futures = [POOL.submit(_fiche, tmdb, e) for e in entrees]
    ajoutes = 0
    for rang, fut in enumerate(futures):
        try:
            detail = fut.result()
        except (TMDBError, KeyError, TypeError, ValueError):
            continue
        titre_id = sync.upsert_titre(detail, "a_voir", cid)
        db.run("INSERT OR IGNORE INTO liste_items (liste_id, titre_id, rang, ajoute) "
               "VALUES (?,?,?,?)", (liste_id, titre_id, rang, int(time.time())))
        if detail["type"] == "serie" and not db.q1(
                "SELECT 1 FROM episodes WHERE titre_id = ? LIMIT 1", (titre_id,)):
            _sync_episodes_bg(tmdb, titre_id, detail["tmdb_id"],
                              detail.get("saisons", []), "a_voir")
        ajoutes += 1
    return liste_id, ajoutes


# Listes système : en plus des titres ajoutés à la main, elles reprennent
# automatiquement les titres au statut « à voir » / marqués favoris.
_REGLE_SYSTEME = {"a_voir": "t.statut = 'a_voir'", "favoris": "t.favori = 1"}


def _titres_sql(liste):
    """Requête (sans colonnes) des titres d'une liste, système ou perso."""
    regle = _REGLE_SYSTEME.get(liste.get("systeme"))
    where = "li.liste_id IS NOT NULL" + (f" OR {regle}" if regle else "")
    return (" FROM titres t LEFT JOIN liste_items li "
            "ON li.titre_id = t.id AND li.liste_id = ? "
            f"WHERE t.compte_id = ? AND ({where})",
            (liste["id"], liste["compte_id"]))


def _liste(row):
    row["systeme_flag"] = bool(row.get("systeme"))
    sql, params = _titres_sql(row)
    row["nb"] = db.q1("SELECT COUNT(*) AS n" + sql, params)["n"]
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
    from routes.library import annotate_cards, carte_cols
    sql, params = _titres_sql(liste)
    rows = db.q(f"SELECT {carte_cols('t.')}" + sql +
                " ORDER BY li.rang IS NULL, li.rang, li.ajoute, t.date_ajout DESC", params)
    return jsonify(liste=liste, titres=annotate_cards(rows))


@bp.post("/lists/<int:liste_id>/items")
@auth.login_required
def add_item(liste_id):
    cid = auth.compte_courant_id()
    titre_id = (request.get_json(silent=True) or {}).get("titre_id")
    liste = db.q1("SELECT systeme FROM listes WHERE id = ? AND compte_id = ?",
                  (liste_id, cid))
    if not liste:
        return jsonify(error="Liste introuvable."), 404
    if not db.q1("SELECT id FROM titres WHERE id = ? AND compte_id = ?", (titre_id, cid)):
        return jsonify(error="Titre introuvable."), 404
    if liste["systeme"] == "favoris":
        # « Favoris » suit la seule règle du cœur : pas de ligne en plus, qui
        # gardait le titre dans la liste une fois le cœur décoché.
        db.run("UPDATE titres SET favori = 1 WHERE id = ? AND compte_id = ?",
               (titre_id, cid))
        return jsonify(ok=True)
    rang = db.q1("SELECT COALESCE(MAX(rang),0)+1 AS r FROM liste_items "
                 "WHERE liste_id = ?", (liste_id,))["r"]
    db.run("INSERT OR IGNORE INTO liste_items (liste_id, titre_id, rang, ajoute) "
           "VALUES (?,?,?,?)", (liste_id, titre_id, rang, int(time.time())))
    return jsonify(ok=True)


@bp.delete("/lists/<int:liste_id>/items/<int:titre_id>")
@auth.login_required
def remove_item(liste_id, titre_id):
    cid = auth.compte_courant_id()
    liste = db.q1("SELECT systeme FROM listes WHERE id = ? AND compte_id = ?",
                  (liste_id, cid))
    if not liste:
        return jsonify(error="Liste introuvable."), 404
    retires = db.run_n("DELETE FROM liste_items WHERE liste_id = ? AND titre_id = ?",
                       (liste_id, titre_id))
    if liste["systeme"] == "favoris":
        retires += db.run_n("UPDATE titres SET favori = 0 WHERE id = ? AND compte_id = ? "
                            "AND favori = 1", (titre_id, cid))
    elif liste["systeme"] == "a_voir" and db.q1(
            "SELECT 1 FROM titres WHERE id = ? AND compte_id = ? AND statut = 'a_voir'",
            (titre_id, cid)):
        # Ce titre est dans « À voir plus tard » par son statut : le retirer de
        # la liste sans changer ce statut ne ferait rien.
        return jsonify(error="Ce titre est « à voir » : change son statut pour le "
                             "retirer de cette liste."), 400
    if not retires:
        return jsonify(error="Ce titre n'est pas dans cette liste."), 404
    return jsonify(ok=True)


@bp.post("/lists/import")
@auth.login_required
def import_list():
    """Crée une liste à partir d'entrées {tmdb_id, type}, dans l'ordre fourni."""
    data = request.get_json(silent=True) or {}
    nom = (data.get("nom") or "Liste importée").strip()
    entrees = data.get("items") or []
    if not isinstance(entrees, list) or not entrees:
        return jsonify(error="Aucun élément à importer."), 400
    if len(entrees) > IMPORT_MAX:
        return jsonify(error=f"{IMPORT_MAX} titres maximum par import."), 400
    entrees = [e for e in entrees if isinstance(e, dict)]
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
