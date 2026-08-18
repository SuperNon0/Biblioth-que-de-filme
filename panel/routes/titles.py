"""Fiche détaillée d'un titre : film ou série.

- Film : infos + dates de visionnage (multiples) + revisionnages.
- Série : saisons/épisodes (nom, image, résumé, durée), marquage Vu/Revu,
  « marquer la saison » et « marquer la série », prochain épisode.
"""
import threading
import time
from datetime import date

from flask import Blueprint, jsonify, request

import auth
import db
from context import get_tmdb
from services import sync
from tmdb import TMDBError

bp = Blueprint("titles", __name__, url_prefix="/api")


def _owns(titre_id):
    """Le titre appartient-il au compte effectif ? (cloisonnement des écritures)"""
    return bool(db.q1("SELECT 1 FROM titres WHERE id = ? AND compte_id = ?",
                      (titre_id, auth.compte_courant_id())))


def _titre(titre_id):
    t = db.q1("SELECT * FROM titres WHERE id = ? AND compte_id = ?",
              (titre_id, auth.compte_courant_id()))
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


@bp.get("/preview/season")
@auth.login_required
def preview_season():
    """Épisodes d'une saison d'une série **non ajoutée** (aperçu, lecture seule)."""
    tmdb_id = request.args.get("tmdb_id")
    saison = request.args.get("saison")
    if not tmdb_id or saison is None:
        return jsonify(episodes=[])
    try:
        eps = get_tmdb().season(int(tmdb_id), int(saison))
    except (TMDBError, ValueError):
        return jsonify(episodes=[])
    return jsonify(episodes=eps)


@bp.get("/title/<int:titre_id>")
@auth.login_required
def detail(titre_id):
    t = _titre(titre_id)
    if not t:
        return jsonify(error="Titre introuvable."), 404
    # Complète casting/équipe pour les titres ajoutés avant (mise à jour légère
    # des seules colonnes concernées : pas de ré-écriture ni de re-téléchargement
    # de l'affiche, pour un chargement rapide).
    if t["tmdb_id"] and not t.get("casting"):
        try:
            tmdb = get_tmdb()
            d = tmdb.movie(t["tmdb_id"]) if t["type"] == "film" else tmdb.tv(t["tmdb_id"])
            import json
            db.run("UPDATE titres SET casting=?, equipe=? WHERE id=?", (
                json.dumps(d.get("casting", []), ensure_ascii=False),
                json.dumps(d.get("equipe", []), ensure_ascii=False), titre_id))
            t["casting"] = d.get("casting", [])
            t["equipe"] = d.get("equipe", [])
        except TMDBError:
            pass
    payload = {"titre": t}
    if t["type"] == "film":
        payload["visionnages"] = db.q(
            "SELECT id, date FROM visionnages WHERE titre_id = ? ORDER BY date DESC",
            (titre_id,),
        )
    else:
        # Détecte une synchronisation incomplète (souvent « seule la saison 1 »
        # à cause d'un appel TMDB qui a échoué) : on compte les saisons présentes
        # et on compare au nombre attendu (nb_saisons). Si c'est incomplet — ou
        # inconnu pour une série ajoutée avant cette détection — on (re)synchronise
        # en arrière-plan et le front affiche « chargement » puis se rafraîchit.
        have = db.q1("SELECT COUNT(DISTINCT saison) AS n FROM episodes "
                     "WHERE titre_id = ?", (titre_id,))["n"] or 0
        expected = t.get("nb_saisons")
        incomplete = have == 0 or expected is None or (expected and have < expected)
        if t["tmdb_id"] and incomplete:
            if sync.is_syncing(titre_id):
                payload["sync_pending"] = True
            else:
                _resync_episodes_bg(get_tmdb(), titre_id, t["tmdb_id"])
                payload["sync_pending"] = True
        payload["saisons"] = _saisons(titre_id)
        payload["prochain_episode"] = _prochain_episode(titre_id)
        from services import statistics
        payload["temps"] = statistics.temps_serie(titre_id)
    payload["alerte"] = db.q1(
        "SELECT canal FROM alertes WHERE titre_id = ?", (titre_id,))
    return jsonify(payload)


def _resync_episodes_bg(tmdb, titre_id, tmdb_id):
    """(Re)synchronise en arrière-plan tous les épisodes d'une série et met à
    jour ``nb_saisons``. Non bloquant : la fiche s'ouvre tout de suite et le
    front rafraîchit les saisons au fur et à mesure (``sync_pending``)."""
    sync.mark_syncing(titre_id)

    def worker():
        try:
            detail_tv = tmdb.tv(tmdb_id)
            nb = detail_tv.get("nb_saisons")
            if nb:
                db.run("UPDATE titres SET nb_saisons=? WHERE id=?", (nb, titre_id))
            sync.sync_episodes(titre_id, tmdb, tmdb_id, detail_tv.get("saisons", []))
        except TMDBError:
            pass
        finally:
            sync.done_syncing(titre_id)

    threading.Thread(target=worker, daemon=True).start()


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
    if not _owns(titre_id):
        return jsonify(error="Titre introuvable."), 404
    data = request.get_json(silent=True) or {}
    raw = (data.get("date") or "").strip()
    jour = raw[:10] if raw else date.today().isoformat()
    db.run("INSERT INTO visionnages (titre_id, date, cree) VALUES (?,?,?)",
           (titre_id, jour, int(time.time())))
    db.run("UPDATE titres SET statut = 'vu' WHERE id = ?", (titre_id,))
    db.log_event(titre_id, "film")
    return jsonify(ok=True)


@bp.delete("/watch/<int:watch_id>")
@auth.login_required
def del_watch(watch_id):
    row = db.q1("SELECT titre_id FROM visionnages WHERE id = ?", (watch_id,))
    if not row or not _owns(row["titre_id"]):
        return jsonify(error="Visionnage introuvable."), 404
    db.run("DELETE FROM visionnages WHERE id = ?", (watch_id,))
    # S'il n'y a plus aucun visionnage, le film n'est plus « vu » (correction
    # d'un marquage par erreur) : on repasse le statut à « à voir ».
    if row and not db.q1(
            "SELECT 1 FROM visionnages WHERE titre_id = ? LIMIT 1", (row["titre_id"],)):
        db.run("UPDATE titres SET statut = 'a_voir' WHERE id = ? AND type = 'film'",
               (row["titre_id"],))
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


def _apply_ep(ep, action):
    """Applique une action à un épisode :
    - ``seen`` : le marque vu (×1) SANS incrémenter s'il l'était déjà ;
    - ``revu`` : le marque vu (×1), ou ajoute un visionnage s'il l'était déjà (×N+1) ;
    - ``remove`` : retire un visionnage (×N-1) ; à 0 l'épisode redevient non vu."""
    today = date.today().isoformat()
    if action == "remove":
        nb = (ep["nb_vues"] or 0) - 1
        if nb <= 0:
            db.run("UPDATE episodes SET vu = 0, nb_vues = 0, derniere_vue = NULL "
                   "WHERE id = ?", (ep["id"],))
        else:
            db.run("UPDATE episodes SET nb_vues = ? WHERE id = ?", (nb, ep["id"]))
    elif action == "seen":
        # Marquage simple : garantit ×1, sans gonfler le compteur si déjà vu.
        if not ep["vu"]:
            db.run("UPDATE episodes SET vu = 1, "
                   "nb_vues = CASE WHEN nb_vues < 1 THEN 1 ELSE nb_vues END, "
                   "derniere_vue = ? WHERE id = ?", (today, ep["id"]))
    else:  # revu (marque ou +1)
        nb = (ep["nb_vues"] or 0) + 1 if ep["vu"] else 1
        db.run("UPDATE episodes SET vu = 1, nb_vues = ?, derniere_vue = ? WHERE id = ?",
               (nb, today, ep["id"]))


@bp.post("/episode/<int:ep_id>/toggle")
@auth.login_required
def toggle_episode(ep_id):
    """Action sur un épisode : ``revu`` (marque / +1) ou ``remove`` (-1)."""
    ep = db.q1("SELECT id, titre_id, vu, nb_vues, nom, saison, numero "
               "FROM episodes WHERE id = ?", (ep_id,))
    if not ep or not _owns(ep["titre_id"]):
        return jsonify(error="Épisode introuvable."), 404
    action = (request.get_json(silent=True) or {}).get("action", "revu")
    _apply_ep(ep, action)
    _refresh_serie_statut(ep["titre_id"])
    if action in ("seen", "revu"):
        db.log_event(ep["titre_id"], "episode", _ep_label(ep))
    return jsonify(ok=True)


@bp.post("/title/<int:titre_id>/episode/<int:saison>/<int:numero>/toggle")
@auth.login_required
def toggle_episode_num(titre_id, saison, numero):
    """Comme ci-dessus mais repéré par (saison, numéro) — utile après un ajout
    depuis l'aperçu, où le front ne connaît pas encore l'id local de l'épisode."""
    if not _owns(titre_id):
        return jsonify(error="Épisode introuvable."), 404
    ep = db.q1(
        "SELECT id, vu, nb_vues, nom, saison, numero FROM episodes "
        "WHERE titre_id = ? AND saison = ? AND numero = ?",
        (titre_id, saison, numero),
    )
    if not ep:
        return jsonify(error="Épisode introuvable."), 404
    action = (request.get_json(silent=True) or {}).get("action", "revu")
    _apply_ep(ep, action)
    _refresh_serie_statut(titre_id)
    if action in ("seen", "revu"):
        db.log_event(titre_id, "episode", _ep_label(ep))
    return jsonify(ok=True)


def _ep_label(ep):
    """Libellé d'un épisode pour le journal : « S02E05 — Le sentier »."""
    code = f"S{ep['saison']:02d}E{ep['numero']:02d}"
    return code + (f" — {ep['nom']}" if ep.get("nom") else "")


def _mark_action(body):
    """Détermine l'action de marquage groupé (saison/série) à partir du corps.
    Rétrocompatible : ``vu:true`` → « seen » (marque sans gonfler), ``vu:false``
    → « unmark »."""
    body = body or {}
    if "action" in body:
        return body["action"]
    return "seen" if body.get("vu", True) else "unmark"


def _mark_episodes(episodes, action):
    for e in episodes:
        if action == "unmark":
            _set_episode(e["id"], False)
        else:
            _apply_ep(e, action)  # seen | revu | remove


@bp.post("/title/<int:titre_id>/season/<int:saison>/mark")
@auth.login_required
def mark_season(titre_id, saison):
    """Marque une saison entière : seen (×1), revu (+1), remove (-1) ou unmark."""
    if not _owns(titre_id):
        return jsonify(error="Titre introuvable."), 404
    action = _mark_action(request.get_json(silent=True))
    eps = db.q("SELECT id, vu, nb_vues FROM episodes WHERE titre_id = ? AND saison = ?",
               (titre_id, saison))
    _mark_episodes(eps, action)
    _refresh_serie_statut(titre_id)
    if action in ("seen", "revu"):
        db.log_event(titre_id, "saison", f"Saison {saison}")
    return jsonify(ok=True)


@bp.post("/title/<int:titre_id>/mark")
@auth.login_required
def mark_series(titre_id):
    """Marque la série entière : seen (×1), revu (+1), remove (-1) ou unmark."""
    if not _owns(titre_id):
        return jsonify(error="Titre introuvable."), 404
    action = _mark_action(request.get_json(silent=True))
    eps = db.q("SELECT id, vu, nb_vues FROM episodes WHERE titre_id = ?", (titre_id,))
    _mark_episodes(eps, action)
    _refresh_serie_statut(titre_id)
    if action in ("seen", "revu"):
        db.log_event(titre_id, "serie", "Série entière")
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
