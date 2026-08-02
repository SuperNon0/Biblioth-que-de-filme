#!/usr/bin/env bash
# Sauvegarde les données de cinéthèque (base SQLite, comptes, réglages, affiches)
# dans une archive horodatée. La rétention est réglable via KEEP (défaut 14).
set -euo pipefail

DATA_DIR="${DATA_DIR:-/opt/cinetheque/data}"
BACKUP_DIR="${BACKUP_DIR:-/opt/cinetheque/backups}"
KEEP="${KEEP:-14}"

mkdir -p "$BACKUP_DIR"
STAMP=$(date +%Y%m%d-%H%M%S)
ARCHIVE="$BACKUP_DIR/cinetheque-$STAMP.tar.gz"

tar -czf "$ARCHIVE" -C "$(dirname "$DATA_DIR")" "$(basename "$DATA_DIR")"
echo "[backup] Sauvegarde créée : $ARCHIVE"

# Rotation : ne conserve que les KEEP archives les plus récentes.
ls -1t "$BACKUP_DIR"/cinetheque-*.tar.gz 2>/dev/null | tail -n +"$((KEEP + 1))" \
    | xargs -r rm -f
echo "[backup] Rétention appliquée (max $KEEP archives)."
