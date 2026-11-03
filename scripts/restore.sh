#!/usr/bin/env bash
# Restaure une sauvegarde de cinéthèque créée par backup.sh.
#
# Usage : sudo bash restore.sh cinetheque-AAAAMMJJ-HHMMSS.tar.gz
set -euo pipefail

DATA_DIR="${DATA_DIR:-/opt/cinetheque/data}"
BACKUP_DIR="${BACKUP_DIR:-/opt/cinetheque/backups}"
SERVICE="${PANEL_SERVICE:-cinetheque-panel}"

[[ $EUID -eq 0 ]] || { echo "Lance ce script en root (sudo)." >&2; exit 1; }

NAME="${1:-}"
[[ -n "$NAME" ]] || { echo "Usage : restore.sh <archive.tar.gz>" >&2; exit 1; }
ARCHIVE="$BACKUP_DIR/$NAME"
[[ -f "$ARCHIVE" ]] || { echo "Archive introuvable : $ARCHIVE" >&2; exit 1; }

# Extraction d'abord dans un dossier temporaire : si l'archive est corrompue,
# les données actuelles ne sont pas touchées.
PARENT="$(dirname "$DATA_DIR")"
TMP=$(mktemp -d "$PARENT/.restore-XXXXXX")
trap 'rm -rf "$TMP"' EXIT
echo "[restore] Vérification de l'archive…"
tar -xzf "$ARCHIVE" -C "$TMP"
[[ -d "$TMP/$(basename "$DATA_DIR")" ]] || { echo "Archive invalide." >&2; exit 1; }

echo "[restore] Arrêt du service…"
systemctl stop "$SERVICE.service" 2>/dev/null || true

echo "[restore] Restauration des données…"
OLD="$DATA_DIR.avant-restauration"
rm -rf "$OLD"
[[ -e "$DATA_DIR" ]] && mv "$DATA_DIR" "$OLD"
mv "$TMP/$(basename "$DATA_DIR")" "$DATA_DIR"
chown -R cinetheque:cinetheque "$DATA_DIR" 2>/dev/null || true
echo "[restore] Anciennes données conservées dans $OLD (à supprimer si tout va bien)."

echo "[restore] Redémarrage du service…"
systemctl start "$SERVICE.service" 2>/dev/null || true
echo "[restore] ✅ Restauration terminée."
