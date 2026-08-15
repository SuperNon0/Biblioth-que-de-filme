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
from context import cfg, get_tmdb
from tmdb import TMDBError

bp = Blueprint("settings", __name__, url_prefix="/api")

UPDATE_SCRIPT = "/opt/cinetheque/scripts/update-panel.sh"

# Tables exportées/réimportées (ordre respectant les dépendances).
TABLES = ["titres", "visionnages", "episodes", "listes", "liste_items", "alertes"]


@bp.get("/settings")
@auth.login_required
def get_settings():
    return jsonify(settings_store.all_public())


@bp.post("/settings")
@auth.login_required
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
        else:
            values[key] = str(data[key]).strip()
    settings_store.update(values)
    return jsonify(ok=True, **settings_store.all_public())


@bp.post("/settings/notif-test")
@auth.login_required
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


@bp.post("/settings/password")
@auth.login_required
def change_password():
    password = str((request.get_json(silent=True) or {}).get("password", ""))
    try:
        auth.set_password(password)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(ok=True)


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
@auth.login_required
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
    fixes = {"films_vu_sans_visionnage": 0, "episodes_incoherents": 0}
    # 1. Films « vu » sans visionnage.
    orphelins = db.q(
        """SELECT id FROM titres WHERE type='film' AND statut='vu'
           AND id NOT IN (SELECT titre_id FROM visionnages)""")
    for f in orphelins:
        db.run("INSERT INTO visionnages (titre_id, date, cree) VALUES (?,?,?)",
               (f["id"], time.strftime("%Y-%m-%d"), int(time.time())))
    fixes["films_vu_sans_visionnage"] = len(orphelins)
    # 2. Épisodes incohérents (vu sans compteur, ou compteur sans vu).
    n = db.q1("SELECT COUNT(*) AS n FROM episodes "
              "WHERE (vu=0 AND nb_vues>0) OR (vu=1 AND nb_vues<1)")["n"]
    db.run("UPDATE episodes SET vu=1 WHERE vu=0 AND nb_vues>0")
    db.run("UPDATE episodes SET nb_vues=1 WHERE vu=1 AND nb_vues<1")
    fixes["episodes_incoherents"] = n
    return jsonify(ok=True, fixes=fixes)


@bp.post("/reset")
@auth.login_required
def reset_data():
    """Réinitialise toute la bibliothèque (titres, visionnages, épisodes, listes
    perso, alertes). Conserve les listes système « À voir » et « Favoris »."""
    conn = db.connect()
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        for table in ("liste_items", "alertes", "visionnages", "episodes", "titres"):
            conn.execute(f"DELETE FROM {table}")
        conn.execute("DELETE FROM listes WHERE systeme IS NULL")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.commit()
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        return jsonify(error=str(exc)), 500
    return jsonify(ok=True)


@bp.get("/export")
@auth.login_required
def export_data():
    """Exporte toute la base au format JSON (fichier de secours/migration)."""
    dump = {"version": 1, "exporte_le": int(time.time())}
    for table in TABLES:
        dump[table] = db.q(f"SELECT * FROM {table}")
    resp = jsonify(dump)
    resp.headers["Content-Disposition"] = (
        f"attachment; filename=cinetheque-export-"
        f"{time.strftime('%Y%m%d')}.json"
    )
    return resp


@bp.post("/import")
@auth.login_required
def import_data():
    """Réimporte un export : remplace intégralement le contenu de la base."""
    dump = request.get_json(silent=True) or {}
    if "titres" not in dump:
        return jsonify(error="Fichier d'export invalide."), 400
    conn = db.connect()
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        for table in reversed(TABLES):
            conn.execute(f"DELETE FROM {table}")
        for table in TABLES:
            for row in dump.get(table, []):
                cols = ", ".join(row.keys())
                marks = ", ".join("?" for _ in row)
                conn.execute(
                    f"INSERT INTO {table} ({cols}) VALUES ({marks})",
                    tuple(row.values()),
                )
        conn.execute("PRAGMA foreign_keys = ON")
        conn.commit()
    except Exception as exc:  # noqa: BLE001 - on renvoie l'erreur telle quelle
        conn.rollback()
        return jsonify(error=f"Import échoué : {exc}"), 500
    return jsonify(ok=True)
