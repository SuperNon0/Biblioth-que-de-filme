#!/usr/bin/env python3
"""cinéthèque — bibliothèque personnelle de films et séries.

Point d'entrée de l'application Flask. Assemble la configuration, la base de
données SQLite et les blueprints (pages, bibliothèque, fiches, découverte,
listes, alertes, statistiques, paramètres).

Lancement :
    PANEL_CONFIG=/etc/cinetheque/config.json python3 app.py
En développement, sans config déployée, l'app tourne avec des valeurs par
défaut et une base locale dans ./.data/.
"""
import json
import os

from flask import Flask, session, url_for

import auth
import config as config_module
import db
import permissions
import settings_store


def _legacy_admin_hash(cfg):
    """Récupère le hash du mot de passe admin existant (users.json puis config).

    Permet d'amorcer le super-admin de base avec le mot de passe DÉJÀ en place,
    pour que la connexion locale continue de fonctionner après la migration.
    """
    try:
        with open(cfg.get("users_file", ""), encoding="utf-8") as handle:
            users = json.load(handle)
        if isinstance(users, dict) and users.get("admin"):
            return users["admin"]
    except (OSError, ValueError):
        pass
    return cfg.get("panel_password_hash") or None


def create_app():
    cfg = config_module.load()
    app = Flask(__name__)
    app.secret_key = cfg["secret_key"]
    app.config.update(
        APP_CONFIG=cfg,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_HTTPONLY=True,
        JSON_AS_ASCII=False,
    )

    db.init(cfg["db_file"])
    # Amorce le super-admin de base + cloisonne le contenu existant (idempotent,
    # sauvegarde .bak posée au 1er passage). Le hash reprend le mot de passe
    # admin déjà en place pour ne pas casser la connexion locale.
    with app.app_context():
        db.bootstrap_accounts(
            superadmin_email=cfg.get("superadmin_email") or cfg.get("cf_access_email") or "",
            superadmin_hash=_legacy_admin_hash(cfg))

    # Cache-busting : suffixe de version basé sur la date de modif du fichier.
    @app.template_global()
    def asset(filename):
        try:
            version = int(os.path.getmtime(
                os.path.join(app.static_folder, filename)))
        except OSError:
            version = 0
        return url_for("static", filename=filename) + f"?v={version}"

    # Auto-login Cloudflare Access (sinon mot de passe requis).
    @app.before_request
    def _sso():
        auth.cloudflare_sso()

    # Contexte partagé des templates : état TMDB, bandeau d'impersonation,
    # helper de permissions `can(...)`, rôle courant.
    @app.context_processor
    def _inject():
        imp = None
        if session.get("impersonator_id"):
            c = auth.current_compte()
            imp = {"email": (c["email"] if c and c["email"] else "ce membre")}
        return {"tmdb_ok": bool(settings_store.get("tmdb_api_key")),
                "impersonation": imp,
                "can": permissions.has_capability,
                "is_super_admin": auth.is_super_admin()}

    _register_blueprints(app)
    # Pas de cache sur les réponses d'API (états temps réel).
    @app.after_request
    def _no_store(resp):
        if resp.mimetype == "application/json":
            resp.headers["Cache-Control"] = "no-store"
        return resp

    # Planificateur de notifications (nouveaux épisodes, sorties) en arrière-plan.
    from services import scheduler
    scheduler.start(app)

    return app


def _register_blueprints(app):
    from routes import (accounts_routes, alerts, auth_routes, discover, library,
                        lists, pages, people, settings, stats, titles)
    for module in (pages, auth_routes, accounts_routes, library, titles,
                   discover, lists, alerts, people, stats, settings):
        app.register_blueprint(module.bp)


app = create_app()

if __name__ == "__main__":
    cfg = app.config["APP_CONFIG"]
    app.run(host=cfg.get("bind", "0.0.0.0"),
            port=int(cfg.get("panel_port", 8080)), threaded=True)
