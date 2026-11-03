"""Pages HTML et service des médias.

Regroupe les routes qui renvoient des pages (index, login, mot de passe
oublié) et la route qui sert les affiches mises en cache localement.
"""
from pathlib import Path

from flask import (Blueprint, current_app, redirect, render_template, request,
                   send_from_directory, session, url_for)

import auth
import settings_store
from context import cfg

bp = Blueprint("pages", __name__)


@bp.get("/")
@auth.login_required
def index():
    # Première installation : si la clé TMDB n'est pas encore configurée, on
    # dirige vers l'accueil de configuration (sauf si l'admin a choisi « plus tard »).
    if not settings_store.get("tmdb_api_key") and not session.get("onboarding_skip"):
        return redirect(url_for("pages.bienvenue"))
    return render_template("index.html")


@bp.get("/bienvenue")
@auth.login_required
def bienvenue():
    """Fiche d'aide de première installation : créer et saisir la clé TMDB."""
    if request.args.get("skip"):
        session["onboarding_skip"] = True
        return redirect(url_for("pages.index"))
    return render_template("bienvenue.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    # GET /login redirige vers le parcours de connexion (gateway) : c'est lui qui
    # décide quel écran montrer (login local, demande, attente, refus, bloqué).
    if request.method == "GET":
        return redirect(url_for("auth.gateway"))
    if not cfg().get("allow_local_login", True):
        return render_template("login.html", error="Connexion locale désactivée."), 403
    attente = auth.attente_login()
    if attente:  # après un échec, le mot de passe suivant attend (anti-force brute)
        return render_template("login.html",
                               error=f"Trop d'essais : réessaie dans {attente} s."), 429
    if auth.do_login(request.form.get("password", "")):
        return redirect(url_for("pages.index"))
    return render_template("login.html", error="Mot de passe incorrect.")


@bp.get("/mot-de-passe-oublie")
def forgot_password():
    return render_template("forgot.html")


@bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.gateway"))


@bp.get("/sw.js")
def service_worker():
    """Sert le service worker à la racine (portée « / » pour la PWA).

    Le nom de sa copie locale suit la version du site (« cinetheque-28.0 ») :
    à chaque mise à jour, l'ancienne copie est effacée toute seule."""
    from routes.settings import numero_version
    chemin = Path(current_app.static_folder) / "sw.js"
    version = numero_version() or str(int(chemin.stat().st_mtime))
    resp = current_app.response_class(
        chemin.read_text(encoding="utf-8").replace("__VERSION__", version),
        mimetype="application/javascript")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["Service-Worker-Allowed"] = "/"
    return resp


@bp.get("/media/<path:name>")
@auth.login_required
def media(name):
    """Sert une affiche/image mise en cache localement."""
    posters_dir = Path(cfg()["posters_dir"]).resolve()
    resp = send_from_directory(posters_dir, name)
    # Le nom du fichier dérive de l'URL d'origine : son contenu ne change jamais.
    # Sans cela (no-cache par défaut), chaque affiche était revalidée auprès du
    # serveur à chaque ouverture de la bibliothèque (le service worker ne met
    # pas /media/ en cache). « private » : pas de cache côté Cloudflare.
    if resp.status_code in (200, 304):
        resp.headers["Cache-Control"] = "private, max-age=31536000, immutable"
    return resp
