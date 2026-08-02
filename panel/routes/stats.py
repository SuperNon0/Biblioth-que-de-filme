"""Statistiques du profil (temps passé, compteurs, genres, par année)."""
from flask import Blueprint, jsonify

import auth
from services import statistics

bp = Blueprint("stats", __name__, url_prefix="/api")


@bp.get("/stats")
@auth.login_required
def stats():
    return jsonify(statistics.resume())
