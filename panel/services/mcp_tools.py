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
import time

from flask import current_app

import auth
import db

DEMARRAGE = int(time.time())

# Taille des réponses : on allège ce qui part vers Claude (moins de jetons,
# réponses plus rapides). Les détails restent accessibles via les paramètres.
LIMITE_DEFAUT = 50
CASTING_MAX = 8
CHAMPS_TITRE = ("id", "tmdb_id", "type", "titre", "annee", "statut", "favori",
                "genres", "note", "nb_saisons", "nb_vues", "progression",
                "prochain_episode", "date_ajout")

# Appels « sensibles » de l'outil générique : exigent confirm="OUI".
_SENSIBLES = ("/api/reset", "/api/import", "/api/update", "/api/settings/password",
              "/api/comptes", "/api/impersonate")


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


def api(method, path, query=None, body=None):
    """Rejoue ``METHOD path`` sur l'app, connecté en super-admin. → (statut, json).

    Un contexte d'application neuf isole ``g`` (cache du compte courant) de la
    requête /mcp englobante.
    """
    app = current_app._get_current_object()
    compte = _compte_mcp()
    with app.app_context():
        client = app.test_client()
        with client.session_transaction() as sess:
            sess["compte_id"], sess["role"] = compte["id"], compte["role"]
        resp = client.open(path, method=method, query_string=query or None,
                           json=body)
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
    return {k: titre[k] for k in CHAMPS_TITRE if k in titre}


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


# Parcours de contrôle : routes en lecture seule, comme les ouvre l'interface.
_PARCOURS = [
    ("GET", "/", None), ("GET", "/sw.js", None),
    ("GET", "/api/version", None), ("GET", "/api/settings", None),
    ("GET", "/api/library", None), ("GET", "/api/library", {"type": "serie"}),
    ("GET", "/api/to-add", None), ("GET", "/api/lists", None),
    ("GET", "/api/lists/presets", None), ("GET", "/api/stats", None),
    ("GET", "/api/journal", None), ("GET", "/api/genres", None),
    ("GET", "/api/suggestions", None), ("GET", "/api/upcoming", None),
    ("GET", "/api/discover", None), ("GET", "/api/providers/all", None),
    ("GET", "/api/search", {"q": "Inception"}),
    ("POST", "/api/settings/tmdb-test", None),
]


def verifier_site(_args):
    """Ouvre chaque écran/API principal et chronomètre la réponse."""
    resultats, en_echec = [], 0
    parcours = list(_PARCOURS)
    premier = db.q1("SELECT id FROM titres WHERE compte_id = ? ORDER BY id LIMIT 1",
                    (_compte_mcp()["id"],))
    if premier:
        parcours.append(("GET", f"/api/title/{premier['id']}", None))
    for method, path, query in parcours:
        t0 = time.perf_counter()
        try:
            status, data = api(method, path, query)
            erreur = data.get("error") if isinstance(data, dict) else None
        except Exception as exc:  # une route qui plante doit apparaître, pas tout casser
            status, erreur = 500, f"{type(exc).__name__}: {exc}"
        ok = status < 400
        en_echec += not ok
        ligne = {"route": f"{method} {path}", "statut": status, "ok": ok,
                 "ms": round((time.perf_counter() - t0) * 1000)}
        if erreur:
            ligne["erreur"] = erreur
        resultats.append(ligne)
    return {"bilan": "tout est OK ✓" if not en_echec else f"{en_echec} route(s) en échec",
            "routes": resultats}


# ── Outils : bibliothèque ────────────────────────────────────────────────────
def chercher(args):
    data = _ok("GET", "/api/search", {"q": args.get("q", "")})
    return {"resultats": data.get("results", [])[:int(args.get("limite") or 10)]}


def lister_bibliotheque(args):
    query = _sans_vide({"statut": args.get("statut"), "type": args.get("type"),
                        "genre": args.get("genre"), "q": args.get("recherche"),
                        "tri": args.get("tri"),
                        "favori": "1" if args.get("favori") else None})
    titres = _ok("GET", "/api/library", query).get("titres", [])
    limite = int(args.get("limite") or LIMITE_DEFAUT)
    return {"total": len(titres), "affiches": min(limite, len(titres)),
            "titres": [_alleger(t) for t in titres[:limite]]}


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
        body = {"tmdb_id": args["tmdb_id"], "type": args.get("type"),
                "statut": args.get("statut", "a_voir")}
        return _ok("POST", "/api/library", body=body)
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
        path = f"/api/title/{titre_id}/season/{int(args['saison'])}/mark"
    else:
        if body["action"] == "unmark":
            body["action"] = "remove"  # un épisode seul se retire par « remove »
        path = (f"/api/title/{titre_id}/episode/{int(args['saison'])}/"
                f"{int(args['numero'])}/toggle")
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
    return {"events": events[:int(args.get("limite") or 30)]}


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
def reparer_donnees(_args):
    return _ok("POST", "/api/repair")


def appel_api(args):
    """Accès générique à n'importe quelle route /api/* (tests poussés)."""
    method = str(args.get("methode", "GET")).upper()
    path = "/" + str(args.get("chemin", "")).lstrip("/")
    if not path.startswith("/api/"):
        raise OutilErreur("Seules les routes /api/... sont accessibles.")
    sensible = method == "DELETE" or path.startswith(_SENSIBLES)
    if sensible and not _confirme(args):
        return {"apercu": f"{method} {path} est une action sensible. Relance avec "
                          "confirm=\"OUI\" après accord de Noë."}
    status, data = api(method, path, args.get("requete"), args.get("corps"))
    return {"statut": status, "reponse": data}


def mettre_a_jour_site(args):
    version = _ok("GET", "/api/version")
    if not _confirme(args):
        return {"apercu": "Récupérerait la dernière version GitHub puis redémarrerait "
                          "le site (~10 s, données intactes). Relance avec "
                          "confirm=\"OUI\" après accord de Noë.",
                "version_actuelle": version.get("version"),
                "dernier_changement": version.get("message")}
    db.audit("mcp_mise_a_jour", acteur="mcp")
    return _ok("POST", "/api/update")


# ── Catalogue (nom → description, schéma, fonction) ──────────────────────────
def _schema(props=None, required=()):
    return {"type": "object", "properties": props or {}, "required": list(required)}


_INT = {"type": "integer"}
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
        _schema({"q": {"type": "string"}, "limite": _INT}, ["q"]), chercher),
    "lister_bibliotheque": (
        "Liste la bibliothèque avec filtres. Renvoie l'id local de chaque titre "
        "(titre_id), utilisé par les autres outils.",
        _schema({"statut": _STATUT, "type": _TYPE, "genre": {"type": "string"},
                 "favori": {"type": "boolean"}, "recherche": {"type": "string",
                 "description": "Filtre sur le titre."},
                 "tri": {"type": "string", "enum": ["ajout", "titre", "annee"]},
                 "limite": {"type": "integer", "description": f"Défaut {LIMITE_DEFAUT}."}}),
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
        "manuellement (titre + type [+ annee]) s'il est absent de TMDB.",
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
                                           "remove = −1, unmark = tout décocher."}},
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
                _schema({"limite": _INT}), journal),
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
        "Vérifie et répare les incohérences de la base sans rien supprimer "
        "(films « vu » sans visionnage, compteurs d'épisodes).",
        _schema(), reparer_donnees),
    "appel_api": (
        "Accès avancé à n'importe quelle route /api/* du site, pour tester une "
        "fonction précise. DELETE et actions sensibles (reset, import, update, "
        "comptes, mot de passe) exigent confirm=\"OUI\".",
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


def catalogue():
    """Liste MCP ``tools/list`` (calculée une fois, le catalogue est figé)."""
    return [{"name": nom, "description": desc, "inputSchema": schema}
            for nom, (desc, schema, _fn) in TOOLS.items()]
