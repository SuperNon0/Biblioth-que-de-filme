"""Gestion des comptes / profils + impersonation + mot de passe (auth v2 §5/§6).

Sur un site « perso » (account_management=off), l'écran est un écran **Profils**
(voir + « se mettre à leur place »). Sur un site « géré » (hub), c'est la
gestion complète (valider / refuser / bloquer / supprimer).
"""
import time

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

import auth
import db
from permissions import has_capability, require_capability

bp = Blueprint("accounts", __name__)


def _fmt(ts):
    return time.strftime("%d/%m/%Y", time.localtime(ts)) if ts else None


def _row_to_view(r):
    return {"id": r["id"], "email": r["email"], "role": r["role"], "etat": r["etat"],
            "local": bool(r["mdp_hash"]), "cree": _fmt(r["cree"]),
            "derniere_cnx": _fmt(r["derniere_cnx"])}


def _guard_manage():
    """Accès à la vue comptes/profils : au moins une capability comptes/profils."""
    return has_capability("account_management") or has_capability("profiles")


# ── Écran (page) ─────────────────────────────────────────────────────────────
@bp.get("/parametres/comptes")
@auth.super_admin_required
def comptes_page():
    if not _guard_manage():
        return redirect(url_for("pages.index"))
    rows = db.q("SELECT * FROM comptes ORDER BY "
                "CASE etat WHEN 'pending' THEN 0 ELSE 1 END, id")
    pending = [_row_to_view(r) for r in rows if r["etat"] == "pending"]
    membres = [_row_to_view(r) for r in rows if r["etat"] != "pending"]
    return render_template("comptes.html", pending=pending, membres=membres,
                           gere=has_capability("account_management"),
                           peut_profils=has_capability("profiles"),
                           base_admin=auth.is_base_admin())


# ── API : liste ──────────────────────────────────────────────────────────────
@bp.get("/api/comptes")
@auth.super_admin_required
def api_comptes():
    rows = db.q("SELECT * FROM comptes ORDER BY id")
    return jsonify(comptes=[_row_to_view(r) for r in rows])


# ── API : transitions d'état (site géré) ────────────────────────────────────
def _set_etat(compte_id, etat, champ_ts=None):
    now = int(time.time())
    if champ_ts:
        db.run(f"UPDATE comptes SET etat=?, {champ_ts}=? WHERE id=?", (etat, now, compte_id))
    else:
        db.run("UPDATE comptes SET etat=? WHERE id=?", (etat, compte_id))


@bp.post("/api/comptes/<int:compte_id>/valider")
@require_capability("account_management")
def valider(compte_id):
    c = auth.get_compte(compte_id)
    if not c:
        return jsonify(error="Compte introuvable"), 404
    _set_etat(compte_id, "actif", "valide")
    db.ensure_system_lists(compte_id)
    db.audit("valider_compte", acteur=_acteur(), cible=c["email"])
    return jsonify(ok=True)


@bp.post("/api/comptes/<int:compte_id>/refuser")
@require_capability("account_management")
def refuser(compte_id):
    c = auth.get_compte(compte_id)
    if not c:
        return jsonify(error="Compte introuvable"), 404
    _set_etat(compte_id, "refused")
    db.audit("refuser_compte", acteur=_acteur(), cible=c["email"])
    return jsonify(ok=True)


@bp.post("/api/comptes/<int:compte_id>/bloquer")
@require_capability("account_management")
def bloquer(compte_id):
    c = auth.get_compte(compte_id)
    if not c:
        return jsonify(error="Compte introuvable"), 404
    if c["role"] == "super_admin":
        return jsonify(error="On ne bloque pas un super-admin."), 400
    _set_etat(compte_id, "bloque", "bloque")
    db.audit("bloquer_compte", acteur=_acteur(), cible=c["email"])
    return jsonify(ok=True)


@bp.post("/api/comptes/<int:compte_id>/debloquer")
@require_capability("account_management")
def debloquer(compte_id):
    c = auth.get_compte(compte_id)
    if not c:
        return jsonify(error="Compte introuvable"), 404
    _set_etat(compte_id, "actif")
    db.audit("debloquer_compte", acteur=_acteur(), cible=c["email"])
    return jsonify(ok=True)


@bp.delete("/api/comptes/<int:compte_id>")
@require_capability("account_management")
def supprimer(compte_id):
    c = auth.get_compte(compte_id)
    if not c:
        return jsonify(error="Compte introuvable"), 404
    if c["role"] == "super_admin" and _compter_super_admins() <= 1:
        return jsonify(error="Le dernier super-admin est indestructible."), 400
    db.run("DELETE FROM comptes WHERE id=?", (compte_id,))  # CASCADE efface son contenu
    db.audit("supprimer_compte", acteur=_acteur(), cible=c["email"])
    return jsonify(ok=True)


# ── API : rôle (super-admin) — réservé au compte de base ─────────────────────
@bp.post("/api/comptes/<int:compte_id>/role")
def changer_role(compte_id):
    if not auth.is_base_admin() or session.get("impersonator_id"):
        return jsonify(error="Réservé au compte administrateur de base."), 403
    role = (request.get_json(silent=True) or {}).get("role")
    if role not in ("membre", "super_admin"):
        return jsonify(error="Rôle invalide"), 400
    c = auth.get_compte(compte_id)
    if not c:
        return jsonify(error="Compte introuvable"), 404
    if c["role"] == "super_admin" and role == "membre" and _compter_super_admins() <= 1:
        return jsonify(error="Le dernier super-admin est indestructible."), 400
    db.run("UPDATE comptes SET role=? WHERE id=?", (role, compte_id))
    db.audit("changer_role", acteur=_acteur(), cible=c["email"], detail=role)
    return jsonify(ok=True)


# ── API : impersonation « voir en tant que » ─────────────────────────────────
@bp.post("/api/comptes/<int:compte_id>/impersonate")
@require_capability("profiles")
def impersonate(compte_id):
    if session.get("impersonator_id"):
        return jsonify(error="Impersonation déjà active."), 400
    cible = auth.get_compte(compte_id)
    if not cible or cible["etat"] != "actif":
        return jsonify(error="Compte cible invalide."), 400
    if cible["role"] == "super_admin":
        return jsonify(error="On n'impersonne pas un super-admin."), 400
    session["impersonator_id"] = session["compte_id"]
    session["compte_id"] = cible["id"]
    db.audit("impersonate_start", acteur=_acteur(), cible=cible["email"])
    return jsonify(ok=True)


@bp.post("/api/impersonate/stop")
def impersonate_stop():
    imp = session.get("impersonator_id")
    if not imp:
        return jsonify(error="Aucune impersonation active."), 400
    cible = auth.get_compte(session.get("compte_id"))
    session["compte_id"] = imp
    session.pop("impersonator_id", None)
    db.audit("impersonate_stop", acteur=_acteur(), cible=cible["email"] if cible else None)
    return jsonify(ok=True)


# ── API : mot de passe administrateur ────────────────────────────────────────
@bp.post("/api/admin/password")
@require_capability("admin_password")
def changer_mdp():
    if session.get("impersonator_id"):
        return jsonify(error="Impossible pendant une impersonation."), 400
    data = request.get_json(silent=True) or {}
    if not auth.do_login_check(data.get("actuel", "")):
        return jsonify(error="Mot de passe actuel incorrect."), 400
    try:
        auth.set_password(data.get("nouveau", ""))
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    db.audit("changer_mdp", acteur=_acteur())
    return jsonify(ok=True)


# ── helpers ──────────────────────────────────────────────────────────────────
def _acteur():
    real = auth.get_compte(session.get("impersonator_id") or session.get("compte_id"))
    return real["email"] if real and real["email"] else "admin"


def _compter_super_admins():
    r = db.q1("SELECT COUNT(*) AS n FROM comptes WHERE role='super_admin'")
    return r["n"] if r else 0
