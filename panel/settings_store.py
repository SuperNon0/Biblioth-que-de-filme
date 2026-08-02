"""Réglages modifiables par l'utilisateur (inscriptibles à l'exécution).

La config ``/etc/cinetheque/config.json`` est posée à l'installation et
appartient à root (lecture seule pour le service). Les réglages que l'admin
change depuis l'interface (clé API TMDB, région, email Cloudflare) sont donc
stockés à part dans ``<data_dir>/settings.json``, inscriptible par le service.

À la lecture, ces réglages priment sur les valeurs de la config de base.
"""
import json
import threading
from pathlib import Path

from flask import current_app

_lock = threading.Lock()

# Clés éditables depuis l'interface et leur valeur par défaut.
EDITABLES = {
    "tmdb_api_key": "",
    "tmdb_language": "fr-FR",
    "tmdb_region": "FR",
    "cf_access_email": "",
}


def _path():
    return Path(current_app.config["APP_CONFIG"]["data_dir"]) / "settings.json"


def _read_file():
    try:
        with open(_path(), encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def get(key):
    """Valeur effective : réglage utilisateur, sinon config de base, sinon défaut."""
    stored = _read_file()
    if key in stored:
        return stored[key]
    return current_app.config["APP_CONFIG"].get(key, EDITABLES.get(key))


def all_public():
    """Réglages exposés à l'interface (la clé TMDB est masquée si présente)."""
    return {
        "tmdb_configuree": bool(get("tmdb_api_key")),
        "tmdb_language": get("tmdb_language"),
        "tmdb_region": get("tmdb_region"),
        "cf_access_email": get("cf_access_email"),
    }


def update(values):
    with _lock:
        data = _read_file()
        for key, value in values.items():
            if key in EDITABLES and value is not None:
                data[key] = value
        path = _path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
