#!/usr/bin/env bash
#
# Met à jour cinéthèque depuis GitHub : récupère la dernière version, recopie
# les fichiers du site et des scripts, puis redémarre le service.
#
# Lancé en root par le site (bouton « Mettre à jour ») via sudo, ou à la main :
#   sudo /opt/cinetheque/scripts/update-panel.sh
#
# Le corps est encapsulé dans main(). Comme la copie des fichiers plus bas
# réécrit CE script pendant qu'il tourne (mise à jour de lui-même), on se
# ré-exécute d'abord depuis une COPIE TEMPORAIRE stable : bash lit alors le
# script depuis /tmp (jamais modifié), ce qui évite l'erreur « unbound variable »
# lorsque le fichier d'origine change de taille en cours d'exécution.
set -euo pipefail

if [[ "${_CINE_REEXEC:-}" != "1" ]]; then
    _self="$(mktemp /tmp/cine-update.XXXXXX.sh)"
    cp "$0" "$_self"; chmod +x "$_self"
    _CINE_REEXEC=1 exec "$_self" "$@"
fi
trap 'rm -f "$0"' EXIT   # supprime la copie temporaire à la sortie

main() {
    local SOURCE_DIR="${SOURCE_DIR:-/opt/cinetheque-src}"
    local PANEL_DIR="${PANEL_DIR:-/opt/cinetheque/panel}"
    local SCRIPTS_DIR="${SCRIPTS_DIR:-/opt/cinetheque/scripts}"
    local PANEL_SERVICE="${PANEL_SERVICE:-cinetheque-panel}"
    # -c safe.directory : sans l'inscrire à chaque passage dans ~/.gitconfig
    # (l'ancien « --add » y ajoutait une ligne à chaque mise à jour).
    local GIT=(git -c "safe.directory=$SOURCE_DIR" -C "$SOURCE_DIR")

    [[ -d "$SOURCE_DIR/.git" ]] || {
        echo "[update] Dépôt source introuvable dans $SOURCE_DIR" >&2; exit 1; }

    echo "[update] Récupération des dernières modifications GitHub…"
    local AVANT
    AVANT=$("${GIT[@]}" rev-parse HEAD)
    "${GIT[@]}" pull --ff-only

    # Contrôle AVANT de toucher au site : un fichier Python invalide sur GitHub
    # ne remplace pas une version qui marche.
    if ! python3 - "$SOURCE_DIR/panel" <<'PY'
import pathlib, sys
erreurs = 0
for f in sorted(pathlib.Path(sys.argv[1]).rglob("*.py")):
    try:
        compile(f.read_bytes(), str(f), "exec")
    except (SyntaxError, ValueError) as exc:
        erreurs += 1
        print(f"[update] ✗ {f} : {exc}", file=sys.stderr)
sys.exit(1 if erreurs else 0)
PY
    then
        echo "[update] Nouvelle version invalide : mise à jour annulée, site inchangé." >&2
        "${GIT[@]}" reset -q --hard "$AVANT"
        exit 1
    fi

    # Dépendances (apt) : PyJWT + cryptography (JWT Cloudflare), waitress
    # (serveur web). Best-effort : sans waitress, le site garde le serveur de
    # Flask ; on ne bloque pas la mise à jour si apt échoue.
    local manquants=()
    python3 -c "import jwt" 2>/dev/null || manquants+=(python3-jwt python3-cryptography)
    python3 -c "import waitress" 2>/dev/null || manquants+=(python3-waitress)
    if (( ${#manquants[@]} )); then
        echo "[update] Installation des dépendances manquantes (${manquants[*]})…"
        { timeout 90 apt-get update -qq && DEBIAN_FRONTEND=noninteractive \
            timeout 90 apt-get install -y -qq "${manquants[@]}"; } >/dev/null 2>&1 || \
            echo "[update] ⚠ Installation apt impossible — installe ${manquants[*]} à la main." >&2
    fi

    echo "[update] Copie des fichiers…"
    # Version en place mise de côté : remise automatiquement si la nouvelle ne
    # démarre pas (voir restart-check.sh).
    rm -rf "$PANEL_DIR.prev"
    cp -a "$PANEL_DIR" "$PANEL_DIR.prev"
    cp -a "$SOURCE_DIR/panel/."   "$PANEL_DIR/"
    cp -a "$SOURCE_DIR/scripts/." "$SCRIPTS_DIR/"
    # Code et scripts à root, en lecture seule pour le service : le compte du
    # site ne doit pas pouvoir réécrire ce que sudo lui laisse lancer en root.
    chown root:root "$(dirname "$PANEL_DIR")"
    chmod 755 "$(dirname "$PANEL_DIR")"
    chown -R root:root "$PANEL_DIR" "$SCRIPTS_DIR"
    chmod -R go-w "$PANEL_DIR" "$SCRIPTS_DIR"
    chmod +x "$SCRIPTS_DIR"/*.sh
    python3 -m compileall -q "$PANEL_DIR" >/dev/null || true

    echo "[update] Redémarrage du site…"
    # Redémarrage détaché (sinon systemd tue ce script, enfant du service), puis
    # contrôle : si le site ne répond plus, retour à la version d'avant.
    if command -v systemd-run >/dev/null; then
        systemd-run --quiet --on-active=2 "$SCRIPTS_DIR/restart-check.sh" \
            "$PANEL_SERVICE" "$PANEL_DIR" "$SOURCE_DIR" "$AVANT"
    else
        systemctl restart "$PANEL_SERVICE.service"
    fi
    echo "[update] Mise à jour terminée."
}

main "$@"
