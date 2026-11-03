"""Préférences d'affichage, propres à chaque compte.

Couleur d'accent, thème clair/sombre, taille des affiches, titres sous les
affiches, vue de la bibliothèque, grande carte « Reprendre » et rangées de
l'accueil (ordre + celles à masquer). Rangées dans ``app_settings`` sous la clé
``prefs:<compte_id>`` (JSON). Le serveur pose l'accent et le thème sur
``<html>`` dès le premier rendu : aucune couleur ne « clignote » au chargement.
"""
import json

from flask import Blueprint, jsonify, request

import auth
import db

bp = Blueprint("prefs", __name__, url_prefix="/api")

ACCENTS = ("or", "ambre", "corail", "menthe", "lavande")
THEMES = ("auto", "sombre", "clair")
AFFICHES = ("s", "m", "l")
VUES = ("grille", "liste", "rangees")
REPRENDRE = ("carte", "rangee")

# Rangées de l'accueil, dans l'ordre d'origine : (clé, libellé des réglages).
RANGEES = (
    ("reprendre", "Reprendre"),
    ("perso", "Parce que tu as aimé…"),
    ("tendances", "Tendances cette semaine"),
    ("cinema", "Au cinéma en ce moment"),
    ("bientot", "Bientôt au cinéma"),
    ("tv_tendances", "Séries tendances"),
    ("genres", "Tes genres préférés"),
    ("pepites", "Pépites à découvrir"),
    ("top", "Les mieux notés"),
    ("pop", "Populaires"),
    ("annees90", "Cultes des années 90"),
)

DEFAUT = {
    "accent": "lavande",
    "theme": "auto",
    "affiche": "m",
    "legendes": True,
    "vue_biblio": "grille",
    "reprendre": "carte",
    "rangees": [{"id": k, "on": True} for k, _ in RANGEES],
}


def _cle(compte_id):
    return f"prefs:{compte_id}"


def _rangees(valeur):
    """Rangées valides, dans l'ordre choisi ; les nouvelles s'ajoutent à la fin."""
    connues = {k for k, _ in RANGEES}
    out, vues = [], set()
    for r in valeur if isinstance(valeur, list) else []:
        if isinstance(r, dict) and r.get("id") in connues and r["id"] not in vues:
            vues.add(r["id"])
            out.append({"id": r["id"], "on": bool(r.get("on", True))})
    out += [{"id": k, "on": True} for k, _ in RANGEES if k not in vues]
    return out


def lire(compte_id):
    """Préférences d'un compte, complétées par les valeurs par défaut."""
    prefs = dict(DEFAUT)
    if compte_id:
        stocke = db.jload(db.get_setting(_cle(compte_id)), {})
        if isinstance(stocke, dict):
            prefs.update({k: v for k, v in stocke.items() if k in DEFAUT})
    prefs["rangees"] = _rangees(prefs.get("rangees"))
    return _valider(prefs)


def _valider(prefs):
    choix = {"accent": ACCENTS, "theme": THEMES, "affiche": AFFICHES,
             "vue_biblio": VUES, "reprendre": REPRENDRE}
    for cle, valeurs in choix.items():
        if prefs.get(cle) not in valeurs:
            prefs[cle] = DEFAUT[cle]
    prefs["legendes"] = bool(prefs.get("legendes"))
    return prefs


@bp.get("/prefs")
@auth.login_required
def get_prefs():
    return jsonify(prefs=lire(auth.compte_courant_id()),
                   rangees=[{"id": k, "nom": n} for k, n in RANGEES])


@bp.post("/prefs")
@auth.login_required
def set_prefs():
    """Enregistre les préférences envoyées (seules les clés connues sont gardées)."""
    cid = auth.compte_courant_id()
    data = request.get_json(silent=True) or {}
    prefs = lire(cid)
    for cle in DEFAUT:
        if cle in data:
            prefs[cle] = data[cle]
    prefs["rangees"] = _rangees(prefs.get("rangees"))
    prefs = _valider(prefs)
    db.set_setting(_cle(cid), json.dumps(prefs, ensure_ascii=False))
    return jsonify(ok=True, prefs=prefs)
