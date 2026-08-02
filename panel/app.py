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
import os

from flask import Flask, session, url_for

import auth
import config as config_module
import db
import settings_store


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

    # Réglages exposés aux templates (état de configuration TMDB).
    @app.context_processor
    def _inject():
        return {"tmdb_ok": bool(settings_store.get("tmdb_api_key"))}

    _register_blueprints(app)
    # Pas de cache sur les réponses d'API (états temps réel).
    @app.after_request
    def _no_store(resp):
        if resp.mimetype == "application/json":
            resp.headers["Cache-Control"] = "no-store"
        return resp

    return app


def _register_blueprints(app):
    from routes import (alerts, discover, library, lists, pages, settings,
                        stats, titles)
    for module in (pages, library, titles, discover, lists, alerts, stats,
                   settings):
        app.register_blueprint(module.bp)


app = create_app()

if __name__ == "__main__":
    cfg = app.config["APP_CONFIG"]
    app.run(host=cfg.get("bind", "0.0.0.0"),
            port=int(cfg.get("panel_port", 8080)), threaded=True)
