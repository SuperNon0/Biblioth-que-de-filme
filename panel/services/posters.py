"""Cache local des affiches et images.

Quand un titre est ajouté à la bibliothèque, son affiche (et éventuellement
les images d'épisodes) est téléchargée une fois et servie localement ensuite :
affichage rapide et bibliothèque consultable même si TMDB est lent/indispo.

Les fichiers vivent dans ``posters_dir`` (config) et sont servis via la route
``/media/<fichier>``.
"""
import hashlib
import threading
import urllib.request
from pathlib import Path

_lock = threading.Lock()


def _dir(app):
    d = Path(app.config["APP_CONFIG"]["posters_dir"])
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache(app, url):
    """Télécharge une image distante et renvoie son nom de fichier local.

    Renvoie ``None`` en cas d'échec (l'appelant retombe alors sur l'URL TMDB).
    Idempotent : une même URL n'est téléchargée qu'une fois.
    """
    if not url:
        return None
    name = hashlib.sha1(url.encode()).hexdigest()[:20] + Path(url).suffix
    dest = _dir(app) / name
    if dest.exists():
        return name
    try:
        with _lock:
            if dest.exists():
                return name
            req = urllib.request.Request(url, headers={"User-Agent": "cinetheque"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read()
            dest.write_bytes(data)
        return name
    except (OSError, ValueError):
        return None


def local_url(name):
    """URL servie par le site pour une image mise en cache."""
    return f"/media/{name}" if name else None
