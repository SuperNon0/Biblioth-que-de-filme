"""Cache local des affiches et images.

Quand un titre est ajouté à la bibliothèque, son affiche (et éventuellement
les images d'épisodes) est téléchargée une fois et servie localement ensuite :
affichage rapide et bibliothèque consultable même si TMDB est lent/indispo.

Les fichiers vivent dans ``posters_dir`` (config) et sont servis via la route
``/media/<fichier>``.
"""
import hashlib
import http.client
import os
import tempfile
import urllib.request
from pathlib import Path


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
    tmp = None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "cinetheque"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
        # Fichier temporaire puis renommage atomique : jamais d'affiche à moitié
        # écrite servie, et plus de verrou global (les téléchargements d'un
        # import de liste passaient l'un après l'autre).
        fd, tmp = tempfile.mkstemp(dir=dest.parent, prefix=".dl-")
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, dest)
        tmp = None
        return name
    except (OSError, ValueError, http.client.HTTPException):
        return None
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass


def local_url(name):
    """URL servie par le site pour une image mise en cache."""
    return f"/media/{name}" if name else None
