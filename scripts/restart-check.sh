#!/usr/bin/env bash
#
# Redémarre cinéthèque après une mise à jour et vérifie qu'il répond. Sinon,
# remet la version précédente (copie panel.prev + commit d'avant) et redémarre :
# une version cassée sur GitHub ne laisse plus le site hors ligne.
#
# Lancé par update-panel.sh via systemd-run, hors du service qui redémarre :
#   restart-check.sh <service> <dossier panel> <dépôt source> <commit d'avant>
# Compte rendu dans le journal : journalctl -t cinetheque-update
set -uo pipefail

SERVICE="${1:-cinetheque-panel}"
PANEL_DIR="${2:-/opt/cinetheque/panel}"
SOURCE_DIR="${3:-/opt/cinetheque-src}"
AVANT="${4:-}"
CONFIG="${PANEL_CONFIG:-/etc/cinetheque/config.json}"
DELAI="${DELAI:-90}"   # secondes laissées au site pour répondre

log() { echo "[update] $*"; logger -t cinetheque-update -- "$*" 2>/dev/null || true; }

# Adresse locale du site d'après la config (bind + port).
URL=$(python3 - "$CONFIG" <<'PY'
import json, sys
try:
    with open(sys.argv[1], encoding="utf-8") as handle:
        cfg = json.load(handle)
except (OSError, ValueError):
    cfg = {}
host = cfg.get("bind") or "127.0.0.1"
if host in ("0.0.0.0", "::"):
    host = "127.0.0.1"
if ":" in host:
    host = f"[{host}]"
print(f"http://{host}:{int(cfg.get('panel_port', 8080))}/sw.js")
PY
)

repond() {
    python3 - "$URL" <<'PY'
import sys, urllib.request
try:
    with urllib.request.urlopen(sys.argv[1], timeout=5) as resp:
        sys.exit(0 if resp.status == 200 else 1)
except Exception:
    sys.exit(1)
PY
}

attendre() {
    local fin=$((SECONDS + DELAI))
    while (( SECONDS < fin )); do
        sleep 3
        repond && return 0
    done
    return 1
}

systemctl restart "$SERVICE.service"
if attendre; then
    log "Mise à jour OK : le site répond."
    exit 0
fi

if [[ ! -d "$PANEL_DIR.prev" ]]; then
    log "⚠ Le site ne répond pas après la mise à jour (aucune version précédente à remettre)."
    exit 1
fi
log "⚠ Le site ne répond pas après la mise à jour : retour à la version précédente."
rm -rf "$PANEL_DIR.echec"
mv "$PANEL_DIR" "$PANEL_DIR.echec"
mv "$PANEL_DIR.prev" "$PANEL_DIR"
if [[ -n "$AVANT" ]]; then
    # Dépôt remis au même commit : la version affichée reste celle qui tourne.
    git -c "safe.directory=$SOURCE_DIR" -C "$SOURCE_DIR" reset -q --hard "$AVANT" || true
fi
systemctl reset-failed "$SERVICE.service" 2>/dev/null || true
systemctl restart "$SERVICE.service"
if attendre; then
    log "Version précédente rétablie, le site répond (version en échec : $PANEL_DIR.echec)."
else
    log "⚠ La version précédente ne répond pas non plus : voir journalctl -u $SERVICE."
fi
