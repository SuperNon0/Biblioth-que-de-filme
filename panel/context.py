"""Accès partagé au contexte applicatif (config + client TMDB).

Petites fonctions utilitaires appelées par les blueprints pour éviter de
répéter l'accès à ``current_app`` partout.
"""
from flask import current_app

import settings_store
from tmdb import TMDB


def cfg():
    return current_app.config["APP_CONFIG"]


def get_tmdb():
    """Client TMDB configuré depuis les réglages éditables (magasin > config)."""
    return TMDB(settings_store.get("tmdb_api_key") or "",
                language=settings_store.get("tmdb_language") or "fr-FR",
                region=settings_store.get("tmdb_region") or "FR")
