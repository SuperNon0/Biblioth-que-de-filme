"""Pages HTML et service des médias.

Regroupe les routes qui renvoient des pages (index, login, mot de passe
oublié) et la route qui sert les affiches mises en cache localement.
"""
from pathlib import Path

from flask import (Blueprint, redirect, render_template, request,
                   send_from_directory, session, url_for)

import auth
from context import cfg

bp = Blueprint("pages", __name__)


@bp.get("/")
@auth.login_required
def index():
    return render_template("index.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if auth.do_login(request.form.get("password", "")):
            return redirect(url_for("pages.index"))
        error = "Mot de passe incorrect."
    return render_template("login.html", error=error)


@bp.get("/mot-de-passe-oublie")
def forgot_password():
    return render_template("forgot.html")


@bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("pages.login"))


@bp.get("/media/<path:name>")
@auth.login_required
def media(name):
    """Sert une affiche/image mise en cache localement."""
    posters_dir = Path(cfg()["posters_dir"]).resolve()
    return send_from_directory(posters_dir, name)
