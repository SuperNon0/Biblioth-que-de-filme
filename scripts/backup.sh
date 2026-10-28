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

# Les bases SQLite (mode WAL) sont copiées via l'API de sauvegarde de SQLite :
# une copie brute du fichier pendant que le service tourne peut être incohérente.
# Le reste (affiches, réglages) est repris en liens durs (copie si impossible).
BASE="$(basename "$DATA_DIR")"
STAGE=$(mktemp -d "$BACKUP_DIR/.stage-XXXXXX")
trap 'rm -rf "$STAGE"' EXIT
cp -al "$DATA_DIR" "$STAGE/$BASE" 2>/dev/null || { rm -rf "${STAGE:?}/$BASE"; cp -a "$DATA_DIR" "$STAGE/$BASE"; }
rm -f "$STAGE/$BASE"/*.db "$STAGE/$BASE"/*.db-wal "$STAGE/$BASE"/*.db-shm
python3 - "$DATA_DIR" "$STAGE/$BASE" <<'PY'
import pathlib, sqlite3, sys
src, dst = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
for db in src.glob("*.db"):
    with sqlite3.connect(db) as s, sqlite3.connect(dst / db.name) as d:
        s.backup(d)
PY
tar -czf "$ARCHIVE" -C "$STAGE" "$BASE"
echo "[backup] Sauvegarde créée : $ARCHIVE"

# Rotation : ne conserve que les KEEP archives les plus récentes.
ls -1t "$BACKUP_DIR"/cinetheque-*.tar.gz 2>/dev/null | tail -n +"$((KEEP + 1))" \
    | xargs -r rm -f
echo "[backup] Rétention appliquée (max $KEEP archives)."
