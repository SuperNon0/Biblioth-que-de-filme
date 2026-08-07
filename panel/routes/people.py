"""Fiches personnes (acteurs / réalisateurs).

Depuis la fiche d'un titre, un clic sur un membre du casting ouvre la fiche de
la personne : ses infos et sa filmographie (films et séries), cliquables pour
les ajouter à la bibliothèque.
"""
from flask import Blueprint, jsonify

import auth
from context import get_tmdb
from routes.library import annotate_library
from tmdb import TMDBError

bp = Blueprint("people", __name__, url_prefix="/api")


@bp.get("/person/<int:person_id>")
@auth.login_required
def person(person_id):
    try:
        data = get_tmdb().person(person_id)
    except TMDBError as exc:
        return jsonify(error=str(exc)), 502
    # Étiquette le statut (Vu / À voir / En cours) et l'id local des films/séries
    # de la filmographie déjà en bibliothèque → badges + menu rapide fonctionnel.
    data["films"] = annotate_library(data.get("films", []))
    return jsonify(data)
