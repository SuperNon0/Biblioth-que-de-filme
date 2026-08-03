"""Fiche détaillée d'un titre : film ou série.

- Film : infos + dates de visionnage (multiples) + revisionnages.
- Série : saisons/épisodes (nom, image, résumé, durée), marquage Vu/Revu,
  « marquer la saison » et « marquer la série », prochain épisode.
"""
import time
from datetime import date

from flask import Blueprint, jsonify, request

import auth
import db
from context import get_tmdb
from services import sync
from tmdb import TMDBError

bp = Blueprint("titles", __name__, url_prefix="/api")


def _titre(titre_id):
    t = db.q1("SELECT * FROM titres WHERE id = ?", (titre_id,))
    if t:
        t["genres"] = db.jload(t.get("genres"), [])
        t["plateformes"] = db.jload(t.get("plateformes"), [])
        t["casting"] = db.jload(t.get("casting"), [])
        t["equipe"] = db.jload(t.get("equipe"), [])
        t["favori"] = bool(t["favori"])
    return t


def _saisons(titre_id):
    """Épisodes groupés par saison, avec compteur vus/total par saison."""
    eps = db.q(
        "SELECT * FROM episodes WHERE titre_id = ? ORDER BY saison, numero",
        (titre_id,),
    )
    saisons = {}
    for e in eps:
        e["vu"] = bool(e["vu"])
        s = saisons.setdefault(e["saison"], {"numero": e["saison"],
                                             "episodes": [], "vus": 0})
        s["episodes"].append(e)
        if e["vu"]:
            s["vus"] += 1
    for s in saisons.values():
        s["total"] = len(s["episodes"])
    return [saisons[k] for k in sorted(saisons)]


@bp.get("/preview")
@auth.login_required
def preview():
    """Aperçu d'un titre TMDB **sans l'ajouter** à la bibliothèque.

    Renvoie la fiche complète (résumé, plateformes, bande-annonce, casting,
    saisons pour les séries). L'ajout ne se fait que si l'utilisateur choisit
    un statut ensuite.
    """
    tmdb_id = request.args.get("tmdb_id")
    typ = request.args.get("type")
    if typ not in ("film", "serie") or not tmdb_id:
        return jsonify(error="Titre invalide."), 400
    tmdb = get_tmdb()
    try:
        detail = (tmdb.movie(int(tmdb_id)) if typ == "film"
                  else tmdb.tv(int(tmdb_id)))
    except (TMDBError, ValueError) as exc:
        return jsonify(error=str(exc)), 502
    return jsonify(detail)


@bp.get("/title/<int:titre_id>")
@auth.login_required
def detail(titre_id):
    t = _titre(titre_id)
    if not t:
        return jsonify(error="Titre introuvable."), 404
    # Complète casting/équipe pour les titres ajoutés avant cette fonctionnalité.
    if t["tmdb_id"] and not t.get("casting"):
        try:
            tmdb = get_tmdb()
            d = tmdb.movie(t["tmdb_id"]) if t["type"] == "film" else tmdb.tv(t["tmdb_id"])
            sync.upsert_titre(d, t["statut"])
            t = _titre(titre_id)
        except TMDBError:
            pass
    payload = {"titre": t}
    if t["type"] == "film":
        payload["visionnages"] = db.q(
            "SELECT id, date FROM visionnages WHERE titre_id = ? ORDER BY date DESC",
            (titre_id,),
        )
    else:
        # Complète les épisodes si la série vient d'être ajoutée sans détail.
        if t["tmdb_id"] and not db.q1(
                "SELECT 1 FROM episodes WHERE titre_id = ? LIMIT 1", (titre_id,)):
            try:
                tmdb = get_tmdb()
                detail_tv = tmdb.tv(t["tmdb_id"])
                sync.sync_episodes(titre_id, tmdb, t["tmdb_id"],
                                   detail_tv.get("saisons", []))
            except TMDBError:
                pass
        payload["saisons"] = _saisons(titre_id)
        payload["prochain_episode"] = _prochain_episode(titre_id)
    payload["alerte"] = db.q1(
        "SELECT canal FROM alertes WHERE titre_id = ?", (titre_id,))
    return jsonify(payload)


def _prochain_episode(titre_id):
    today = date.today().isoformat()
    return db.q1(
        """SELECT saison, numero, nom, date_diff FROM episodes
           WHERE titre_id = ? AND date_diff >= ? ORDER BY date_diff LIMIT 1""",
        (titre_id, today),
    )


# --- visionnages de films --------------------------------------------------
@bp.post("/title/<int:titre_id>/watch")
@auth.login_required
def add_watch(titre_id):
    """Enregistre un visionnage (« vu » / « revu ») à la date du jour par défaut."""
    data = request.get_json(silent=True) or {}
    raw = (data.get("date") or "").strip()
    jour = raw[:10] if raw else date.today().isoformat()
    db.run("INSERT INTO visionnages (titre_id, date, cree) VALUES (?,?,?)",
           (titre_id, jour, int(time.time())))
    db.run("UPDATE titres SET statut = 'vu' WHERE id = ?", (titre_id,))
    return jsonify(ok=True)


@bp.delete("/watch/<int:watch_id>")
@auth.login_required
def del_watch(watch_id):
    db.run("DELETE FROM visionnages WHERE id = ?", (watch_id,))
    return jsonify(ok=True)


# --- épisodes de séries ----------------------------------------------------
def _set_episode(ep_id, vu):
    if vu:
        db.run(
            """UPDATE episodes SET vu = 1, nb_vues = nb_vues + 1,
               derniere_vue = ? WHERE id = ?""",
            (date.today().isoformat(), ep_id),
        )
    else:
        db.run("UPDATE episodes SET vu = 0, nb_vues = 0, derniere_vue = NULL "
               "WHERE id = ?", (ep_id,))


@bp.post("/episode/<int:ep_id>/toggle")
@auth.login_required
def toggle_episode(ep_id):
    ep = db.q1("SELECT id, titre_id, vu FROM episodes WHERE id = ?", (ep_id,))
    if not ep:
        return jsonify(error="Épisode introuvable."), 404
    _set_episode(ep_id, not ep["vu"])
    _refresh_serie_statut(ep["titre_id"])
    return jsonify(ok=True)


@bp.post("/title/<int:titre_id>/season/<int:saison>/mark")
@auth.login_required
def mark_season(titre_id, saison):
    """Marque toute une saison vue (ou non vue selon ``vu``)."""
    vu = (request.get_json(silent=True) or {}).get("vu", True)
    for e in db.q("SELECT id FROM episodes WHERE titre_id = ? AND saison = ?",
                  (titre_id, saison)):
        _set_episode(e["id"], vu)
    _refresh_serie_statut(titre_id)
    return jsonify(ok=True)


@bp.post("/title/<int:titre_id>/mark")
@auth.login_required
def mark_series(titre_id):
    """Marque toute la série vue (ou non vue)."""
    vu = (request.get_json(silent=True) or {}).get("vu", True)
    for e in db.q("SELECT id FROM episodes WHERE titre_id = ?", (titre_id,)):
        _set_episode(e["id"], vu)
    _refresh_serie_statut(titre_id)
    return jsonify(ok=True)


def _refresh_serie_statut(titre_id):
    """Ajuste le statut de la série selon la progression des épisodes."""
    stats = db.q1(
        "SELECT COUNT(*) AS total, SUM(vu) AS vus FROM episodes WHERE titre_id = ?",
        (titre_id,),
    )
    total, vus = stats["total"] or 0, stats["vus"] or 0
    if total and vus >= total:
        statut = "vu"
    elif vus:
        statut = "en_cours"
    else:
        statut = "a_voir"
    db.run("UPDATE titres SET statut = ? WHERE id = ?", (statut, titre_id))
