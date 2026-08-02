"""Alertes de sortie (cinéma / streaming).

Poser une alerte sur un film à venir : le film est ajouté à la bibliothèque
(statut « à voir ») puis marqué comme suivi. L'info ciné/streaming est
affichée sur la page Futur et sur la fiche.
"""
from flask import Blueprint, jsonify, request

import auth
import db
from context import get_tmdb
from services import sync
from tmdb import TMDBError

bp = Blueprint("alerts", __name__, url_prefix="/api")


@bp.post("/alerts")
@auth.login_required
def create():
    data = request.get_json(silent=True) or {}
    titre_id = data.get("titre_id")
    canal = data.get("canal", "cine")
    canal = canal if canal in ("cine", "streaming") else "cine"
    # Depuis la page Futur, le film n'est pas encore en base : on l'ajoute.
    if not titre_id and data.get("tmdb_id"):
        typ = data.get("type", "film")
        try:
            detail = (get_tmdb().movie(data["tmdb_id"]) if typ == "film"
                      else get_tmdb().tv(data["tmdb_id"]))
        except TMDBError as exc:
            return jsonify(error=str(exc)), 502
        titre_id = sync.upsert_titre(detail, "a_voir")
    if not db.q1("SELECT id FROM titres WHERE id = ?", (titre_id,)):
        return jsonify(error="Titre introuvable."), 404
    import time
    db.run("INSERT OR REPLACE INTO alertes (titre_id, canal, cree) VALUES (?,?,?)",
           (titre_id, canal, int(time.time())))
    return jsonify(ok=True, id=titre_id)


@bp.delete("/alerts/<int:titre_id>")
@auth.login_required
def delete(titre_id):
    db.run("DELETE FROM alertes WHERE titre_id = ?", (titre_id,))
    return jsonify(ok=True)
