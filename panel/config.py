"""Chargement de la configuration de cinéthèque.

La config est lue depuis le fichier JSON pointé par la variable
d'environnement ``PANEL_CONFIG`` (défaut ``/etc/cinetheque/config.json``).
Elle contient les secrets (clé de session, hash du mot de passe admin, clé
TMDB) et les chemins/ports. Elle n'est jamais committée.

Un fichier d'exemple (``config.example.json``) documente les champs.
"""
import json
import os
from pathlib import Path

DEFAULTS = {
    "bind": "0.0.0.0",
    "panel_port": 8080,
    "data_dir": "/opt/cinetheque/data",
    "db_file": "/opt/cinetheque/data/library.db",
    "users_file": "/opt/cinetheque/data/users.json",
    "posters_dir": "/opt/cinetheque/data/posters",
    "source_dir": "/opt/cinetheque-src",
    "panel_service_name": "cinetheque-panel",
    "tmdb_api_key": "",
    "tmdb_language": "fr-FR",
    "tmdb_region": "FR",
    "cf_access_email": "",
}


class Config(dict):
    """Config = dict fusionné avec les valeurs par défaut, accès par attribut."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def load():
    path = os.environ.get("PANEL_CONFIG", "/etc/cinetheque/config.json")
    data = dict(DEFAULTS)
    try:
        with open(path, encoding="utf-8") as handle:
            data.update(json.load(handle))
    except FileNotFoundError:
        # Mode dev sans config déployée : on tourne avec les valeurs par défaut
        # et une clé de session éphémère. Suffisant pour lancer en local.
        data.setdefault("secret_key", os.urandom(24).hex())
        for key in ("db_file", "users_file", "posters_dir", "data_dir"):
            data[key] = str(Path("./.data") / Path(data[key]).name) \
                if key != "posters_dir" else "./.data/posters"
    if "secret_key" not in data:
        data["secret_key"] = os.urandom(24).hex()
    return Config(data)
