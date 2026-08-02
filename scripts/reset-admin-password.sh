#!/usr/bin/env bash
# Réinitialise le mot de passe du compte « admin » de cinéthèque.
#
# À lancer SUR LE SERVEUR (console Proxmox ou SSH) quand le mot de passe est
# oublié. Écrit un nouveau hash dans le fichier des comptes, puis aligne le
# propriétaire du fichier sur celui du dossier (l'utilisateur « cinetheque »).
#
# Usage :
#   sudo bash reset-admin-password.sh                 # demande le mot de passe
#   sudo bash reset-admin-password.sh 'MonNouveauMDP' # mot de passe en argument
set -euo pipefail

CONFIG="${PANEL_CONFIG:-/etc/cinetheque/config.json}"

USERS_FILE="$(python3 - "$CONFIG" <<'PY' 2>/dev/null || true
import json, os, sys
try:
    cfg = json.load(open(sys.argv[1]))
except OSError:
    cfg = {}
data = cfg.get("data_dir", "/opt/cinetheque/data")
print(cfg.get("users_file", os.path.join(data, "users.json")))
PY
)"
USERS_FILE="${USERS_FILE:-/opt/cinetheque/data/users.json}"

PASSWORD="${1:-}"
if [ -z "$PASSWORD" ]; then
    read -rsp "Nouveau mot de passe (8 caractères min.) : " PASSWORD; echo
fi
if [ "${#PASSWORD}" -lt 8 ]; then
    echo "Erreur : le mot de passe doit faire au moins 8 caractères." >&2; exit 1
fi

python3 - "$USERS_FILE" "$PASSWORD" <<'PY'
import json, sys
from werkzeug.security import generate_password_hash
path, password = sys.argv[1], sys.argv[2]
with open(path, "w", encoding="utf-8") as handle:
    json.dump({"admin": generate_password_hash(password)}, handle, indent=2)
print("Fichier des comptes réécrit :", path)
PY

# Le site tourne en tant que « cinetheque » : il doit pouvoir réécrire ce fichier.
chown --reference="$(dirname "$USERS_FILE")" "$USERS_FILE" 2>/dev/null || true
chmod 600 "$USERS_FILE" 2>/dev/null || true

echo "✅ Mot de passe du compte « admin » réinitialisé. Reconnecte-toi."
