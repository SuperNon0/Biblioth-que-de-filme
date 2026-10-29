"""Catalogue des outils du serveur MCP de cinéthèque.

Principe : chaque outil est une **fine surcouche des routes /api/* du site**.
L'appel est rejoué *dans le processus* (client de test Flask, aucun aller-retour
réseau) avec la session du super-admin de base. Conséquences :

- Claude voit et fait exactement ce que fait l'interface (mêmes règles, même
  cloisonnement par compte, mêmes erreurs) → idéal pour tester le vrai site ;
- aucune logique métier dupliquée ici : une correction dans une route profite
  aussitôt au MCP.

Pour ajouter un outil : écrire une fonction ``handler(args) -> dict`` puis
l'inscrire dans ``TOOLS`` avec sa description et son schéma JSON.
"""
import json
import posixpath
import re
import time
from concurrent.futures import ThreadPoolExecutor, wait
from urllib.parse import unquote

from flask import current_app

import auth
import db

DEMARRAGE = int(time.time())

# Taille des réponses : on allège ce qui part vers Claude (moins de jetons,
# réponses plus rapides). Les détails restent accessibles via les paramètres.
LIMITE_DEFAUT = 50
CASTING_MAX = 8
CHAMPS_TITRE = ("id", "tmdb_id", "type", "titre", "annee", "statut", "favori",
                "genres", "nb_saisons", "nb_vues", "date_ajout")

# Outil générique appel_api : la garde porte sur la route RÉELLEMENT visée
# (endpoint Flask, après décodage du chemin) et non sur le texte du chemin —
# « /api/%72eset » atteignait /api/reset sans confirmation.
# Écritures qui exigent confirm="OUI" (en plus de tout DELETE) :
_ENDPOINTS_SENSIBLES = {
    "settings.reset_data", "settings.import_data", "settings.update",
    "settings.set_settings", "settings.repair_data", "settings.notif_test",
}
_BLUEPRINTS_SENSIBLES = {"accounts"}  # comptes, rôles, impersonation, mot de passe, Cloudflare
# Jamais depuis le MCP : régénérer/révoquer sa propre clé couperait le connecteur.
_ENDPOINTS_INTERDITS = {"mcp.generer_cle", "mcp.revoquer_cle"}
_METHODES = ("GET", "POST", "PATCH", "DELETE")
# Réponse brute d'appel_api plafonnée (GET /api/library brut : ~1 Mo).
REPONSE_MAX = 50_000
# Chemin accepté APRÈS décodage : pas de %, ?, #, espace… (paramètres d'URL
# uniquement via « requete ») — sinon le client de test redécoupe le chemin.
_CHEMIN_OK = re.compile(r"/api/[A-Za-z0-9_\-./]*")


class OutilErreur(Exception):
    """Erreur renvoyée proprement à Claude (isError=true), sans trace Python."""


# ── Appel interne d'une route du site ────────────────────────────────────────
def _compte_mcp():
    """Compte au nom duquel agit le MCP : le super-admin de base (Noë)."""
    row = auth.base_admin_row() or db.q1(
        "SELECT * FROM comptes WHERE role='super_admin' ORDER BY id LIMIT 1")
    if not row:
        raise OutilErreur("Aucun compte super-admin : le site n'est pas initialisé.")
    return row


def api(method, path, query=None, body=None, app=None):
    """Rejoue ``METHOD path`` sur l'app, connecté en super-admin. → (statut, json).

    Un contexte d'application neuf isole ``g`` (cache du compte courant) de la
    requête /mcp englobante. ``app`` : à passer depuis un autre thread.
    """
    app = app or current_app._get_current_object()
    with app.app_context():
        compte = _compte_mcp()
        client = app.test_client()
        with client.session_transaction() as sess:
            sess["compte_id"], sess["role"] = compte["id"], compte["role"]
            sess["via_mcp"] = True  # journal d'audit : l'auteur est « mcp »
        # X-Cinetheque : l'appel vient du site lui-même (garde anti-CSRF).
        resp = client.open(path, method=method, query_string=query or None,
                           json=body, headers={"X-Cinetheque": "1"})
        with resp:  # referme aussi les fichiers servis (app.js, style.css…)
            if 300 <= resp.status_code < 400:
                return resp.status_code, {"redirection": resp.headers.get("Location")}
            data = resp.get_json(silent=True)
            if data is None:
                data = {"contenu": resp.get_data(as_text=True)[:500]}
            return resp.status_code, data


def _ok(method, path, query=None, body=None):
    """Comme ``api`` mais lève OutilErreur si la route répond une erreur."""
    status, data = api(method, path, query, body)
    if status >= 400:
        msg = data.get("error") if isinstance(data, dict) else None
        raise OutilErreur(f"{method} {path} → {status} : {msg or data}")
    return data


def _confirme(args):
    return str(args.get("confirm", "")).strip().upper() == "OUI"


def _alleger(titre):
    """Fiche courte d'un titre pour Claude (note, progression, épisode suivant)."""
    out = {k: titre[k] for k in CHAMPS_TITRE if k in titre}
    if titre.get("note_tmdb") is not None:
        out["note"] = titre["note_tmdb"]
    if titre.get("total_ep"):
        out["progression"] = f"{titre.get('vus_ep') or 0}/{titre['total_ep']}"
    if titre.get("next_saison"):
        out["prochain_episode"] = f"S{titre['next_saison']:02d}E{titre['next_numero']:02d}"
    return out


def _sans_vide(d):
    """Retire les paramètres absents (None / "") avant de les passer à l'API."""
    return {k: v for k, v in d.items() if v not in (None, "")}


# ── Outils : état & diagnostic ───────────────────────────────────────────────
def etat_du_site(_args):
    version = _ok("GET", "/api/version")
    reglages = _ok("GET", "/api/settings")
    compte = _compte_mcp()
    n = db.q1("SELECT COUNT(*) AS n, SUM(type='film') AS films, SUM(type='serie') AS series "
              "FROM titres WHERE compte_id = ?", (compte["id"],))
    return {
        "version": version.get("version"),
        "dernier_changement": version.get("message"),
        "demarre_le": time.strftime("%d/%m/%Y %H:%M:%S", time.localtime(DEMARRAGE)),
        "en_ligne_depuis_s": int(time.time()) - DEMARRAGE,
        "compte": compte["email"] or f"#{compte['id']}",
        "tmdb_configuree": reglages.get("tmdb_configuree"),
        "bibliotheque": {"titres": n["n"], "films": n["films"] or 0,
                         "series": n["series"] or 0},
    }


# Parcours de contrôle : routes en lecture seule, comme les ouvre l'interface,
# (méthode, chemin, paramètres, dépend de TMDB). Les routes TMDB ne sont
# testées que si TMDB répond : sinon elles sont « non testées », pas en échec.
_PARCOURS = [
    ("GET", "/", None, False), ("GET", "/sw.js", None, False),
    ("GET", "/static/app.js", None, False), ("GET", "/static/style.css", None, False),
    ("GET", "/api/version", None, False), ("GET", "/api/settings", None, False),
    ("GET", "/api/library", None, False), ("GET", "/api/library", {"type": "serie"}, False),
    ("GET", "/api/lists", None, False), ("GET", "/api/lists/presets", None, False),
    ("GET", "/api/stats", None, False), ("GET", "/api/journal", None, False),
    ("GET", "/api/roulette", None, False), ("GET", "/api/comptes", None, False),
    ("GET", "/api/cloudflare", None, False), ("GET", "/api/mcp", None, False),
    ("GET", "/api/to-add", None, True), ("GET", "/api/genres", None, True),
    ("GET", "/api/suggestions", None, True), ("GET", "/api/upcoming", None, True),
    ("GET", "/api/discover", None, True), ("GET", "/api/providers/all", None, True),
    ("GET", "/api/search", {"q": "Inception"}, True),
]
# Durée maximale du parcours complet : au-delà, le client MCP coupe sans
# diagnostic (avec un TMDB lent, le parcours séquentiel prenait ~3 min).
BUDGET_VERIF = 20


def _sonde(app, method, path, query):
    t0 = time.perf_counter()
    try:
        status, data = api(method, path, query, app=app)
        erreur = data.get("error") if isinstance(data, dict) else None
        if 300 <= status < 400:
            erreur = f"redirection vers {data.get('redirection')}"
    except Exception as exc:  # noqa: BLE001 - une route qui plante doit apparaître
        status, erreur = 500, f"{type(exc).__name__}: {exc}"
    ligne = {"statut": status, "ok": status < 300,
             "ms": round((time.perf_counter() - t0) * 1000)}
    if erreur:
        ligne["erreur"] = erreur
    return ligne


def verifier_site(_args):
    """Teste TMDB, puis ouvre chaque écran/API principal en parallèle."""
    app = current_app._get_current_object()
    cid = _compte_mcp()["id"]
    tmdb = _sonde(app, "POST", "/api/settings/tmdb-test", None)
    parcours = list(_PARCOURS)
    for typ in ("film", "serie"):  # une fiche de chaque sorte
        row = db.q1("SELECT id FROM titres WHERE compte_id = ? AND type = ? "
                    "ORDER BY id LIMIT 1", (cid, typ))
        if row:
            parcours.append(("GET", f"/api/title/{row['id']}", None, False))
    liste = db.q1("SELECT id FROM listes WHERE compte_id = ? ORDER BY id LIMIT 1", (cid,))
    if liste:
        parcours.append(("GET", f"/api/lists/{liste['id']}", None, False))

    resultats = []
    pool = ThreadPoolExecutor(max_workers=6)
    try:
        futures = {}
        for method, path, query, via_tmdb in parcours:
            libelle = f"{method} {path}" + (f"?{'&'.join(f'{k}={v}' for k, v in query.items())}"
                                            if query else "")
            ligne = {"route": libelle, "tmdb": via_tmdb}
            resultats.append(ligne)
            if via_tmdb and not tmdb["ok"]:
                ligne.update(ok=None, statut=None, erreur="non testé (TMDB injoignable)")
            else:
                futures[pool.submit(_sonde, app, method, path, query)] = ligne
        fini, _ = wait(futures, timeout=BUDGET_VERIF)
        for fut, ligne in futures.items():
            if fut in fini:
                ligne.update(fut.result())
            else:
                ligne.update(ok=False, statut=None,
                             erreur=f"pas de réponse en {BUDGET_VERIF} s")
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    echecs_site = sum(1 for r in resultats if r["ok"] is False and not r["tmdb"])
    echecs_tmdb = sum(1 for r in resultats if r["ok"] is False and r["tmdb"])
    non_testees = sum(1 for r in resultats if r["ok"] is None)
    bilan = ["site OK ✓" if not echecs_site else f"site : {echecs_site} route(s) en échec"]
    if not tmdb["ok"]:
        bilan.append(f"TMDB injoignable ({tmdb.get('erreur') or tmdb['statut']}), "
                     f"{non_testees} route(s) non testée(s)")
    else:
        bilan.append("TMDB OK ✓" if not echecs_tmdb
                     else f"TMDB : {echecs_tmdb} route(s) en échec")
    return {"bilan": " ; ".join(bilan), "tmdb": tmdb, "routes": resultats}


# ── Outils : bibliothèque ────────────────────────────────────────────────────
def _limite(args, defaut):
    return max(1, int(args.get("limite") or defaut))


def chercher(args):
    data = _ok("GET", "/api/search", {"q": args.get("q", "")})
    return {"resultats": data.get("results", [])[:_limite(args, 10)]}


def lister_bibliotheque(args):
    query = _sans_vide({"statut": args.get("statut"), "type": args.get("type"),
                        "genre": args.get("genre"), "q": args.get("recherche"),
                        "tri": args.get("tri"),
                        "favori": "1" if args.get("favori") else None})
    titres = _ok("GET", "/api/library", query).get("titres", [])
    limite, decalage = _limite(args, LIMITE_DEFAUT), max(0, int(args.get("decalage") or 0))
    page = titres[decalage:decalage + limite]
    return {"total": len(titres), "decalage": decalage, "affiches": len(page),
            "titres": [_alleger(t) for t in page]}


def voir_titre(args):
    data = _ok("GET", f"/api/title/{int(args['titre_id'])}")
    t = data.get("titre", {})
    t["casting"] = (t.get("casting") or [])[:CASTING_MAX]
    t.pop("equipe", None)
    if not args.get("episodes"):
        # Résumé par saison (vus/total) au lieu de la liste complète des épisodes.
        data["saisons"] = [{"numero": s["numero"], "vus": s["vus"], "total": s["total"]}
                           for s in data.get("saisons", [])]
    return data


def apercu_tmdb(args):
    return _ok("GET", "/api/preview", {"tmdb_id": args["tmdb_id"], "type": args["type"]})


def ajouter_titre(args):
    if args.get("tmdb_id"):
        tmdb_id, typ = int(args["tmdb_id"]), args.get("type")
        existant = db.q1("SELECT id, statut FROM titres WHERE compte_id = ? AND tmdb_id = ? "
                         "AND type = ?", (_compte_mcp()["id"], tmdb_id, typ))
        if existant and not args.get("statut"):
            # « Ajoute Inception » alors qu'il est déjà vu : on ne touche à rien
            # (avant, il repassait « à voir »).
            return {"deja_present": True, "id": existant["id"], "statut": existant["statut"]}
        # Sans statut, la route met « à voir » à un titre nouveau seulement.
        return _ok("POST", "/api/library", body=_sans_vide({
            "tmdb_id": tmdb_id, "type": typ, "statut": args.get("statut")}))
    if not args.get("titre"):
        raise OutilErreur("Donne soit tmdb_id (+ type), soit titre pour un ajout manuel.")
    return _ok("POST", "/api/library/manual", body=_sans_vide({
        "titre": args["titre"], "type": args.get("type"), "annee": args.get("annee"),
        "statut": args.get("statut", "a_voir")}))


def modifier_titre(args):
    body = _sans_vide({"statut": args.get("statut")})
    if "favori" in args:
        body["favori"] = bool(args["favori"])
    if not body:
        raise OutilErreur("Rien à modifier : précise statut et/ou favori.")
    return _ok("PATCH", f"/api/library/{int(args['titre_id'])}", body=body)


def supprimer_titre(args):
    titre_id = int(args["titre_id"])
    t = _ok("GET", f"/api/title/{titre_id}").get("titre", {})
    if not _confirme(args):
        return {"apercu": f"Supprimerait « {t.get('titre')} » (#{titre_id}) et tout son "
                          "historique. Relance avec confirm=\"OUI\" après accord de Noë."}
    _ok("DELETE", f"/api/library/{titre_id}")
    return {"ok": True, "supprime": t.get("titre")}


def enregistrer_visionnage(args):
    return _ok("POST", f"/api/title/{int(args['titre_id'])}/watch",
               body=_sans_vide({"date": args.get("date")}))


def marquer_episodes(args):
    titre_id, portee = int(args["titre_id"]), args.get("portee", "episode")
    body = {"action": args.get("action", "seen")}
    if portee == "serie":
        path = f"/api/title/{titre_id}/mark"
    elif portee == "saison":
        if args.get("saison") is None:
            raise OutilErreur("Précise la saison à marquer.")
        path = f"/api/title/{titre_id}/season/{int(args['saison'])}/mark"
    elif portee == "episode":
        if args.get("saison") is None or args.get("numero") is None:
            raise OutilErreur("Précise la saison et le numéro de l'épisode.")
        path = (f"/api/title/{titre_id}/episode/{int(args['saison'])}/"
                f"{int(args['numero'])}/toggle")
    else:
        raise OutilErreur("portee : episode, saison ou serie.")
    return _ok("POST", path, body=body)


def creer_alerte(args):
    return _ok("POST", "/api/alerts", body=_sans_vide({
        "titre_id": args.get("titre_id"), "tmdb_id": args.get("tmdb_id"),
        "type": args.get("type"), "canal": args.get("canal", "cine")}))


# ── Outils : listes ──────────────────────────────────────────────────────────
def lister_listes(_args):
    return _ok("GET", "/api/lists")


def voir_liste(args):
    data = _ok("GET", f"/api/lists/{int(args['liste_id'])}")
    if isinstance(data.get("titres"), list):
        data["titres"] = [_alleger(t) for t in data["titres"]]
    return data


def creer_liste(args):
    return _ok("POST", "/api/lists", body={"nom": args["nom"]})


def ajouter_a_liste(args):
    return _ok("POST", f"/api/lists/{int(args['liste_id'])}/items",
               body={"titre_id": int(args["titre_id"])})


def retirer_de_liste(args):
    return _ok("DELETE", f"/api/lists/{int(args['liste_id'])}/items/{int(args['titre_id'])}")


# ── Outils : découverte & statistiques ───────────────────────────────────────
def statistiques(_args):
    return _ok("GET", "/api/stats")


def journal(args):
    events = _ok("GET", "/api/journal").get("events", [])
    return {"events": events[:_limite(args, 30)]}


def suggestions(args):
    return _ok("GET", "/api/suggestions", _sans_vide({"media": args.get("media")}))


def decouvrir(args):
    return _ok("GET", "/api/discover", _sans_vide({
        "type": args.get("type"), "genre": args.get("genre"), "annee": args.get("annee"),
        "pays": args.get("pays"), "plateforme": args.get("plateforme"),
        "note": args.get("note_min"), "tri": args.get("tri"), "page": args.get("page")}))


def sorties_a_venir(args):
    return _ok("GET", "/api/upcoming", _sans_vide({"page": args.get("page")}))


# ── Outils : maintenance ─────────────────────────────────────────────────────
def reparer_donnees(args):
    if not _confirme(args):
        data = _ok("POST", "/api/repair", body={"simulation": True})
        return {"apercu": "Rien n'a été modifié. Voici ce qui serait corrigé ; relance "
                          "avec confirm=\"OUI\" après accord de Noë pour appliquer.",
                "a_corriger": data.get("fixes")}
    return _ok("POST", "/api/repair")


def _endpoint(method, path):
    """Endpoint Flask que la requête exécuterait, sinon None (404/405/redirection)."""
    try:
        endpoint, _ = current_app.url_map.bind("localhost").match(path, method=method)
    except Exception:  # noqa: BLE001 - NotFound, MethodNotAllowed, RequestRedirect
        return None
    return endpoint


def appel_api(args):
    """Accès générique à n'importe quelle route /api/* (tests poussés)."""
    method = str(args.get("methode", "GET")).upper()
    if method not in _METHODES:
        raise OutilErreur(f"Méthode non prise en charge : {method}.")
    brut, _, qs = str(args.get("chemin", "")).partition("?")
    # Chemin décodé et normalisé une fois pour toutes : c'est CE chemin qui est
    # contrôlé puis exécuté (plus d'écart possible entre les deux).
    path = posixpath.normpath("/" + unquote(brut).lstrip("/"))
    if not _CHEMIN_OK.fullmatch(path):
        raise OutilErreur("Chemin invalide : seules les routes /api/... sont accessibles "
                          "(paramètres d'URL dans « requete »).")
    endpoint = _endpoint(method, path)
    if endpoint is None:  # route inconnue : on n'exécute rien (aucune garde fiable)
        raise OutilErreur(f"Route inconnue : {method} {path}.")
    if endpoint in _ENDPOINTS_INTERDITS:
        raise OutilErreur("La clé du connecteur se gère dans Paramètres, pas depuis Claude.")
    sensible = method == "DELETE" or (method != "GET" and (
        endpoint in _ENDPOINTS_SENSIBLES or endpoint.split(".")[0] in _BLUEPRINTS_SENSIBLES))
    if sensible and not _confirme(args):
        return {"apercu": f"{method} {path} est une action sensible. Relance avec "
                          "confirm=\"OUI\" après accord de Noë."}
    status, data = api(method, path, args.get("requete") or qs or None, args.get("corps"))
    texte = json.dumps(data, ensure_ascii=False, default=str)
    if len(texte) > REPONSE_MAX:
        return {"statut": status, "tronque": True, "taille": len(texte),
                "reponse_debut": texte[:REPONSE_MAX],
                "conseil": "Réponse trop longue : filtre avec « requete » ou utilise "
                           "un outil dédié (lister_bibliotheque…)."}
    return {"statut": status, "reponse": data}


def mettre_a_jour_site(args):
    version = _ok("GET", "/api/version")
    if not _confirme(args):
        return {"apercu": "Récupérerait la dernière version GitHub puis redémarrerait "
                          "le site (~10 s, données intactes). Relance avec "
                          "confirm=\"OUI\" après accord de Noë.",
                "version_actuelle": version.get("version"),
                "dernier_changement": version.get("message")}
    # Journalisée par la route elle-même, après coup (lancée / échec), au nom « mcp ».
    return _ok("POST", "/api/update")


# ── Catalogue (nom → description, schéma, fonction) ──────────────────────────
def _schema(props=None, required=()):
    return {"type": "object", "properties": props or {}, "required": list(required)}


_INT = {"type": "integer"}
_LIMITE = {"type": "integer", "minimum": 1}
_STATUT = {"type": "string", "enum": ["a_voir", "en_cours", "vu"],
           "description": "a_voir = à voir, en_cours, vu."}
_TYPE = {"type": "string", "enum": ["film", "serie"]}
_CONFIRM = {"type": "string", "description": "Mettre \"OUI\" pour appliquer. "
            "Sinon, simple aperçu. Toujours demander l'accord de Noë avant."}

TOOLS = {
    "etat_du_site": (
        "État de cinéthèque : version installée, dernier changement, heure de "
        "démarrage, clé TMDB configurée, taille de la bibliothèque.",
        _schema(), etat_du_site),
    "verifier_site": (
        "Teste le site en direct : ouvre chaque écran et API principal (bibliothèque, "
        "listes, stats, découverte, recherche TMDB…) et renvoie statut + temps de "
        "réponse de chacun. Lecture seule, sûr.",
        _schema(), verifier_site),
    "chercher": (
        "Recherche un film ou une série sur TMDB (indique s'il est déjà dans la "
        "bibliothèque). Donne le tmdb_id nécessaire pour ajouter_titre.",
        _schema({"q": {"type": "string"}, "limite": _LIMITE}, ["q"]), chercher),
    "lister_bibliotheque": (
        "Liste la bibliothèque avec filtres. Renvoie l'id local de chaque titre "
        "(titre_id), utilisé par les autres outils. Page suivante : decalage.",
        _schema({"statut": _STATUT, "type": _TYPE, "genre": {"type": "string"},
                 "favori": {"type": "boolean"}, "recherche": {"type": "string",
                 "description": "Filtre sur le titre."},
                 "tri": {"type": "string", "enum": ["ajout", "titre", "annee", "note"]},
                 "limite": {**_LIMITE, "description": f"Défaut {LIMITE_DEFAUT}."},
                 "decalage": {"type": "integer", "minimum": 0,
                              "description": "Titres à sauter (pagination)."}}),
        lister_bibliotheque),
    "voir_titre": (
        "Fiche complète d'un titre de la bibliothèque : infos, visionnages, "
        "progression par saison, prochain épisode, alerte.",
        _schema({"titre_id": _INT, "episodes": {"type": "boolean",
                 "description": "true = liste détaillée de chaque épisode."}},
                ["titre_id"]), voir_titre),
    "apercu_tmdb": (
        "Fiche TMDB d'un titre SANS l'ajouter (résumé, plateformes, casting).",
        _schema({"tmdb_id": _INT, "type": _TYPE}, ["tmdb_id", "type"]), apercu_tmdb),
    "ajouter_titre": (
        "Ajoute un titre à la bibliothèque : depuis TMDB (tmdb_id + type) ou "
        "manuellement (titre + type [+ annee]) s'il est absent de TMDB. Un titre "
        "déjà présent n'est pas modifié, sauf si un statut est donné.",
        _schema({"tmdb_id": _INT, "type": _TYPE, "statut": _STATUT,
                 "titre": {"type": "string"}, "annee": _INT}, ["type"]), ajouter_titre),
    "modifier_titre": (
        "Change le statut (à voir / en cours / vu) et/ou le favori d'un titre.",
        _schema({"titre_id": _INT, "statut": _STATUT, "favori": {"type": "boolean"}},
                ["titre_id"]), modifier_titre),
    "supprimer_titre": (
        "Supprime un titre et son historique. SÉCURITÉ : n'agit QUE si confirm "
        "vaut \"OUI\" ; sinon aperçu.",
        _schema({"titre_id": _INT, "confirm": _CONFIRM}, ["titre_id"]), supprimer_titre),
    "enregistrer_visionnage": (
        "Enregistre un visionnage d'un film (vu / revu), à la date du jour par défaut.",
        _schema({"titre_id": _INT, "date": {"type": "string",
                 "description": "AAAA-MM-JJ (optionnel)."}}, ["titre_id"]),
        enregistrer_visionnage),
    "marquer_episodes": (
        "Marque des épisodes d'une série : un épisode (saison + numero), une "
        "saison entière, ou la série entière.",
        _schema({"titre_id": _INT,
                 "portee": {"type": "string", "enum": ["episode", "saison", "serie"]},
                 "saison": _INT, "numero": _INT,
                 "action": {"type": "string", "enum": ["seen", "revu", "remove", "unmark"],
                            "description": "seen = vu (×1), revu = +1 visionnage, "
                                           "remove = −1, unmark = tout décocher. "
                                           "Saison/série : seuls les épisodes déjà "
                                           "diffusés sont cochés."}},
                ["titre_id", "portee"]), marquer_episodes),
    "creer_alerte": (
        "Crée une alerte de sortie (ciné ou streaming) pour un titre "
        "(titre_id local, ou tmdb_id + type s'il n'est pas encore ajouté).",
        _schema({"titre_id": _INT, "tmdb_id": _INT, "type": _TYPE,
                 "canal": {"type": "string", "enum": ["cine", "streaming"]}}),
        creer_alerte),
    "lister_listes": ("Liste les listes (système et perso) avec leur nombre de titres.",
                      _schema(), lister_listes),
    "voir_liste": ("Contenu d'une liste.", _schema({"liste_id": _INT}, ["liste_id"]),
                   voir_liste),
    "creer_liste": ("Crée une liste perso.", _schema({"nom": {"type": "string"}}, ["nom"]),
                    creer_liste),
    "ajouter_a_liste": ("Ajoute un titre de la bibliothèque à une liste.",
                        _schema({"liste_id": _INT, "titre_id": _INT},
                                ["liste_id", "titre_id"]), ajouter_a_liste),
    "retirer_de_liste": ("Retire un titre d'une liste (le titre reste en bibliothèque).",
                         _schema({"liste_id": _INT, "titre_id": _INT},
                                 ["liste_id", "titre_id"]), retirer_de_liste),
    "statistiques": ("Statistiques de visionnage (temps, genres, compteurs…).",
                     _schema(), statistiques),
    "journal": ("Historique des derniers visionnages, du plus récent au plus ancien.",
                _schema({"limite": _LIMITE}), journal),
    "suggestions": ("Suggestions personnalisées à partir des goûts de la bibliothèque.",
                    _schema({"media": {"type": "string", "enum": ["all", "movie", "tv"]}}),
                    suggestions),
    "decouvrir": (
        "Explore TMDB avec filtres (genre id, année, pays, plateforme id, note min).",
        _schema({"type": _TYPE, "genre": {"type": "string"}, "annee": _INT,
                 "pays": {"type": "string"}, "plateforme": {"type": "string"},
                 "note_min": {"type": "number"}, "page": _INT,
                 "tri": {"type": "string", "enum": ["populaire", "note", "recent"]}}),
        decouvrir),
    "sorties_a_venir": ("Prochaines sorties de films.", _schema({"page": _INT}),
                        sorties_a_venir),
    "reparer_donnees": (
        "Vérifie les incohérences de la base (films « vu » sans visionnage, "
        "compteurs d'épisodes). Sans confirm : simple rapport, rien n'est modifié. "
        "Avec confirm=\"OUI\" : corrige, sans rien supprimer.",
        _schema({"confirm": _CONFIRM}), reparer_donnees),
    "appel_api": (
        "Accès avancé à n'importe quelle route /api/* du site, pour tester une "
        "fonction précise. DELETE et écritures sensibles (reset, import, mise à "
        "jour, réglages, réparation, comptes, mot de passe, Cloudflare) exigent "
        "confirm=\"OUI\". Réponse tronquée au-delà de 50 000 caractères.",
        _schema({"methode": {"type": "string",
                             "enum": ["GET", "POST", "PATCH", "DELETE"]},
                 "chemin": {"type": "string", "description": "Ex. /api/library"},
                 "requete": {"type": "object", "description": "Paramètres d'URL."},
                 "corps": {"type": "object", "description": "Corps JSON."},
                 "confirm": _CONFIRM}, ["chemin"]), appel_api),
    "mettre_a_jour_site": (
        "Met à jour cinéthèque depuis GitHub puis redémarre le site (données "
        "intactes). SÉCURITÉ : n'agit QUE si confirm vaut \"OUI\" ; sinon aperçu "
        "(version actuelle). Toujours demander l'accord de Noë avant.",
        _schema({"confirm": _CONFIRM}), mettre_a_jour_site),
}


# Indications MCP (annotations) : le client peut laisser passer les lectures
# et demander l'accord de Noë pour le reste — une vraie barrière, là où
# confirm est rempli par le modèle lui-même.
LECTURE_SEULE = {"etat_du_site", "verifier_site", "chercher", "lister_bibliotheque",
                 "voir_titre", "apercu_tmdb", "lister_listes", "voir_liste",
                 "statistiques", "journal", "suggestions", "decouvrir", "sorties_a_venir"}
_DESTRUCTIFS = {"supprimer_titre", "retirer_de_liste", "modifier_titre", "marquer_episodes",
                "appel_api", "mettre_a_jour_site"}
_IDEMPOTENTS = {"ajouter_titre", "modifier_titre", "supprimer_titre", "creer_alerte",
                "ajouter_a_liste", "retirer_de_liste"}
_MONDE_OUVERT = {"verifier_site", "chercher", "apercu_tmdb", "ajouter_titre", "creer_alerte",
                 "suggestions", "decouvrir", "sorties_a_venir", "appel_api",
                 "mettre_a_jour_site"}  # TMDB, GitHub


def _annotations(nom):
    lecture = nom in LECTURE_SEULE
    return {"readOnlyHint": lecture,
            "destructiveHint": not lecture and nom in _DESTRUCTIFS,
            "idempotentHint": lecture or nom in _IDEMPOTENTS,
            "openWorldHint": nom in _MONDE_OUVERT}


def catalogue():
    """Liste MCP ``tools/list`` (calculée une fois, le catalogue est figé)."""
    return [{"name": nom, "description": desc, "inputSchema": schema,
             "annotations": _annotations(nom)}
            for nom, (desc, schema, _fn) in TOOLS.items()]
