#!/usr/bin/env bash
# Restaure une sauvegarde de cinéthèque créée par backup.sh.
#
# Usage : sudo bash restore.sh cinetheque-AAAAMMJJ-HHMMSS.tar.gz
set -euo pipefail

DATA_DIR="${DATA_DIR:-/opt/cinetheque/data}"
BACKUP_DIR="${BACKUP_DIR:-/opt/cinetheque/backups}"
SERVICE="${PANEL_SERVICE:-cinetheque-panel}"

NAME="${1:-}"
[[ -n "$NAME" ]] || { echo "Usage : restore.sh <archive.tar.gz>" >&2; exit 1; }
ARCHIVE="$BACKUP_DIR/$NAME"
[[ -f "$ARCHIVE" ]] || { echo "Archive introuvable : $ARCHIVE" >&2; exit 1; }

echo "[restore] Arrêt du service…"
systemctl stop "$SERVICE.service" 2>/dev/null || true

echo "[restore] Restauration des données…"
rm -rf "$DATA_DIR"
tar -xzf "$ARCHIVE" -C "$(dirname "$DATA_DIR")"
chown -R cinetheque:cinetheque "$DATA_DIR" 2>/dev/null || true

echo "[restore] Redémarrage du service…"
systemctl start "$SERVICE.service" 2>/dev/null || true
echo "[restore] ✅ Restauration terminée."
