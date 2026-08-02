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
    # Auto-login Cloudflare Access : activé par défaut (sans effet hors Cloudflare,
    # car l'en-tête est alors absent). Désactivable pour toujours exiger le MDP.
    "cf_sso_enabled": True,
    "cf_access_email": "",
    # Notifications Discord via botpanel (déclenchement par slug).
    "notif_discord_enabled": False,
    "botpanel_url": "",
    "botpanel_slug_episode": "",
    "botpanel_slug_cine": "",
    "botpanel_slug_streaming": "",
    # Notifications ntfy (push direct sur le téléphone, contenu dynamique).
    "notif_ntfy_enabled": False,
    "ntfy_url": "https://ntfy.sh",
    "ntfy_topic": "",
}

# Ces clés sont renvoyées telles quelles à l'interface (pas de secret sensible).
PUBLIC_KEYS = (
    "tmdb_language", "tmdb_region", "cf_sso_enabled", "cf_access_email",
    "notif_discord_enabled", "botpanel_url", "botpanel_slug_episode",
    "botpanel_slug_cine", "botpanel_slug_streaming",
    "notif_ntfy_enabled", "ntfy_url", "ntfy_topic",
)


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
    data = {"tmdb_configuree": bool(get("tmdb_api_key"))}
    for key in PUBLIC_KEYS:
        data[key] = get(key)
    return data


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
