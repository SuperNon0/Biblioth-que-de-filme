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
    # --- Fondation multi-comptes (auth v2, socle « site-base ») ---------------
    "superadmin_email": "",          # e-mail Google du super-admin de base
    "cf_team_domain": "",            # <team>.cloudflareaccess.com (nom seul)
    "cf_aud": "",                    # AUD tag de l'application Access
    "cf_verify_jwt": True,           # vérifier le JWT Cloudflare (prod)
    "allow_local_login": True,       # login local par mot de passe (LAN)
    # Permissions par site — preset « perso » (données cloisonnées). Niveaux :
    # "off" | "membre" | "super_admin". Voir docs/authentification-v2.md.
    "cap_account_management": "off",       # site perso : e-mail CF → compte auto actif
    "cap_profiles": "super_admin",         # « voir en tant que » (impersonation)
    "cap_admin_password": "super_admin",   # changer le mot de passe admin
    "cap_site_update": "super_admin",      # bouton « Mettre à jour le site »
}

# Surcharges possibles par variable d'environnement (systemd `Environment=` ou
# shell), pratiques sans toucher au config.json. clé_config -> VAR_ENV.
_ENV_OVERRIDES = {
    "superadmin_email": "SUPERADMIN_EMAIL",
    "cf_team_domain": "CF_ACCESS_TEAM_DOMAIN",
    "cf_aud": "CF_ACCESS_AUD",
    "cf_verify_jwt": "CF_VERIFY_JWT",
    "allow_local_login": "ALLOW_LOCAL_LOGIN",
    "cap_account_management": "CAP_ACCOUNT_MANAGEMENT",
    "cap_profiles": "CAP_PROFILES",
    "cap_admin_password": "CAP_ADMIN_PASSWORD",
    "cap_site_update": "CAP_SITE_UPDATE",
}


def _as_bool(value):
    return str(value).strip().lower() in ("1", "true", "yes", "on")


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
    # Surcharges par variables d'environnement (prioritaires sur le JSON).
    for key, env in _ENV_OVERRIDES.items():
        if env in os.environ:
            data[key] = os.environ[env]
    # Coercition des booléens (JSON booléen, ou "true"/"1" venus de l'env).
    for key in ("cf_verify_jwt", "allow_local_login"):
        data[key] = _as_bool(data.get(key, DEFAULTS[key]))
    return Config(data)
