"""Authentification de cinéthèque — multi-comptes derrière Cloudflare Zero Trust.

Deux couches (docs/authentification-v2.md §1 et §9) :
  - **Cloudflare Access** = portier e-mail (qui peut *frapper à la porte*) ;
  - **l'application** = rôles + cycle de vie des comptes (ce qui se passe *après*).

⚠️ Sécurité (§9.1) : on ne fait JAMAIS confiance à l'en-tête
`Cf-Access-Authenticated-User-Email` seul en production — il est falsifiable si
l'origine est joignable hors Cloudflare. On vérifie le JWT `Cf-Access-Jwt-Assertion`
contre les clés publiques de l'équipe Cloudflare + `aud` + `iss`.

Site « perso » (données cloisonnées) : `cap_account_management=off` → un e-mail
autorisé par Cloudflare mais inconnu est créé **automatiquement en `actif`**.
"""
import math
import re
import threading
import time
from functools import wraps

from flask import current_app, g, jsonify, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

import db

# PyJWT est optionnel à l'import : requis seulement si la vérif JWT est active.
# On rattrape BaseException : une lib `cryptography` cassée lève un
# pyo3 PanicException (BaseException, pas Exception). Repli sûr : jwt=None →
# cf_access_email() renvoie None quand la vérif est active (aucun contournement).
try:
    import jwt
    from jwt import PyJWKClient
except BaseException:  # pragma: no cover
    jwt = None
    PyJWKClient = None

_jwk_clients = {}  # cache des clients JWK par équipe Cloudflare
# Nom d'équipe Cloudflare : il sert à construire l'URL des clés publiques et
# l'émetteur (`iss`) attendu, donc aucun autre caractère n'est admis.
TEAM_RE = re.compile(r"[a-z0-9-]{1,63}")


# ── Configuration Cloudflare (UI/app_settings prioritaire sur config) ────────
def _cfg():
    return current_app.config["APP_CONFIG"]


def normalize_team(team):
    """Garde le NOM d'équipe seul : `super-nono`, pas l'URL complète."""
    t = (team or "").strip().lower()
    t = t.removeprefix("https://").removeprefix("http://").strip("/")
    return t.removesuffix(".cloudflareaccess.com").strip("/")


def cf_config():
    """Config Cloudflare effective : réglages en base (UI) sinon config de base."""
    cfg = _cfg()
    team = db.get_setting("cf_team")
    if team is None:
        team = cfg.get("cf_team_domain", "")
    aud = db.get_setting("cf_aud")
    if aud is None:
        aud = cfg.get("cf_aud", "")
    verify_s = db.get_setting("cf_verify")
    verify = bool(cfg.get("cf_verify_jwt", True)) if verify_s is None else verify_s == "1"
    team = normalize_team(team)
    if team and not TEAM_RE.fullmatch(team):
        team = ""  # valeur invalide → vérification impossible, donc refus
    return {"team": team, "aud": (aud or "").strip(), "verify": verify}


def access_managed():
    """True = site « géré » (hub, comptes validés) ; False = site « perso » (auto-actif)."""
    return (_cfg().get("cap_account_management", "off") or "off").strip().lower() != "off"


# ── Cloudflare Access : e-mail vérifié ───────────────────────────────────────
def _get_jwk_client(team):
    if not team or PyJWKClient is None:
        return None
    client = _jwk_clients.get(team)
    if client is None:
        client = PyJWKClient(f"https://{team}.cloudflareaccess.com/cdn-cgi/access/certs")
        _jwk_clients[team] = client
    return client


def _cf_token():
    return (request.headers.get("Cf-Access-Jwt-Assertion")
            or request.cookies.get("CF_Authorization"))


def via_cloudflare():
    """La requête est-elle passée par Cloudflare Access (jeton présent) ?"""
    return bool(_cf_token())


def cf_access_email():
    """E-mail Cloudflare vérifié pour la requête, sinon None."""
    cfg = cf_config()
    header_email = request.headers.get("Cf-Access-Authenticated-User-Email")
    if not cfg["verify"]:
        return header_email.strip().lower() if header_email else None
    token = _cf_token()
    if not token or jwt is None:
        return None
    team, aud = cfg["team"], cfg["aud"]
    client = _get_jwk_client(team)
    if client is None or not aud or not team:
        current_app.logger.warning("Vérif JWT active mais équipe/AUD non renseignés.")
        return None
    try:
        signing_key = client.get_signing_key_from_jwt(token)
        claims = jwt.decode(token, signing_key.key, algorithms=["RS256"],
                            audience=aud, issuer=f"https://{team}.cloudflareaccess.com")
    except Exception as exc:
        current_app.logger.warning("JWT Cloudflare rejeté : %s", exc)
        return None
    return (claims.get("email") or "").strip().lower() or None


def cf_diagnostic():
    """Diagnostic Cloudflare pour Paramètres → Diagnostic."""
    cfg = cf_config()
    header_email = request.headers.get("Cf-Access-Authenticated-User-Email")
    token = _cf_token()
    d = {"team": cfg["team"], "aud": cfg["aud"], "verify": cfg["verify"],
         "header_email": header_email, "has_token": bool(token),
         "jwt_status": "non testé", "jwt_email": None, "jwt_error": None}
    if not token:
        d["jwt_error"] = "Aucun jeton Cloudflare reçu (origine peut-être pas derrière Access)."
        return d
    if not cfg["team"] or not cfg["aud"]:
        d["jwt_error"] = "Équipe et/ou AUD non renseignés."
        return d
    if jwt is None:
        d["jwt_error"] = "PyJWT indisponible (pip install PyJWT[crypto])."
        return d
    try:
        client = _get_jwk_client(cfg["team"])
        signing_key = client.get_signing_key_from_jwt(token)
        claims = jwt.decode(token, signing_key.key, algorithms=["RS256"],
                            audience=cfg["aud"],
                            issuer=f"https://{cfg['team']}.cloudflareaccess.com")
        d["jwt_status"], d["jwt_email"] = "OK ✓", (claims.get("email") or "").strip().lower() or None
    except Exception as exc:
        d["jwt_status"], d["jwt_error"] = "échec ✗", str(exc)
    return d


# ── Comptes / session ────────────────────────────────────────────────────────
def get_compte(compte_id):
    if not compte_id:
        return None
    return db.q1("SELECT * FROM comptes WHERE id = ?", (compte_id,))


def current_compte():
    """Compte *effectif* (celui impersonné le cas échéant), mis en cache sur g."""
    if "compte" not in g:
        g.compte = get_compte(session.get("compte_id"))
    return g.compte


def compte_courant_id():
    """Id du compte effectif — clé de cloisonnement des données métier."""
    c = current_compte()
    return c["id"] if c else None


def is_super_admin():
    """Rôle réel : celui de l'impersonateur s'il y en a un, sinon du compte.
    Un compte bloqué entre-temps perd ses droits, même avec une ancienne session."""
    if session.get("impersonator_id"):
        c = get_compte(session["impersonator_id"])
    else:
        c = current_compte()
    return bool(c and c["role"] == "super_admin" and c["etat"] == "actif")


def is_base_admin():
    """Super-admin AVEC login local (mot de passe) = compte racine du site."""
    real_id = session.get("impersonator_id") or session.get("compte_id")
    c = get_compte(real_id)
    return bool(c and c["role"] == "super_admin" and c["mdp_hash"]
                and c["etat"] == "actif")


def acteur():
    """Auteur réel d'une action pour le journal d'audit : « mcp » pour le
    connecteur Claude, sinon l'e-mail du compte réel (l'impersonateur pendant
    un « voir en tant que »)."""
    if session.get("via_mcp"):
        return "mcp"
    real = get_compte(session.get("impersonator_id") or session.get("compte_id"))
    return real["email"] if real and real["email"] else "admin"


def base_admin_row():
    return db.q1("SELECT * FROM comptes WHERE role='super_admin' AND mdp_hash IS NOT NULL "
                 "ORDER BY id LIMIT 1")


def login_compte(compte):
    """Ouvre la session pour un compte actif et note la dernière connexion."""
    session.clear()
    session["compte_id"] = compte["id"]
    session["role"] = compte["role"]
    db.run("UPDATE comptes SET derniere_cnx = ? WHERE id = ?",
           (int(time.time()), compte["id"]))


def logout():
    session.clear()


# ── Login local (mot de passe) — compat avec l'existant ──────────────────────
# Anti-force brute : après chaque échec, plus aucun essai n'est examiné pendant
# 1, 2, 4… jusqu'à 30 s, quel que soit le nombre de connexions en parallèle
# (avant, un sleep(1) par requête : N connexions = N essais/s). Les essais
# refusés répondent tout de suite, sans immobiliser un thread du serveur.
_login_lock = threading.Lock()
_login_etat = {"echecs": 0, "bloque_jusqu": 0.0}

# Méthode de hachage fixée : le scrypt par défaut de Werkzeug 3 (Debian 13)
# est illisible par Werkzeug 2 (Debian 12) — base restaurée ailleurs = plus
# de connexion possible.
HASH_METHOD = "pbkdf2:sha256"


def _mdp_ok(mdp_hash, password):
    try:
        return bool(mdp_hash) and check_password_hash(mdp_hash, password)
    except (ValueError, TypeError) as exc:  # format de hash non pris en charge
        current_app.logger.warning("Mot de passe illisible par cette version : %s", exc)
        return False


def attente_login():
    """Secondes avant que le prochain mot de passe soit examiné (0 : tout de suite)."""
    return max(0, math.ceil(_login_etat["bloque_jusqu"] - time.time()))


def do_login(password):
    """Connexion locale du super-admin de base par mot de passe (anti-force brute)."""
    with _login_lock:
        if attente_login():
            return False  # pendant le délai, le mot de passe n'est même pas testé
        row = base_admin_row()
        if row and _mdp_ok(row["mdp_hash"], password):
            _login_etat.update(echecs=0, bloque_jusqu=0.0)
            login_compte(row)
            return True
        _login_etat["echecs"] += 1
        _login_etat["bloque_jusqu"] = time.time() + min(30, 2 ** min(_login_etat["echecs"] - 1, 5))
        db.audit("login_echec", acteur=request.headers.get("Cf-Connecting-IP")
                 or request.remote_addr)
        return False


def do_login_check(password):
    """Vérifie le mot de passe du super-admin de base sans ouvrir de session."""
    row = base_admin_row()
    return bool(row and _mdp_ok(row["mdp_hash"], password))


def set_password(password):
    """Change le mot de passe du super-admin de base."""
    if len(password) < 8:
        raise ValueError("Le mot de passe doit faire au moins 8 caractères.")
    row = base_admin_row()
    if not row:
        raise ValueError("Aucun compte administrateur de base.")
    db.run("UPDATE comptes SET mdp_hash = ? WHERE id = ?",
           (generate_password_hash(password, method=HASH_METHOD), row["id"]))


# ── Établissement de session via Cloudflare (before_request) ─────────────────
def cloudflare_sso():
    """Auto-connecte un compte actif reconnu par Cloudflare.

    - déjà connecté → rien ;
    - e-mail vérifié + compte `actif` → connexion ;
    - e-mail vérifié + inconnu + site « perso » → création auto en `actif` ;
    - autres cas (pending/refused/bloque, ou site géré) → laissés au *gateway*.
    """
    if session.get("compte_id"):
        return
    email = cf_access_email()
    if not email:
        return
    c = db.q1("SELECT * FROM comptes WHERE email = ?", (email,))
    if c is None and not access_managed():
        now = int(time.time())
        cid = db.run("INSERT INTO comptes (email, role, etat, cree, valide) "
                     "VALUES (?, 'membre', 'actif', ?, ?)", (email, now, now))
        db.ensure_system_lists(cid)
        db.audit("compte_auto_cree", acteur=email, cible=email)
        c = get_compte(cid)
    if c and c["etat"] == "actif":
        login_compte(c)


# ── Décorateurs ──────────────────────────────────────────────────────────────
def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        c = current_compte()
        if c is None or c["etat"] != "actif":
            if request.path.startswith("/api/"):
                return jsonify(error="Non authentifié"), 401
            return redirect(url_for("auth.gateway"))
        return view(*args, **kwargs)
    return wrapper


def super_admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if current_compte() is None:
            if request.path.startswith("/api/"):
                return jsonify(error="Non authentifié"), 401
            return redirect(url_for("auth.gateway"))
        if not is_super_admin():
            if request.path.startswith("/api/"):
                return jsonify(error="Réservé au super-admin"), 403
            return redirect(url_for("pages.index"))
        return view(*args, **kwargs)
    return wrapper
