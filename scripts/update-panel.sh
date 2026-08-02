#!/usr/bin/env bash
#
# Met à jour cinéthèque depuis GitHub : récupère la dernière version, recopie
# les fichiers du site et des scripts, puis redémarre le service.
#
# Lancé en root par le site (bouton « Mettre à jour ») via sudo, ou à la main :
#   sudo /opt/cinetheque/scripts/update-panel.sh
#
# Le corps est encapsulé dans main() : bash parse toute la fonction en mémoire
# avant exécution, ce qui permet au script de se remplacer lui-même sans
# corruption pendant la copie.
set -euo pipefail

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
