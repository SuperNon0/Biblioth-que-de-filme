"""Serveur MCP de cinéthèque : permet à Claude de tester et piloter le site.

Protocole : MCP « Streamable HTTP » en mode **sans état** (une requête JSON-RPC
→ une réponse JSON, pas de flux SSE). Suffisant pour des outils, et sans
connexion longue à garder ouverte. Voir docs/mcp.md.

Authentification : une **clé API MCP dédiée**, distincte du mot de passe du
site et de la clé TMDB. Elle se génère dans Paramètres → Connecteur Claude
(super-admin) et n'est affichée qu'une fois. Seule son empreinte SHA-256 est
gardée en base (``app_settings.mcp_cle_hash``) : rien de secret dans le dépôt
ni en clair sur le disque. La clé se présente **dans un en-tête** (méthode
recommandée, la clé n'apparaît ni dans l'URL ni dans les journaux) :
  - ``Authorization: Bearer <clé>`` ;
  - ou ``X-API-Key: <clé>``.
En dernier recours, ``/mcp/<clé>`` reste accepté pour un client sans en-têtes.

Les outils eux-mêmes sont dans ``services/mcp_tools.py``.
"""
import hashlib
import hmac
import json
import secrets
import time

from flask import Blueprint, Response, current_app, jsonify, request

import auth
import db
from routes.settings import numero_version
from services import mcp_tools

bp = Blueprint("mcp", __name__)

PROTOCOLES = ("2025-06-18", "2025-03-26", "2024-11-05")
INSTRUCTIONS = (
    "Accès à cinéthèque, la bibliothèque de films et séries de Noë. Réponds en "
    "français. Pour tester le site, commence par etat_du_site puis verifier_site. "
    "Les outils prennent l'id local d'un titre (titre_id, voir lister_bibliotheque) ; "
    "chercher donne le tmdb_id pour ajouter un titre. Demande toujours confirmation "
    "avant une suppression ou une mise à jour du site (confirm=\"OUI\")."
)
_CATALOGUE = mcp_tools.catalogue()


# ── Clé API MCP ──────────────────────────────────────────────────────────────
def _empreinte(cle):
    return hashlib.sha256(cle.encode("utf-8")).hexdigest()


def _cle_valide(cle):
    attendu = db.get_setting("mcp_cle_hash")
    # compare_digest : temps constant (pas de fuite par chronométrage).
    return bool(attendu and cle) and hmac.compare_digest(_empreinte(cle), attendu)


def _cle_presentee(cle_url):
    """Clé envoyée par le client : en-tête d'abord, URL en dernier recours."""
    entete = request.headers.get("Authorization", "")
    if entete.lower().startswith("bearer "):
        return entete[7:].strip()
    return (request.headers.get("X-API-Key") or cle_url or "").strip()


# ── JSON-RPC ─────────────────────────────────────────────────────────────────
def _resultat(rid, result):
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def _erreur(rid, code, message):
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


def _texte(data, is_error=False):
    out = {"content": [{"type": "text",
                        "text": json.dumps(data, ensure_ascii=False, default=str)}]}
    if is_error:
        out["isError"] = True
    return out


def _abrege(nom, args):
    """Arguments d'un outil pour le journal d'audit (jamais un corps d'appel_api :
    il peut contenir un mot de passe ou une clé)."""
    if nom == "appel_api":
        return f"{args.get('methode', 'GET')} {args.get('chemin', '')}"
    return json.dumps({k: v for k, v in args.items() if k != "confirm"},
                      ensure_ascii=False, default=str)[:200]


def _appeler_outil(params):
    nom, args = params.get("name"), params.get("arguments") or {}
    outil = mcp_tools.TOOLS.get(nom)
    if outil is None:
        return None
    try:
        resultat = outil[2](args)
    except mcp_tools.OutilErreur as exc:
        out = _texte({"erreur": str(exc)}, is_error=True)
    except (KeyError, ValueError, TypeError) as exc:
        out = _texte({"erreur": f"Paramètre manquant ou invalide : {exc}"}, is_error=True)
    except Exception as exc:  # noqa: BLE001 - un outil en panne ne fait pas tomber /mcp
        db.rollback_open()
        current_app.logger.exception("Outil MCP « %s » en échec", nom)
        out = _texte({"erreur": f"Erreur interne : {type(exc).__name__}: {exc}"},
                     is_error=True)
    else:
        out = _texte(resultat)
        if isinstance(resultat, dict) and "apercu" in resultat:
            return out  # simple aperçu : rien n'a été écrit
    if nom not in mcp_tools.LECTURE_SEULE:
        # Trace de ce que Claude a fait (réussi ou non), au nom « mcp ».
        db.audit("mcp_outil", acteur="mcp", cible=nom,
                 detail=_abrege(nom, args) + (" → erreur" if out.get("isError") else ""))
    return out


def _traiter(msg):
    """Traite UN message JSON-RPC. Renvoie la réponse, ou None (notification)."""
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
        return _erreur(None, -32600, "Requête JSON-RPC invalide.")
    if "method" not in msg:  # réponse du client à une requête : rien à répondre
        return None
    rid, method = msg.get("id"), msg.get("method")
    if "id" not in msg:  # notification (ex. notifications/initialized)
        return None
    if not isinstance(method, str):
        return _erreur(rid, -32600, "Requête JSON-RPC invalide.")
    params = msg.get("params") or {}
    if not isinstance(params, dict):
        return _erreur(rid, -32602, "« params » doit être un objet.")
    if method == "initialize":
        demande = params.get("protocolVersion")
        return _resultat(rid, {
            "protocolVersion": demande if demande in PROTOCOLES else PROTOCOLES[0],
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "cinetheque", "version": numero_version() or "1.0"},
            "instructions": INSTRUCTIONS,
        })
    if method == "ping":
        return _resultat(rid, {})
    if method == "tools/list":
        return _resultat(rid, {"tools": _CATALOGUE})
    if method == "tools/call":
        if not isinstance(params.get("arguments") or {}, dict):
            return _erreur(rid, -32602, "« arguments » doit être un objet.")
        res = _appeler_outil(params)
        if res is None:
            return _erreur(rid, -32602, f"Outil inconnu : {params.get('name')}")
        return _resultat(rid, res)
    return _erreur(rid, -32601, f"Méthode non prise en charge : {method}")


def _traiter_sur(msg):
    """``_traiter`` sans jamais de page d'erreur HTML : un imprévu devient une
    erreur JSON-RPC lisible par le client."""
    try:
        return _traiter(msg)
    except Exception:  # noqa: BLE001
        db.rollback_open()
        current_app.logger.exception("Message MCP en échec")
        rid = msg.get("id") if isinstance(msg, dict) else None
        return _erreur(rid, -32603, "Erreur interne du serveur MCP.")


@bp.route("/mcp", methods=["GET", "POST", "DELETE"], defaults={"cle_url": None},
          strict_slashes=False)
@bp.route("/mcp/<cle_url>", methods=["GET", "POST", "DELETE"])
def endpoint(cle_url):
    if not _cle_valide(_cle_presentee(cle_url)):
        time.sleep(0.5)  # freine les essais de clé à l'aveugle
        return jsonify(error="Clé API MCP invalide ou absente."), 401
    if request.method != "POST":
        # Mode sans état : ni flux SSE (GET) ni session à fermer (DELETE).
        return Response(status=405, headers={"Allow": "POST"})
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify(_erreur(None, -32700, "JSON illisible.")), 400
    if isinstance(payload, list):  # lot de messages
        if not payload:
            return jsonify(_erreur(None, -32600, "Lot vide.")), 400
        reponses = [r for r in map(_traiter_sur, payload) if r is not None]
        return jsonify(reponses) if reponses else Response(status=202)
    reponse = _traiter_sur(payload)
    return jsonify(reponse) if reponse is not None else Response(status=202)


# ── Gestion de la clé depuis Paramètres (super-admin) ────────────────────────
@bp.get("/api/mcp")
@auth.super_admin_required
def statut():
    cree = db.get_setting("mcp_cle_cree")
    return jsonify(active=bool(db.get_setting("mcp_cle_hash")),
                   cree=time.strftime("%d/%m/%Y %H:%M", time.localtime(int(cree)))
                   if cree else None)


@bp.post("/api/mcp/cle")
@auth.super_admin_required
def generer_cle():
    """Crée (ou remplace) la clé : l'ancienne cesse aussitôt de fonctionner."""
    cle = "cine_" + secrets.token_urlsafe(32)
    db.set_setting("mcp_cle_hash", _empreinte(cle))
    db.set_setting("mcp_cle_cree", str(int(time.time())))
    db.audit("mcp_cle_generee", acteur=auth.acteur())
    return jsonify(ok=True, cle=cle)


@bp.delete("/api/mcp/cle")
@auth.super_admin_required
def revoquer_cle():
    db.run("DELETE FROM app_settings WHERE cle IN ('mcp_cle_hash', 'mcp_cle_cree')")
    db.audit("mcp_cle_revoquee", acteur=auth.acteur())
    return jsonify(ok=True)
