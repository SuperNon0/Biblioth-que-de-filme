"""Parcours de connexion (gateway) — auth v2.

`gateway()` implémente l'arbre de décision de la spec §4 :

    cf_access_email() ?
       ├─ None (accès LAN)     → login.html (mot de passe super-admin)
       └─ e-mail vérifié :
            compte inexistant  → demande.html (site géré)  /  auto-actif (site perso)
            etat == pending    → attente.html
            etat == refused    → refus.html
            etat == bloque     → bloque.html
            etat == actif      → connexion puis application
"""
import time

from flask import (Blueprint, redirect, render_template, request, session,
                   url_for)

import auth
import db

bp = Blueprint("auth", __name__, url_prefix="/acces")


def _view_email(email):
    return {"email": email}


@bp.get("")
def gateway():
    """Point d'entrée du parcours de connexion (redirige l'app si déjà connecté)."""
    c = auth.current_compte()
    if c and c["etat"] == "actif":
        return redirect(url_for("pages.index"))

    email = auth.cf_access_email()
    if not email:
        # Accès LAN (hors Cloudflare) : mot de passe du super-admin de base.
        return render_template("login.html", error=None)

    row = db.q1("SELECT * FROM comptes WHERE email = ?", (email,))
    if row is None:
        # Site « perso » : cloudflare_sso() a normalement déjà créé+connecté.
        # Site « géré » : on propose de demander un accès.
        return render_template("demande.html", **_view_email(email))
    etat = row["etat"]
    if etat == "actif":
        auth.login_compte(row)
        return redirect(url_for("pages.index"))
    if etat == "pending":
        return render_template("attente.html", envoye=row["cree"], **_view_email(email))
    if etat == "refused":
        return render_template("refus.html", **_view_email(email))
    if etat == "bloque":
        return render_template("bloque.html", **_view_email(email))
    return render_template("demande.html", **_view_email(email))


@bp.post("/demande")
def request_access():
    """Crée (ou ré-active) une demande d'accès `pending` pour l'e-mail Cloudflare."""
    email = auth.cf_access_email()
    if not email:
        return redirect(url_for("auth.gateway"))
    now = int(time.time())
    row = db.q1("SELECT id, etat FROM comptes WHERE email = ?", (email,))
    if row is None:
        db.run("INSERT INTO comptes (email, role, etat, cree) VALUES (?, 'membre', 'pending', ?)",
               (email, now))
        db.audit("demande_acces", acteur=email, cible=email)
    elif row["etat"] == "refused":
        db.run("UPDATE comptes SET etat = 'pending', cree = ? WHERE id = ?", (now, row["id"]))
        db.audit("redemande_acces", acteur=email, cible=email)
    return redirect(url_for("auth.gateway"))
