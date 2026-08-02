"""Authentification de cinéthèque.

Compte unique ``admin`` (pas de champ identifiant, juste un mot de passe),
conforme au socle de référence :
- mot de passe haché (``werkzeug.security`` / scrypt) ;
- modifiable dans les paramètres du site ;
- réinitialisable depuis le terminal (``scripts/reset-admin-password.sh``) ;
- auto-login optionnel derrière Cloudflare Access.

Le hash est stocké dans ``users.json`` (inscriptible par l'utilisateur du
service), avec repli sur le hash d'installation présent dans la config.
"""
import json
import threading
import time
from functools import wraps
from pathlib import Path

from flask import current_app, jsonify, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

_lock = threading.Lock()


def _users_path():
    return Path(current_app.config["APP_CONFIG"]["users_file"])


def load_users():
    """Comptes du panel. Migre depuis le hash d'installation au 1er accès."""
    cfg = current_app.config["APP_CONFIG"]
    try:
        with open(_users_path(), encoding="utf-8") as handle:
            users = json.load(handle)
        if isinstance(users, dict) and users:
            return users
    except (OSError, ValueError):
        pass
    users = {"admin": cfg.get("panel_password_hash", "")}
    try:
        save_users(users)
    except OSError:
        pass
    return users


def save_users(users):
    path = _users_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(users, handle, indent=2)


def verify(password):
    with _lock:
        stored = load_users().get("admin")
    return bool(stored and check_password_hash(stored, password))


def set_password(password):
    if len(password) < 8:
        raise ValueError("Le mot de passe doit faire au moins 8 caractères.")
    with _lock:
        users = load_users()
        users["admin"] = generate_password_hash(password)
        save_users(users)


def cloudflare_sso():
    """Connexion auto si la requête passe par Cloudflare Access (en-tête signé).

    En accès LAN direct, l'en-tête est absent → le mot de passe reste exigé.
    Un email autorisé peut être configuré pour n'accepter que le tien.
    """
    if session.get("logged_in"):
        return
    email = request.headers.get("Cf-Access-Authenticated-User-Email", "").strip()
    if not email:
        return
    allowed = (current_app.config["APP_CONFIG"].get("cf_access_email") or "").strip().lower()
    if allowed and email.lower() != allowed:
        return
    session.update(logged_in=True, user="admin", via="cloudflare")


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            if request.path.startswith("/api/"):
                return jsonify(error="Non authentifié"), 401
            return redirect(url_for("pages.login"))
        return view(*args, **kwargs)
    return wrapper


def do_login(password):
    """Tente la connexion ; renvoie True si réussie (freine la force brute)."""
    if verify(password):
        session.update(logged_in=True, user="admin", via="panel")
        return True
    time.sleep(1)
    return False
