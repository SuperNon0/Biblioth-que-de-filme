"""Serveur MCP de cinéthèque : permet à Claude de tester et piloter le site.

Protocole : MCP « Streamable HTTP » en mode **sans état** (une requête JSON-RPC
→ une réponse JSON, pas de flux SSE). Suffisant pour des outils, et sans
connexion longue à garder ouverte. Voir docs/mcp.md.

Authentification : une **clé API MCP dédiée**, distincte du mot de passe du
site et de la clé TMDB. Elle se génère dans Paramètres → Connecteur Claude
(super-admin) et n'est affichée qu'une fois. Seule son empreinte SHA-256 est
gardée en base (``app_settings.mcp_cle_hash``) : rien de secret dans le dépôt
ni en clair sur le disque. La clé se présente :
  - dans l'en-tête ``Authorization: Bearer <clé>`` (clients qui le permettent) ;
  - ou dans l'URL ``/mcp/<clé>`` (connecteur personnalisé de claude.ai).

Les outils eux-mêmes sont dans ``services/mcp_tools.py``.
"""
import hashlib
import hmac
import json
import secrets
import time

from flask import Blueprint, Response, jsonify, request

import auth
import db
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
    entete = request.headers.get("Authorization", "")
    if entete.lower().startswith("bearer "):
        return entete[7:].strip()
    return cle_url or ""


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


def _appeler_outil(params):
    nom, args = params.get("name"), params.get("arguments") or {}
    outil = mcp_tools.TOOLS.get(nom)
    if outil is None:
        return None
    try:
        return _texte(outil[2](args))
    except mcp_tools.OutilErreur as exc:
        return _texte({"erreur": str(exc)}, is_error=True)
    except (KeyError, ValueError, TypeError) as exc:
        return _texte({"erreur": f"Paramètre manquant ou invalide : {exc}"}, is_error=True)


def _traiter(msg):
    """Traite UN message JSON-RPC. Renvoie la réponse, ou None (notification)."""
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
        return _erreur(None, -32600, "Requête JSON-RPC invalide.")
    rid, method = msg.get("id"), msg.get("method", "")
    if "id" not in msg:  # notification (ex. notifications/initialized)
        return None
    params = msg.get("params") or {}
    if method == "initialize":
        demande = params.get("protocolVersion")
        return _resultat(rid, {
            "protocolVersion": demande if demande in PROTOCOLES else PROTOCOLES[0],
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "cinetheque", "version": "1.0"},
            "instructions": INSTRUCTIONS,
        })
    if method == "ping":
        return _resultat(rid, {})
    if method == "tools/list":
        return _resultat(rid, {"tools": _CATALOGUE})
    if method == "tools/call":
        res = _appeler_outil(params)
        if res is None:
            return _erreur(rid, -32602, f"Outil inconnu : {params.get('name')}")
        return _resultat(rid, res)
    return _erreur(rid, -32601, f"Méthode non prise en charge : {method}")


@bp.route("/mcp", methods=["GET", "POST", "DELETE"], defaults={"cle_url": None})
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
        reponses = [r for r in map(_traiter, payload) if r is not None]
        return jsonify(reponses) if reponses else Response(status=202)
    reponse = _traiter(payload)
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
    db.audit("mcp_cle_generee", acteur=(auth.current_compte() or {}).get("email"))
    return jsonify(ok=True, cle=cle)


@bp.delete("/api/mcp/cle")
@auth.super_admin_required
def revoquer_cle():
    db.run("DELETE FROM app_settings WHERE cle IN ('mcp_cle_hash', 'mcp_cle_cree')")
    db.audit("mcp_cle_revoquee", acteur=(auth.current_compte() or {}).get("email"))
    return jsonify(ok=True)
