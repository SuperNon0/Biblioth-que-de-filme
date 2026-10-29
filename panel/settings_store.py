"""Réglages modifiables par l'utilisateur (inscriptibles à l'exécution).

La config ``/etc/cinetheque/config.json`` est posée à l'installation et
appartient à root (lecture seule pour le service). Les réglages que l'admin
change depuis l'interface (clé API TMDB, région, email Cloudflare) sont donc
stockés à part dans ``<data_dir>/settings.json``, inscriptible par le service.

À la lecture, ces réglages priment sur les valeurs de la config de base.
"""
import json
import os
import tempfile
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
    # Plateformes de streaming auxquelles l'utilisateur est abonné (noms TMDB).
    # Sert à mettre en avant « où regarder » sur les fiches (les autres grisées).
    "mes_plateformes": [],
}

# Ces clés sont renvoyées telles quelles à l'interface (pas de secret sensible).
PUBLIC_KEYS = (
    "tmdb_language", "tmdb_region", "cf_sso_enabled", "cf_access_email",
    "notif_discord_enabled", "botpanel_url", "botpanel_slug_episode",
    "botpanel_slug_cine", "botpanel_slug_streaming", "mes_plateformes",
)


def _path():
    return Path(current_app.config["APP_CONFIG"]["data_dir"]) / "settings.json"


# Dernier contenu lu, gardé tant que le fichier ne change pas : get() est
# appelé des dizaines de fois par page (chaque réglage, chaque client TMDB) et
# relisait puis réanalysait le fichier à chaque fois.
_cache = {"cle": None, "data": {}}


def _read_file():
    path = _path()
    try:
        st = path.stat()
        cle = (str(path), st.st_mtime_ns, st.st_size, st.st_ino)
        if cle != _cache["cle"]:
            with open(path, encoding="utf-8") as handle:
                _cache.update(data=json.load(handle), cle=cle)
    except (OSError, ValueError):
        return {}
    return dict(_cache["data"])


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
        # Fichier temporaire puis renommage : un lecteur ne voit jamais un
        # fichier à moitié écrit (il retombait sur les valeurs par défaut, clé
        # TMDB comprise). mkstemp le crée en 600 : la clé n'est lisible que du service.
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".settings-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2)
            os.replace(tmp, path)
        except BaseException:
            os.unlink(tmp)
            raise
