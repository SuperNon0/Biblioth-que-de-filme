"""Statistiques du profil (temps passé, compteurs, genres, par année)."""
from flask import Blueprint, jsonify

import auth
from services import statistics

bp = Blueprint("stats", __name__, url_prefix="/api")


@bp.get("/stats")
@auth.login_required
def stats():
    return jsonify(statistics.resume())


@bp.get("/journal")
@auth.login_required
def journal():
    """Historique de visionnage : chaque marquage (film / série / saison /
    épisode) avec son affiche et son horodatage (date + heure), du + récent."""
    import db
    events = db.q(
        """SELECT j.id, j.type, j.label, j.cree,
                  t.id AS titre_id, t.titre, t.affiche, t.type AS media
           FROM journal j JOIN titres t ON t.id = j.titre_id
           ORDER BY j.cree DESC, j.id DESC LIMIT 300"""
    )
    return jsonify(events=events)


@bp.delete("/journal/<int:event_id>")
@auth.login_required
def del_journal(event_id):
    """Supprime une entrée du journal (correction), sans toucher aux compteurs."""
    import db
    db.run("DELETE FROM journal WHERE id = ?", (event_id,))
    return jsonify(ok=True)
