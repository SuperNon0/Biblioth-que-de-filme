"""Permissions (capabilities) configurables par site — socle « site-base ».

Chaque fonctionnalité sensible a un niveau requis, choisi à la création du site
(docs/permissions.md) :

    off          → personne (désactivée sur ce site)
    membre       → tout compte actif
    super_admin  → super-admin uniquement

Le niveau vient de la config `cap_<clé>` (config.json / env). Cas particulier :
`account_management` pilote aussi le modèle d'accès (voir auth.access_managed()).
"""
from functools import wraps

from flask import current_app, jsonify, redirect, request, url_for

import auth

LEVELS = ("off", "membre", "super_admin")

# clé → (libellé, description, niveau par défaut)
CAPABILITIES = {
    "account_management": (
        "Gestion des comptes",
        "Demandes d'accès, validation, refus, blocage, suppression, rôles. "
        "Désactivée = site « perso » (utilisateurs auto-créés en actif).",
        "super_admin"),
    "profiles": (
        "Profils & « se mettre à leur place »",
        "Voir les profils et les impersonner. N'a de sens que sur un site à "
        "données cloisonnées (chacun ses films).",
        "super_admin"),
    "admin_password": (
        "Mot de passe administrateur",
        "Changer le mot de passe admin dans les Paramètres.",
        "super_admin"),
    "site_update": (
        "Mise à jour du site",
        "Bouton « Mettre à jour » (git + redémarrage) et /api/system/*.",
        "super_admin"),
}


def capability_level(key):
    default = CAPABILITIES[key][2]
    val = (current_app.config["APP_CONFIG"].get(f"cap_{key}") or default).strip().lower()
    return val if val in LEVELS else default


def has_capability(key):
    level = capability_level(key)
    if level == "off":
        return False
    if level == "super_admin":
        return auth.is_super_admin()
    if auth.is_super_admin():
        return True
    c = auth.current_compte()
    return bool(c and c["etat"] == "actif")


def any_admin_capability():
    """Vrai si l'utilisateur a au moins une capability (→ accès aux Paramètres)."""
    return any(has_capability(k) for k in CAPABILITIES)


def require_capability(key):
    """Décorateur : exige la capability. 403 JSON sur /api/*, sinon redirige."""
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if auth.current_compte() is None:
                if request.path.startswith("/api/"):
                    return jsonify(error="Non authentifié"), 401
                return redirect(url_for("auth.gateway"))
            if not has_capability(key):
                if request.path.startswith("/api/"):
                    return jsonify(error="Action non autorisée"), 403
                return redirect(url_for("pages.index"))
            return view(*args, **kwargs)
        return wrapper
    return decorator
