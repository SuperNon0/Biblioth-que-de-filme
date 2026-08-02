"""Fiches personnes (acteurs / réalisateurs).

Depuis la fiche d'un titre, un clic sur un membre du casting ouvre la fiche de
la personne : ses infos et sa filmographie (films et séries), cliquables pour
les ajouter à la bibliothèque.
"""
from flask import Blueprint, jsonify

import auth
from context import get_tmdb
from tmdb import TMDBError

bp = Blueprint("people", __name__, url_prefix="/api")


@bp.get("/person/<int:person_id>")
@auth.login_required
def person(person_id):
    try:
        return jsonify(get_tmdb().person(person_id))
    except TMDBError as exc:
        return jsonify(error=str(exc)), 502
