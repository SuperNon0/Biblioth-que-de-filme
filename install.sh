#!/usr/bin/env bash
#
# ============================================================================
#  cinéthèque — installation idempotente (Ubuntu 22.04 / 24.04, LXC ou VM)
#
#  Usage :
#      git clone https://github.com/SuperNon0/Biblioth-que-de-filme.git /opt/cinetheque-src
#      sudo bash /opt/cinetheque-src/install.sh
#
#  Options :
#      --panel-port PORT       Port HTTP du site        (défaut : 8080)
#      --panel-password MDP    Mot de passe admin       (défaut : généré)
#      --tmdb-key CLE          Clé API TMDB             (défaut : vide, à mettre dans l'UI)
#      -h, --help              Affiche cette aide
#
#  Réexécutable sans écraser la config ni les données existantes.
# ============================================================================
set -euo pipefail

APP=cinetheque
APP_HOME=/opt/$APP
PANEL_DIR=$APP_HOME/panel
SCRIPTS_DIR=$APP_HOME/scripts
DATA_DIR=$APP_HOME/data
ETC_DIR=/etc/$APP
SRC_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

PANEL_PORT=8080
PANEL_PASSWORD=""
TMDB_KEY=""

log()  { echo -e "\033[1;36m[install]\033[0m $*"; }
fail() { echo -e "\033[1;31m[erreur]\033[0m $*" >&2; exit 1; }
usage() { sed -n '3,19p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,2\}//'; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --panel-port)     PANEL_PORT=$2; shift 2 ;;
        --panel-password) PANEL_PASSWORD=$2; shift 2 ;;
        --tmdb-key)       TMDB_KEY=$2; shift 2 ;;
        -h|--help)        usage; exit 0 ;;
        *)                fail "Option inconnue : $1 (voir --help)" ;;
    esac
done

[[ $EUID -eq 0 ]] || fail "Lance ce script en root (sudo)."

# --- 1. dépendances (apt : Python 3 + Flask + PyJWT/crypto) ------------------
# python3-jwt (PyJWT) + python3-cryptography : vérification du JWT Cloudflare
# Access (RS256). Installés via apt pour rester sans pip, conformément au socle.
log "Installation des dépendances (python3, flask, pyjwt, cryptography)…"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-flask python3-jwt python3-cryptography git >/dev/null

# --- 2. utilisateur dédié non-root ------------------------------------------
if ! id "$APP" &>/dev/null; then
    log "Création de l'utilisateur système « $APP »…"
    useradd --system --home "$APP_HOME" --shell /usr/sbin/nologin "$APP"
fi

# --- 3. arborescence + copie des fichiers -----------------------------------
log "Mise en place des fichiers dans $APP_HOME…"
mkdir -p "$PANEL_DIR" "$SCRIPTS_DIR" "$DATA_DIR" "$DATA_DIR/posters" "$ETC_DIR"
cp -a "$SRC_DIR/panel/." "$PANEL_DIR/"
cp -a "$SRC_DIR/scripts/." "$SCRIPTS_DIR/"
chmod +x "$SCRIPTS_DIR"/*.sh

# --- 4. config (générée une seule fois, préservée ensuite) ------------------
CONFIG="$ETC_DIR/config.json"
if [[ ! -f "$CONFIG" ]]; then
    log "Génération de la configuration initiale…"
    SECRET=$(python3 -c "import os; print(os.urandom(24).hex())")
    [[ -n "$PANEL_PASSWORD" ]] || PANEL_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(12))")
    HASH=$(python3 -c "from werkzeug.security import generate_password_hash as h; print(h('$PANEL_PASSWORD'))")
    cat > "$CONFIG" <<EOF
{
  "secret_key": "$SECRET",
  "panel_password_hash": "$HASH",
  "bind": "0.0.0.0",
  "panel_port": $PANEL_PORT,
  "data_dir": "$DATA_DIR",
  "db_file": "$DATA_DIR/library.db",
  "users_file": "$DATA_DIR/users.json",
  "posters_dir": "$DATA_DIR/posters",
  "source_dir": "$SRC_DIR",
  "panel_service_name": "$APP-panel",
  "tmdb_api_key": "$TMDB_KEY",
  "tmdb_language": "fr-FR",
  "tmdb_region": "FR",
  "cf_access_email": ""
}
EOF
    chmod 640 "$CONFIG"
    PASSWORD_TO_SHOW="$PANEL_PASSWORD"
else
    log "Configuration existante conservée ($CONFIG)."
    PASSWORD_TO_SHOW=""
fi

# --- 5. droits (le service tourne non-root et doit écrire ses données) -------
chown -R "$APP:$APP" "$APP_HOME"
chown root:"$APP" "$CONFIG"; chmod 640 "$CONFIG"
chown -R root:root "$SCRIPTS_DIR"; chmod +x "$SCRIPTS_DIR"/*.sh

# --- 6. service systemd -----------------------------------------------------
log "Installation du service systemd…"
sed "s/__PORT__/$PANEL_PORT/" "$SRC_DIR/systemd/$APP-panel.service" \
    > /etc/systemd/system/$APP-panel.service
systemctl daemon-reload
systemctl enable --now $APP-panel.service

# --- 7. sudoers minimal (mise à jour auto-remplaçante) ----------------------
cat > /etc/sudoers.d/$APP <<EOF
$APP ALL=(root) NOPASSWD: $SCRIPTS_DIR/update-panel.sh
EOF
chmod 440 /etc/sudoers.d/$APP

# --- fin --------------------------------------------------------------------
IP=$(hostname -I | awk '{print $1}')
log "✅ cinéthèque installé et démarré."
echo   "   → http://$IP:$PANEL_PORT"
[[ -n "$PASSWORD_TO_SHOW" ]] && echo "   → Mot de passe admin : $PASSWORD_TO_SHOW"
echo   "   → Pense à renseigner ta clé API TMDB dans Paramètres."
