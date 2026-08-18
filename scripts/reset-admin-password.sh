#!/usr/bin/env bash
# Réinitialise le mot de passe du super-admin de base de cinéthèque.
#
# À lancer SUR LE SERVEUR (console Proxmox ou SSH) quand le mot de passe est
# oublié. Écrit un nouveau hash dans la table `comptes` de la base SQLite
# (compte super-admin de base = celui avec un login local).
#
# Usage :
#   sudo bash reset-admin-password.sh                 # demande le mot de passe
#   sudo bash reset-admin-password.sh 'MonNouveauMDP' # mot de passe en argument
set -euo pipefail

CONFIG="${PANEL_CONFIG:-/etc/cinetheque/config.json}"

DB_FILE="$(python3 - "$CONFIG" <<'PY' 2>/dev/null || true
import json, os, sys
try:
    cfg = json.load(open(sys.argv[1]))
except OSError:
    cfg = {}
data = cfg.get("data_dir", "/opt/cinetheque/data")
print(cfg.get("db_file", os.path.join(data, "library.db")))
PY
)"
DB_FILE="${DB_FILE:-/opt/cinetheque/data/library.db}"

PASSWORD="${1:-}"
if [ -z "$PASSWORD" ]; then
    read -rsp "Nouveau mot de passe (8 caractères min.) : " PASSWORD; echo
fi
if [ "${#PASSWORD}" -lt 8 ]; then
    echo "Erreur : le mot de passe doit faire au moins 8 caractères." >&2; exit 1
fi

python3 - "$DB_FILE" "$PASSWORD" <<'PY'
import sqlite3, sys
from werkzeug.security import generate_password_hash
path, password = sys.argv[1], sys.argv[2]
h = generate_password_hash(password)
db = sqlite3.connect(path)
# Cible en priorité le super-admin « de base » (login local), sinon le 1er
# super-admin. À défaut d'aucun super-admin, on en crée un (compte racine).
row = db.execute(
    "SELECT id FROM comptes WHERE role='super_admin' AND mdp_hash IS NOT NULL "
    "ORDER BY id LIMIT 1").fetchone()
if row is None:
    row = db.execute("SELECT id FROM comptes WHERE role='super_admin' "
                     "ORDER BY id LIMIT 1").fetchone()
if row is None:
    import time
    now = int(time.time())
    db.execute("INSERT INTO comptes (role, etat, mdp_hash, cree, valide) "
               "VALUES ('super_admin','actif',?,?,?)", (h, now, now))
    print("Aucun super-admin : compte administrateur de base créé.")
else:
    db.execute("UPDATE comptes SET mdp_hash=? WHERE id=?", (h, row[0]))
    print("Mot de passe du super-admin de base réinitialisé (compte id %s)." % row[0])
db.commit(); db.close()
PY

echo "✅ Mot de passe réinitialisé. Reconnecte-toi en local."
