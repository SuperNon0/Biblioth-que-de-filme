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

    [[ -d "$SOURCE_DIR/.git" ]] || {
        echo "[update] Dépôt source introuvable dans $SOURCE_DIR" >&2; exit 1; }

    echo "[update] Récupération des dernières modifications GitHub…"
    git config --global --add safe.directory "$SOURCE_DIR" 2>/dev/null || true
    git -C "$SOURCE_DIR" pull --ff-only

    # Dépendances (apt) : PyJWT + cryptography pour la vérif JWT Cloudflare.
    # Best-effort et idempotent : on ne bloque pas la mise à jour si apt échoue.
    if ! python3 -c "import jwt" 2>/dev/null; then
        echo "[update] Installation des dépendances manquantes (python3-jwt, cryptography)…"
        DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
            python3-jwt python3-cryptography >/dev/null 2>&1 || \
            echo "[update] ⚠ Installation apt impossible — installe python3-jwt manuellement." >&2
    fi

    echo "[update] Copie des fichiers…"
    cp -a "$SOURCE_DIR/panel/."   "$PANEL_DIR/"
    cp -a "$SOURCE_DIR/scripts/." "$SCRIPTS_DIR/"
    chown -R cinetheque:cinetheque "$PANEL_DIR"
    chown -R root:root "$SCRIPTS_DIR"
    chmod +x "$SCRIPTS_DIR"/*.sh

    echo "[update] Redémarrage du site…"
    # Redémarrage détaché : sinon systemd tue ce script (enfant du service).
    if command -v systemd-run >/dev/null; then
        systemd-run --quiet --on-active=2 systemctl restart "$PANEL_SERVICE.service"
    else
        systemctl restart "$PANEL_SERVICE.service"
    fi
    echo "[update] Mise à jour terminée."
}

main "$@"
