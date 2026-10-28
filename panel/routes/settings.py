"""Paramètres : mot de passe, clé API TMDB, sauvegarde/export, import.

- Mot de passe admin modifiable (compte unique, conforme au CDC).
- Clé API TMDB + région, stockées dans le magasin de réglages inscriptible.
- Export complet des données (fichier JSON de secours) et réimport.
"""
import os
import subprocess
import time

from flask import Blueprint, jsonify, request

import auth
import db
import settings_store
from permissions import require_capability
from context import cfg, get_tmdb
from tmdb import TMDBError

bp = Blueprint("settings", __name__, url_prefix="/api")

UPDATE_SCRIPT = "/opt/cinetheque/scripts/update-panel.sh"

@bp.get("/settings")
@auth.login_required
def get_settings():
    return jsonify(settings_store.all_public())


@bp.post("/settings")
@auth.super_admin_required
def set_settings():
    data = request.get_json(silent=True) or {}
    values = {}
    for key, default in settings_store.EDITABLES.items():
        if key not in data:
            continue
        if key == "tmdb_api_key":
            # ne jamais écraser la clé TMDB par une valeur vide
            if str(data[key]).strip():
                values[key] = str(data[key]).strip()
        elif isinstance(default, bool):
            values[key] = bool(data[key])
        elif isinstance(default, list):
            # Liste de chaînes (ex. « mes plateformes ») : on nettoie et dédoublonne.
            raw = data[key] if isinstance(data[key], list) else []
            seen, clean = set(), []
            for x in raw:
                s = str(x).strip()
                if s and s not in seen:
                    seen.add(s)
                    clean.append(s)
            values[key] = clean
        else:
            values[key] = str(data[key]).strip()
    settings_store.update(values)
    return jsonify(ok=True, **settings_store.all_public())


@bp.post("/settings/notif-test")
@auth.super_admin_required
def notif_test():
    """Envoie une notification de test sur Discord (si activé)."""
    from services import notifications
    canaux = notifications.test()
    if not canaux:
        return jsonify(error="Aucun canal activé/configuré, ou envoi échoué."), 400
    return jsonify(ok=True, canaux=canaux)


@bp.post("/settings/tmdb-test")
@auth.login_required
def test_tmdb():
    """Vérifie que la clé TMDB fonctionne (petite recherche témoin)."""
    try:
        get_tmdb().trending("all", "week")
        return jsonify(ok=True)
    except TMDBError as exc:
        return jsonify(error=str(exc)), 502


def _git(src, *args):
    """Commande git tolérante à la propriété du dépôt (site non-root, dépôt root)."""
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={src}", "-C", src, *args],
        text=True, timeout=5, stderr=subprocess.DEVNULL).strip()


@bp.get("/version")
@auth.login_required
def version():
    """Version déployée.

    Priorité au fichier ``VERSION`` à la racine du dépôt (numéro lisible, ex.
    « 26.1 »). Repli sur le commit court si le fichier est absent. Le message du
    dernier commit est joint quand il est disponible (contexte utile).
    """
    src = cfg().get("source_dir", "/opt/cinetheque-src")
    numero = None
    try:
        with open(os.path.join(src, "VERSION"), encoding="utf-8") as handle:
            numero = handle.read().strip() or None
    except OSError:
        pass
    try:
        message = _git(src, "log", "-1", "--pretty=%s")
        return jsonify(version=numero or _git(src, "rev-parse", "--short", "HEAD"),
                       message=message)
    except (subprocess.SubprocessError, OSError):
        return jsonify(version=numero, message=None)


@bp.post("/update")
@require_capability("site_update")
def update():
    """Lance la mise à jour depuis GitHub (script auto-remplaçant + redémarrage).

    Le script fait `git pull` sur la branche déployée (main), recopie les
    fichiers, puis redémarre le service de façon détachée.
    """
    if not os.path.exists(UPDATE_SCRIPT):
        return jsonify(error="Script de mise à jour introuvable (déploiement requis)."), 400
    try:
        proc = subprocess.run(["sudo", "-n", UPDATE_SCRIPT],
                              capture_output=True, text=True, timeout=120)
    except subprocess.SubprocessError as exc:
        return jsonify(error=f"Échec du lancement : {exc}"), 500
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "échec inconnu").strip()
        return jsonify(error=detail[-400:]), 500
    return jsonify(ok=True,
                   message="Mise à jour lancée. Le site redémarre dans quelques secondes.")


@bp.post("/repair")
@auth.login_required
def repair_data():
    """Vérifie et répare les incohérences de la base (sans rien supprimer) :

    - Film marqué « vu » mais sans aucun visionnage → ajoute un visionnage
      (sinon il ne compte pas dans les statistiques et paraît « non sauvegardé »).
    - Épisode marqué vu sans compteur (ou l'inverse) → remet le compteur cohérent.
    Renvoie le détail de ce qui a été corrigé.
    """
    cid = auth.compte_courant_id()
    fixes = {"films_vu_sans_visionnage": 0, "episodes_incoherents": 0}
    # 1. Films « vu » sans visionnage (de ce compte uniquement).
    orphelins = db.q(
        """SELECT id FROM titres WHERE type='film' AND statut='vu' AND compte_id = ?
           AND id NOT IN (SELECT titre_id FROM visionnages)""", (cid,))
    for f in orphelins:
        db.run("INSERT INTO visionnages (titre_id, date, cree) VALUES (?,?,?)",
               (f["id"], time.strftime("%Y-%m-%d"), int(time.time())))
    fixes["films_vu_sans_visionnage"] = len(orphelins)
    # 2. Épisodes incohérents (vu sans compteur, ou compteur sans vu), de ce compte.
    scope = ("titre_id IN (SELECT id FROM titres WHERE compte_id = ?)")
    n = db.q1(f"SELECT COUNT(*) AS n FROM episodes "
              f"WHERE ((vu=0 AND nb_vues>0) OR (vu=1 AND nb_vues<1)) AND {scope}",
              (cid,))["n"]
    db.run(f"UPDATE episodes SET vu=1 WHERE vu=0 AND nb_vues>0 AND {scope}", (cid,))
    db.run(f"UPDATE episodes SET nb_vues=1 WHERE vu=1 AND nb_vues<1 AND {scope}", (cid,))
    fixes["episodes_incoherents"] = n
    return jsonify(ok=True, fixes=fixes)


@bp.post("/reset")
@auth.login_required
def reset_data():
    """Réinitialise la bibliothèque DE CE COMPTE (titres → cascade visionnages,
    épisodes, alertes, liste_items ; + listes perso). Conserve les listes
    système « À voir » et « Favoris »."""
    cid = auth.compte_courant_id()
    conn = db.connect()
    try:
        # Supprimer les titres du compte suffit : les enfants sont en CASCADE.
        conn.execute("DELETE FROM titres WHERE compte_id = ?", (cid,))
        conn.execute("DELETE FROM listes WHERE compte_id = ? AND systeme IS NULL", (cid,))
        conn.commit()
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        return jsonify(error=str(exc)), 500
    return jsonify(ok=True)


# Tables enfants rattachées à un titre (cloisonnement hérité via `titre_id`).
_TABLES_TITRE = ["visionnages", "episodes", "alertes", "journal"]


def _colonnes(conn, table):
    """Colonnes réelles d'une table (liste blanche pour l'import)."""
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]


@bp.get("/export")
@auth.super_admin_required
def export_data():
    """Exporte la bibliothèque DU COMPTE COURANT en JSON (secours/migration)."""
    cid = auth.compte_courant_id()
    dump = {"version": 2, "exporte_le": int(time.time())}
    dump["titres"] = db.q("SELECT * FROM titres WHERE compte_id = ?", (cid,))
    dump["listes"] = db.q("SELECT * FROM listes WHERE compte_id = ?", (cid,))
    for table in _TABLES_TITRE:
        dump[table] = db.q(
            f"SELECT x.* FROM {table} x JOIN titres t ON t.id = x.titre_id "
            "WHERE t.compte_id = ?", (cid,))
    dump["liste_items"] = db.q(
        "SELECT li.* FROM liste_items li JOIN listes l ON l.id = li.liste_id "
        "WHERE l.compte_id = ?", (cid,))
    resp = jsonify(dump)
    resp.headers["Content-Disposition"] = (
        f"attachment; filename=cinetheque-export-"
        f"{time.strftime('%Y%m%d')}.json"
    )
    return resp


@bp.post("/import")
@auth.super_admin_required
def import_data():
    """Réimporte un export dans le compte courant : remplace SA bibliothèque.

    Les autres comptes ne sont pas touchés. Les identifiants sont renumérotés
    (titres/listes) pour ne pas entrer en collision avec ceux des autres comptes.
    """
    dump = request.get_json(silent=True) or {}
    if not isinstance(dump.get("titres"), list):
        return jsonify(error="Fichier d'export invalide."), 400
    cid = auth.compte_courant_id()
    conn = db.connect()

    def _insert(table, row, cols_ok, **force):
        data = {k: v for k, v in row.items() if k in cols_ok and k != "id"}
        data.update(force)
        cols = ", ".join(data)
        marks = ", ".join("?" for _ in data)
        cur = conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})",
                           tuple(data.values()))
        return cur.lastrowid

    try:
        # Les enfants partent en CASCADE avec les titres/listes du compte.
        conn.execute("DELETE FROM titres WHERE compte_id = ?", (cid,))
        conn.execute("DELETE FROM listes WHERE compte_id = ?", (cid,))
        map_titres, map_listes = {}, {}
        cols = _colonnes(conn, "titres")
        for row in dump["titres"]:
            map_titres[row.get("id")] = _insert("titres", row, cols, compte_id=cid)
        cols = _colonnes(conn, "listes")
        for row in dump.get("listes") or []:
            map_listes[row.get("id")] = _insert("listes", row, cols, compte_id=cid)
        for table in _TABLES_TITRE:
            cols = _colonnes(conn, table)
            for row in dump.get(table) or []:
                if row.get("titre_id") in map_titres:
                    _insert(table, row, cols, titre_id=map_titres[row["titre_id"]])
        cols = _colonnes(conn, "liste_items")
        for row in dump.get("liste_items") or []:
            if row.get("titre_id") in map_titres and row.get("liste_id") in map_listes:
                _insert("liste_items", row, cols,
                        titre_id=map_titres[row["titre_id"]],
                        liste_id=map_listes[row["liste_id"]])
        conn.commit()
    except Exception as exc:  # noqa: BLE001 - on renvoie l'erreur telle quelle
        conn.rollback()
        return jsonify(error=f"Import échoué : {exc}"), 500
    db.ensure_system_lists(cid)
    return jsonify(ok=True)
