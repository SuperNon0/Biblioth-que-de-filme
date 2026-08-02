#!/usr/bin/env bash
#
# ============================================================================
#  cinéthèque — déploiement Proxmox en UNE commande (conteneur LXC Ubuntu)
#
#  À COLLER DANS LE SHELL DE L'HÔTE PROXMOX :
#      bash -c "$(wget -qLO - https://raw.githubusercontent.com/SuperNon0/Biblioth-que-de-filme/main/proxmox/cinetheque-lxc.sh)"
#
#  Personnalisable (toutes les variables sont optionnelles) :
#      CTID=210 HOSTNAME=cinetheque CORES=2 MEMORY=2048 DISK=8 \
#      PANEL_PORT=8080 bash cinetheque-lxc.sh
#
#  Crée un conteneur LXC Ubuntu 24.04 non privilégié, y clone le dépôt et
#  lance install.sh — le site est déployé, configuré et démarré sans étape
#  manuelle.
# ============================================================================
set -euo pipefail

REPO="https://github.com/SuperNon0/Biblioth-que-de-filme.git"
BRANCH="${BRANCH:-main}"

CTID="${CTID:-$(pvesh get /cluster/nextid)}"
HOSTNAME="${HOSTNAME:-cinetheque}"
CORES="${CORES:-2}"
MEMORY="${MEMORY:-2048}"
SWAP="${SWAP:-512}"
DISK="${DISK:-8}"
STORAGE="${STORAGE:-local-lvm}"
BRIDGE="${BRIDGE:-vmbr0}"
PANEL_PORT="${PANEL_PORT:-8080}"
TEMPLATE_STORAGE="${TEMPLATE_STORAGE:-local}"

log() { echo -e "\033[1;36m[lxc]\033[0m $*"; }
fail() { echo -e "\033[1;31m[erreur]\033[0m $*" >&2; exit 1; }

command -v pct >/dev/null || fail "Ce script s'exécute sur un hôte Proxmox VE."

# --- template Ubuntu 24.04 (téléchargé si absent) ---------------------------
TEMPLATE=$(pveam available --section system 2>/dev/null \
    | awk '/ubuntu-24.04-standard/{print $2}' | sort | tail -1)
[[ -n "$TEMPLATE" ]] || fail "Template Ubuntu 24.04 introuvable (pveam update ?)."
if ! pveam list "$TEMPLATE_STORAGE" 2>/dev/null | grep -q "$TEMPLATE"; then
    log "Téléchargement du template $TEMPLATE…"
    pveam download "$TEMPLATE_STORAGE" "$TEMPLATE"
fi

# --- création du conteneur --------------------------------------------------
log "Création du conteneur LXC $CTID ($HOSTNAME)…"
pct create "$CTID" "$TEMPLATE_STORAGE:vztmpl/$TEMPLATE" \
    --hostname "$HOSTNAME" \
    --unprivileged 1 --features nesting=1 \
    --cores "$CORES" --memory "$MEMORY" --swap "$SWAP" \
    --rootfs "$STORAGE:$DISK" \
    --net0 "name=eth0,bridge=$BRIDGE,ip=dhcp" \
    --onboot 1

log "Démarrage du conteneur…"
pct start "$CTID"
sleep 6

# --- installation à l'intérieur ---------------------------------------------
log "Installation de cinéthèque dans le conteneur…"
pct exec "$CTID" -- bash -c "
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq && apt-get install -y -qq git >/dev/null
    git clone --branch '$BRANCH' '$REPO' /opt/cinetheque-src
    bash /opt/cinetheque-src/install.sh --panel-port '$PANEL_PORT'
"

IP=$(pct exec "$CTID" -- hostname -I | awk '{print $1}')
log "✅ cinéthèque déployé dans le conteneur $CTID."
echo   "   → http://$IP:$PANEL_PORT"
echo   "   → Mot de passe admin affiché ci-dessus (dans la sortie de l'install)."
