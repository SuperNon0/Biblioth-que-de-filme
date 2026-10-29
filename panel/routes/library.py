"""Bibliothèque : recherche TMDB, ajout, listing filtré, statuts.

Le cœur de l'app : chercher un titre, l'ajouter, lister sa collection avec
tris/filtres, changer le statut ou le favori, supprimer.
"""
import json
import threading
import time
from datetime import date

from flask import Blueprint, jsonify, request

import auth
import db
import genres as genres_fr
import settings_store
from context import get_tmdb
from services import sync, undo
from tmdb import TMDBError, canon_platform

bp = Blueprint("library", __name__, url_prefix="/api")

STATUTS = {"vu", "a_voir", "en_cours"}
TRIS = {
    "ajout": "date_ajout DESC",
    "titre": "titre COLLATE NOCASE ASC",
    "annee": "annee DESC",
    "note": "note_tmdb DESC",
}


# Colonnes d'une CARTE (grilles bibliothèque/listes, MCP). La fiche complète
# (casting, équipe, résumé, plateformes…) se charge à l'ouverture via
# /api/title/<id> : renvoyer `SELECT *` faisait ~6 Ko par titre, soit ~3 Mo
# pour une bibliothèque de 500 titres à chaque affichage sur téléphone.
CARTE_COLS = ("id", "tmdb_id", "type", "titre", "annee", "affiche", "note_tmdb",
              "genres", "statut", "favori", "date_ajout", "nb_saisons", "date_sortie")


def carte_cols(alias=""):
    """Liste SQL des colonnes de carte (préfixées par l'alias de table)."""
    return ", ".join(f"{alias}{c}" for c in CARTE_COLS)


def _row(t):
    """Sérialise une ligne de titre pour le front (genres regroupés en français)."""
    t["genres"] = genres_fr.normaliser(db.jload(t.get("genres"), []))
    if "plateformes" in t:
        t["plateformes"] = db.jload(t.get("plateformes"), [])
    t["favori"] = bool(t.get("favori"))
    return t


# Modes d'accès « inclus » dans un abonnement (sans achat ni location).
MODES_INCLUS = {"Abonnement", "Gratuit", "Avec pubs", ""}


def mes_plateformes():
    """Noms canoniques (minuscules) des plateformes auxquelles on est abonné."""
    return {canon_platform(n).lower() for n in settings_store.get("mes_plateformes") or []}


def plateforme_incluse(plateformes, mes):
    """Première de MES plateformes où le titre est inclus : {nom, logo} ou None."""
    for p in plateformes or []:
        nom = canon_platform(p.get("nom"))
        if nom and nom.lower() in mes and p.get("mode", "") in MODES_INCLUS:
            return {"nom": nom, "logo": p.get("logo")}
    return None


def annotate_cards(rows):
    """Prépare des lignes de titres pour les cartes : genres décodés, « vu ×N »
    des films (nombre de visionnages), progression des séries, date du dernier
    visionnage (``vu_le``, rangée « Vus récemment ») et badge de la plateforme
    où le titre est inclus dans mes abonnements."""
    out = [_row(r) for r in rows]
    film_ids = [r["id"] for r in out if r["type"] == "film"]
    vues = {}
    if film_ids:
        marks = ",".join("?" * len(film_ids))
        for v in db.q(f"""SELECT titre_id, COUNT(*) AS n, MAX(cree) AS dernier
                          FROM visionnages WHERE titre_id IN ({marks})
                          GROUP BY titre_id""", film_ids):
            vues[v["titre_id"]] = v
    # Progression + prochain épisode des séries (barre + « où j'en suis »).
    annotate_series_progress(out)
    for row in out:
        if row["type"] == "film":
            v = vues.get(row["id"]) or {}
            row["nb_vues"] = v.get("n", 0)
            if v.get("dernier"):
                row["vu_le"] = time.strftime("%Y-%m-%d", time.localtime(v["dernier"]))
    mes = mes_plateformes()
    if mes and out:
        ids = [r["id"] for r in out]
        plats = {}
        for i in range(0, len(ids), 500):  # limite de variables SQLite
            lot = ids[i:i + 500]
            for p in db.q(f"SELECT id, plateformes FROM titres WHERE id IN "
                          f"({','.join('?' * len(lot))})", lot):
                plats[p["id"]] = p["plateformes"]
        for row in out:
            d = plateforme_incluse(db.jload(plats.get(row["id"]), []), mes)
            if d:
                row["dispo"] = d
    return out


def _mark_seen(titre_id, typ, lot=None):
    """Fait qu'un titre marqué « vu » compte dans les statistiques.

    - Film : ajoute un visionnage « déjà vu » (date NULL) s'il n'y en a aucun,
      donc sans forcer de date. Les re-visionnages s'ajoutent depuis la fiche.
    - Série : marque tous les épisodes comme vus (comptent dans le temps passé).

    ``lot`` (facultatif) retient de quoi annuler ces changements.
    """
    lot = lot or undo.Lot()
    if typ == "film":
        if not db.q1("SELECT 1 FROM visionnages WHERE titre_id = ? LIMIT 1", (titre_id,)):
            lot.ajoute("visionnages", db.run(
                "INSERT OR IGNORE INTO visionnages (titre_id, date, cree) VALUES (?,?,?)",
                (titre_id, time.strftime("%Y-%m-%d"), int(time.time()))))
            lot.ajoute("journal", db.log_event(titre_id, "film"))
    else:
        lot.episodes(titre_id)
        # Épisodes déjà diffusés seulement : une saison à venir cochée d'avance
        # ne reviendrait jamais dans « Reprendre » à sa sortie.
        db.run(f"""UPDATE episodes SET vu = 1,
                   nb_vues = CASE WHEN nb_vues < 1 THEN 1 ELSE nb_vues END
                   WHERE titre_id = ? AND {sync.ep_diffuse_sql()}""", (titre_id,))


def annotate_series_progress(rows):
    """Ajoute à des lignes de séries : progression (``total_ep``/``vus_ep``) et
    prochain épisode (``next_saison``/``next_numero``) — pour « où j'en suis ».

    Le « prochain épisode » gère aussi le **re-visionnage** : s'il ne reste aucun
    épisode non vu, on propose le premier épisode **moins revu que le maximum**
    (``revoit=True``), pour pouvoir enchaîner une série déjà vue."""
    ids = [r["id"] for r in rows if r.get("type") == "serie"]
    if not ids:
        return rows
    marks = ",".join("?" * len(ids))
    eps_by = {}
    for e in db.q(f"""SELECT titre_id, saison, numero, nom, duree, vu, nb_vues, date_diff,
                             derniere_vue
                      FROM episodes WHERE titre_id IN ({marks})
                      ORDER BY titre_id, saison, numero""", ids):
        eps_by.setdefault(e["titre_id"], []).append(e)
    today = date.today().isoformat()
    for r in rows:
        if r.get("type") != "serie":
            continue
        tous = eps_by.get(r["id"])
        if not tous:
            continue
        # Progression sur les épisodes DÉJÀ DIFFUSÉS : une saison annoncée ne
        # fait pas d'une série terminée une série « en cours ».
        eps = [e for e in sync.flag_diffuses(tous, today) if e["diffuse"]]
        if len(eps) < len(tous):
            r["a_venir"] = len(tous) - len(eps)
        if not eps:
            continue
        total = len(eps)
        vus = sum(1 for e in eps if e["vu"])
        vu_le = max((e["derniere_vue"] or "" for e in eps if e["vu"]), default="")
        if vu_le:
            r["vu_le"] = vu_le
        maxi = max((e["nb_vues"] or 0) for e in eps)
        mini = min((e["nb_vues"] or 0) for e in eps)
        r["total_ep"] = total
        r["vus_ep"] = vus
        # Prochain épisode : d'abord un non-vu (1er visionnage) ; sinon, le
        # premier moins revu que le max (re-visionnage en cours).
        nxt = next((e for e in eps if not e["vu"]), None)
        if nxt is None and maxi > 0:
            nxt = next((e for e in eps if (e["nb_vues"] or 0) < maxi), None)
            if nxt is not None:
                r["revoit"] = True
        if nxt is not None:
            r["next_saison"] = nxt["saison"]
            r["next_numero"] = nxt["numero"]
            r["next_nom"] = nxt["nom"]
            r["next_duree"] = nxt["duree"]
        # Prochaine diffusion annoncée (saison à venir) : date du 1er épisode.
        futur = next((e for e in tous if e.get("date_diff") and e["date_diff"] > today), None)
        if futur is not None:
            r["prochaine_diffusion"] = {"saison": futur["saison"], "numero": futur["numero"],
                                        "date": futur["date_diff"]}
        # Série entièrement vue N fois (min des revisionnages) → « ↻ ×N ».
        if total and vus >= total:
            r["nb_vues"] = mini
    return rows


def annotate_library(items):
    """Ajoute le statut local + l'id aux résultats TMDB déjà en bibliothèque.

    Permet au front d'afficher le badge de statut sur les cartes et le menu
    rapide (« déjà dans ta bibliothèque : … »).
    """
    if not items:
        return items
    lib = {(r["tmdb_id"], r["type"]): r for r in db.q(
        """SELECT id, tmdb_id, type, statut, date_ajout,
                  (SELECT COUNT(*) FROM visionnages v WHERE v.titre_id = t.id) AS nb_vues
           FROM titres t WHERE tmdb_id IS NOT NULL AND compte_id = ?""",
        (auth.compte_courant_id(),))}
    for it in items:
        row = lib.get((it.get("tmdb_id"), it.get("type")))
        if row:
            it["statut"] = row["statut"]
            it["local_id"] = row["id"]
            it["nb_vues"] = row["nb_vues"]
            it["date_ajout"] = row["date_ajout"]
    # Progression des séries (X/Y, prochain épisode, re-visionnage) sur TOUS les
    # écrans qui affichent des résultats TMDB (suggestions, découverte, similaires,
    # sagas, page acteur…), pour que le menu rapide montre « En cours » et
    # « Épisode suivant » partout. annotate_series_progress attend la clé « id ».
    in_lib = [it for it in items if it.get("local_id")]
    for it in in_lib:
        it["id"] = it["local_id"]
    annotate_series_progress(in_lib)
    for it in in_lib:
        it.pop("id", None)
    return items


@bp.get("/search")
@auth.login_required
def search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify(results=[])
    try:
        # annotate_library annote aussi la progression des séries (X/Y, prochain
        # épisode) → le menu rapide « épisode suivant » marche depuis la recherche.
        items = annotate_library(get_tmdb().search(query))
    except TMDBError as exc:
        return jsonify(error=str(exc)), 502
    return jsonify(results=items)


@bp.get("/library")
@auth.login_required
def library():
    """Liste la bibliothèque avec filtres (statut, type, genre) et tri."""
    where, params = ["compte_id = ?"], [auth.compte_courant_id()]
    statut = request.args.get("statut")
    if statut in STATUTS:
        where.append("statut = ?")
        params.append(statut)
    typ = request.args.get("type")
    if typ in ("film", "serie"):
        where.append("type = ?")
        params.append(typ)
    genre = request.args.get("genre")
    if genre:
        # « Action » retrouve aussi les séries classées « Action & Adventure ».
        noms = genres_fr.variantes(genre)
        where.append("(" + " OR ".join("genres LIKE ?" for _ in noms) + ")")
        params.extend(f'%"{g}"%' for g in noms)
    if request.args.get("favori") == "1":
        where.append("favori = 1")
    recherche = request.args.get("q", "").strip()
    if recherche:
        where.append("titre LIKE ?")
        params.append(f"%{recherche}%")
    order = TRIS.get(request.args.get("tri", "ajout"), TRIS["ajout"])
    rows = db.q(
        f"SELECT {carte_cols()} FROM titres WHERE {' AND '.join(where)} ORDER BY {order}",
        params,
    )
    return jsonify(titres=annotate_cards(rows))


@bp.get("/library/genres")
@auth.login_required
def library_genres():
    """Genres présents dans la bibliothèque (regroupés, en français), avec le
    nombre de titres de chacun : sert au filtre « Genre » de la bibliothèque."""
    compte = {}
    for r in db.q("SELECT genres FROM titres WHERE compte_id = ?", (auth.compte_courant_id(),)):
        for g in genres_fr.normaliser(db.jload(r["genres"], [])):
            compte[g] = compte.get(g, 0) + 1
    out = [{"nom": g, "n": n} for g, n in compte.items()]
    out.sort(key=lambda x: (-x["n"], x["nom"]))
    return jsonify(genres=out)


@bp.post("/library")
@auth.login_required
def add():
    """Ajoute un titre depuis TMDB (par tmdb_id + type) à la bibliothèque."""
    data = request.get_json(silent=True) or {}
    tmdb_id, typ = data.get("tmdb_id"), data.get("type")
    statut = data.get("statut", "a_voir")
    if typ not in ("film", "serie") or not tmdb_id:
        return jsonify(error="Titre invalide."), 400
    if statut not in STATUTS:
        return jsonify(error="Statut invalide (a_voir, en_cours ou vu)."), 400
    tmdb = get_tmdb()
    try:
        detail = tmdb.movie(tmdb_id) if typ == "film" else tmdb.tv(tmdb_id)
    except TMDBError as exc:
        return jsonify(error=str(exc)), 502
    cid = auth.compte_courant_id()
    lot = undo.Lot()
    existant = db.q1("SELECT id FROM titres WHERE compte_id = ? AND tmdb_id = ? AND type = ?",
                     (cid, tmdb_id, typ))
    if existant:
        lot.colonnes("titres", existant["id"], ["statut"])
    titre_id = sync.upsert_titre(detail, statut, cid)
    if not existant:
        lot.ajoute("titres", titre_id)  # « Annuler » retire le titre ajouté
    # Applique le statut choisi même si le titre existait déjà (upsert ne le
    # change pas à la mise à jour) — utile depuis le menu rapide. Sans statut
    # explicite, un titre déjà présent garde le sien : « ajoute Inception »
    # ne doit pas remettre « à voir » un film déjà vu.
    if "statut" in data:
        db.run("UPDATE titres SET statut = ? WHERE id = ?", (statut, titre_id))
    if typ == "serie":
        # Les épisodes (un appel TMDB par saison) se remplissent en arrière-plan
        # pour que l'ajout réponde instantanément, même pour les longues séries.
        _sync_episodes_bg(tmdb, titre_id, tmdb_id, detail.get("saisons", []), statut)
    elif statut == "vu":
        _mark_seen(titre_id, typ, lot if existant else None)
    return jsonify(ok=True, id=titre_id, annuler=undo.enregistrer(lot, cid))


def _sync_episodes_bg(tmdb, titre_id, tmdb_id, saisons, statut):
    """Remplit les épisodes d'une série dans un thread détaché (non bloquant).

    Le client TMDB et ``db`` ne dépendent pas du contexte de requête : on peut
    donc travailler hors requête. La fiche affiche « chargement… » tant que
    ``sync.is_syncing`` est vrai.
    """
    from datetime import date

    sync.mark_syncing(titre_id)

    def worker():
        try:
            sync.sync_episodes(titre_id, tmdb, tmdb_id, saisons)
            # Baseline anti-spam : les épisodes déjà diffusés ne déclenchent pas
            # de notification « nouvel épisode ». Seuls les futurs le feront.
            db.run("UPDATE episodes SET notifie=1 WHERE titre_id=? AND "
                   "date_diff IS NOT NULL AND date_diff <= ?",
                   (titre_id, date.today().isoformat()))
            if statut == "vu":
                _mark_seen(titre_id, "serie")
                db.run("UPDATE titres SET statut='vu' WHERE id=?", (titre_id,))
        except TMDBError:
            pass  # les épisodes se compléteront à l'ouverture de la fiche
        finally:
            sync.done_syncing(titre_id)

    threading.Thread(target=worker, daemon=True).start()


@bp.post("/library/manual")
@auth.login_required
def add_manual():
    """Ajout manuel d'un titre absent de TMDB."""
    data = request.get_json(silent=True) or {}
    titre = (data.get("titre") or "").strip()
    typ = data.get("type")
    if not titre or typ not in ("film", "serie"):
        return jsonify(error="Titre et type requis."), 400
    statut = data.get("statut") if data.get("statut") in STATUTS else "a_voir"
    try:
        annee = int(data["annee"]) if data.get("annee") not in (None, "") else None
        duree = int(data["duree"]) if data.get("duree") not in (None, "") else None
    except (TypeError, ValueError):
        return jsonify(error="Année et durée doivent être des nombres."), 400
    now = int(time.time())
    titre_id = db.run(
        """INSERT INTO titres (compte_id, type, titre, annee, resume, duree, statut,
                               ajout_manuel, date_ajout, maj)
           VALUES (?,?,?,?,?,?,?,1,?,?)""",
        (auth.compte_courant_id(), typ, titre, annee, data.get("resume"),
         duree, statut, now, now),
    )
    if typ == "film" and statut == "vu":
        # Sans visionnage, un film « vu » ne compte pas dans les statistiques.
        db.run("INSERT INTO visionnages (titre_id, date, cree) VALUES (?,?,?)",
               (titre_id, None, now))
    return jsonify(ok=True, id=titre_id)


@bp.patch("/library/<int:titre_id>")
@auth.login_required
def update(titre_id):
    """Change le statut ou le favori d'un titre."""
    data = request.get_json(silent=True) or {}
    cid = auth.compte_courant_id()
    row = db.q1("SELECT id, type FROM titres WHERE id = ? AND compte_id = ?", (titre_id, cid))
    if not row:
        return jsonify(error="Titre introuvable."), 404
    if "statut" in data and data["statut"] not in STATUTS:
        return jsonify(error="Statut invalide (a_voir, en_cours ou vu)."), 400
    lot = undo.Lot()
    lot.colonnes("titres", titre_id, ["statut", "favori"])
    if "statut" in data:
        db.run("UPDATE titres SET statut = ? WHERE id = ? AND compte_id = ?",
               (data["statut"], titre_id, cid))
        if data["statut"] == "vu":
            _mark_seen(titre_id, row["type"], lot)
    if "favori" in data:
        db.run("UPDATE titres SET favori = ? WHERE id = ? AND compte_id = ?",
               (1 if data["favori"] else 0, titre_id, cid))
        if not data["favori"]:
            # Ancien ajout manuel dans « Favoris » : le titre y restait affiché
            # alors que le cœur était décoché.
            lot.supprime("liste_items", db.q(
                "SELECT * FROM liste_items WHERE titre_id = ? AND liste_id IN "
                "(SELECT id FROM listes WHERE compte_id = ? AND systeme = 'favoris')",
                (titre_id, cid)))
            db.run("DELETE FROM liste_items WHERE titre_id = ? AND liste_id IN "
                   "(SELECT id FROM listes WHERE compte_id = ? AND systeme = 'favoris')",
                   (titre_id, cid))
    return jsonify(ok=True, annuler=undo.enregistrer(lot, cid))


@bp.delete("/library/<int:titre_id>")
@auth.login_required
def delete(titre_id):
    row = db.q1("SELECT titre FROM titres WHERE id = ? AND compte_id = ?",
                (titre_id, auth.compte_courant_id()))
    if not row:
        return jsonify(error="Titre introuvable."), 404
    lot = undo.Lot()
    lot.titre_complet(titre_id)
    db.run("DELETE FROM titres WHERE id = ? AND compte_id = ?",
           (titre_id, auth.compte_courant_id()))
    db.audit("supprimer_titre", acteur=auth.acteur(), cible=row["titre"])
    return jsonify(ok=True, annuler=undo.enregistrer(lot, auth.compte_courant_id()))


@bp.post("/undo")
@auth.login_required
def annuler():
    """Annule la dernière action désignée par son jeton (« Annuler », 5 s)."""
    jeton = str((request.get_json(silent=True) or {}).get("jeton") or "")
    if not jeton or not undo.annuler(jeton, auth.compte_courant_id()):
        return jsonify(error="Trop tard pour annuler cette action."), 410
    return jsonify(ok=True)


@bp.get("/to-add")
@auth.login_required
def to_add():
    """Suggestions de films connus/classiques à ajouter (remplir vite).

    Renvoie des populaires/mieux notés en excluant ce qui est déjà en base.
    """
    from routes.discover import POOL  # import local : discover importe ce module
    tmdb = get_tmdb()
    top, pop = POOL.submit(tmdb.top_rated, "movie"), POOL.submit(tmdb.popular, "movie")
    try:
        pool = top.result() + pop.result()
    except TMDBError as exc:
        return jsonify(error=str(exc)), 502
    connus = {r["tmdb_id"] for r in
              db.q("SELECT tmdb_id FROM titres WHERE tmdb_id IS NOT NULL AND type = 'film' "
                   "AND compte_id = ?", (auth.compte_courant_id(),))}
    seen, out = set(), []
    for r in pool:
        if r["tmdb_id"] in connus or r["tmdb_id"] in seen:
            continue
        seen.add(r["tmdb_id"])
        out.append(r)
    return jsonify(results=out[:30])
