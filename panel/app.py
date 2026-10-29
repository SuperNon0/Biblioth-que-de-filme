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
import base64
import json
import os
import time

from flask import Flask, jsonify, request, session, url_for

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
    # Fuseau du site (« aujourd'hui » des épisodes diffusés, des alertes…) :
    # un LXC tourne souvent en UTC, soit la veille entre minuit et 2 h à Paris.
    if cfg.get("timezone") and not os.environ.get("TZ"):
        os.environ["TZ"] = cfg["timezone"]
        time.tzset()
    app = Flask(__name__)
    app.secret_key = cfg["secret_key"]
    app.config.update(
        APP_CONFIG=cfg,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_HTTPONLY=True,
        JSON_AS_ASCII=False,
        # Garde-fou sur la taille des envois (import d'une sauvegarde JSON).
        MAX_CONTENT_LENGTH=64 * 1024 * 1024,
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

    # Icône d'accueil iPhone INTÉGRÉE À LA PAGE (data URI base64), plutôt que
    # servie comme fichier séparé : le site est derrière Cloudflare Access, et
    # l'iPhone qui télécharge l'icône dans une requête à part peut recevoir la
    # page de connexion Cloudflare au lieu de l'image. En l'intégrant, iOS n'a
    # rien à télécharger → le logo s'affiche sans ouvrir de règle Cloudflare.
    # Source : panel/static/apple-touch-icon.png (PNG carré plein, opaque, 180px).
    _apple_icon = {}

    @app.template_global()
    def apple_touch_icon():
        if "uri" not in _apple_icon:
            try:
                with open(os.path.join(app.static_folder, "apple-touch-icon.png"), "rb") as fh:
                    _apple_icon["uri"] = "data:image/png;base64," + \
                        base64.b64encode(fh.read()).decode("ascii")
            except OSError:
                _apple_icon["uri"] = ""
        return _apple_icon["uri"]

    # Anti-CSRF, AVANT l'auto-login : un formulaire posté depuis un autre site
    # arrive sans le cookie de session (SameSite=Lax), mais cloudflare_sso()
    # reconnecterait aussitôt grâce au jeton Cloudflare. Les navigateurs
    # signalent l'origine d'une requête (Sec-Fetch-Site) ; ceux qui ne le font
    # pas doivent poser un en-tête que seul notre propre JS envoie (un
    # formulaire ne le peut pas, un autre site pas sans autorisation CORS).
    @app.before_request
    def _anti_csrf():
        if request.method in ("GET", "HEAD", "OPTIONS") or request.path.startswith("/mcp"):
            return None
        site = request.headers.get("Sec-Fetch-Site")
        if site in ("cross-site", "same-site"):
            return jsonify(error="Requête venue d'un autre site refusée."), 403
        if site is None and request.path.startswith("/api/") \
                and request.headers.get("X-Cinetheque") != "1":
            return jsonify(error="Requête refusée (en-tête X-Cinetheque manquant)."), 403
        return None

    # Auto-login Cloudflare Access (sinon mot de passe requis).
    @app.before_request
    def _sso():
        auth.cloudflare_sso()

    # Filet de sécurité : jamais de transaction (donc de verrou d'écriture)
    # laissée ouverte par une requête en erreur sur la connexion du thread.
    @app.teardown_request
    def _db_cleanup(_exc):
        db.rollback_open()

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
    # Pas de cache sur les réponses d'API (états temps réel). Les fichiers
    # statiques versionnés (?v=… change à chaque modification, voir asset())
    # peuvent, eux, rester en cache sans revalidation à chaque lancement.
    @app.after_request
    def _headers(resp):
        if resp.mimetype == "application/json":
            resp.headers["Cache-Control"] = "no-store"
        elif request.path.startswith("/static/") and request.args.get("v") \
                and resp.status_code == 200:
            resp.headers["Cache-Control"] = "private, max-age=31536000, immutable"
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        return resp

    # Planificateur de notifications (nouveaux épisodes, sorties) en arrière-plan.
    from services import scheduler
    scheduler.start(app)

    return app


def _register_blueprints(app):
    from routes import (accounts_routes, alerts, auth_routes, discover, library,
                        lists, mcp, pages, people, settings, stats, titles)
    for module in (pages, auth_routes, accounts_routes, library, titles,
                   discover, lists, alerts, people, stats, settings, mcp):
        app.register_blueprint(module.bp)


app = create_app()

if __name__ == "__main__":
    cfg = app.config["APP_CONFIG"]
    host, port = cfg.get("bind", "0.0.0.0"), int(cfg.get("panel_port", 8080))
    try:
        # Serveur de production (paquet apt python3-waitress) quand il est là ;
        # sinon serveur de développement de Flask, comme avant.
        from waitress import serve
    except ImportError:
        app.run(host=host, port=port, threaded=True)
    else:
        serve(app, host=host, port=port, threads=16, ident="cinetheque")
