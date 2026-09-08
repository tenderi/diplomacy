#!/bin/bash
#
# install_vps.sh — install the CONTROL layer (Telegram bot + web frontend) on
# the VPS. Debian/Ubuntu. This is the same VPS that runs the p2p control layer,
# and it reuses that stack's WireGuard tunnel: p2p's install_vps.sh already
# installed Docker and set up wg0 (10.8.0.1 here, 10.8.0.2 at home). This
# script only verifies those and adds what diplomacy needs.
#
# Usage:  ./install_vps.sh        (idempotent)
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

info()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33mWARN:\033[0m %s\n' "$*"; }
err()   { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; }

if ! command -v apt-get >/dev/null 2>&1; then
    err "This installer targets Debian/Ubuntu (apt-get not found)."
    exit 1
fi
if [ "$(id -u)" -eq 0 ]; then SUDO=""; else SUDO="sudo"; fi

# ---------------------------------------------------------------------------
# 1. Docker (from Docker's repo, as p2p does; a no-op if p2p already did it)
# ---------------------------------------------------------------------------
$SUDO apt-get update -qq
$SUDO apt-get install -y -qq ca-certificates curl git wireguard
if ! command -v docker >/dev/null 2>&1; then
    info "Installing Docker..."
    $SUDO install -m 0755 -d /etc/apt/keyrings
    . /etc/os-release
    $SUDO curl -fsSL "https://download.docker.com/linux/${ID}/gpg" -o /etc/apt/keyrings/docker.asc
    $SUDO chmod a+r /etc/apt/keyrings/docker.asc
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] " \
         "https://download.docker.com/linux/${ID} ${VERSION_CODENAME} stable" \
        | $SUDO tee /etc/apt/sources.list.d/docker.list >/dev/null
    $SUDO apt-get update -qq
    $SUDO apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
else
    info "Docker already installed."
fi
$SUDO systemctl enable --now docker.service
if [ "$(id -u)" -ne 0 ] && ! id -nG "$USER" | tr ' ' '\n' | grep -qx docker; then
    $SUDO usermod -aG docker "$USER"
    NEEDS_RELOGIN=1
fi

# ---------------------------------------------------------------------------
# 2. Environment file
# ---------------------------------------------------------------------------
if [ ! -f "$REPO_DIR/.env" ]; then
    info "Creating .env from .env.control.example — fill in TELEGRAM_BOT_TOKEN and DIPLOMACY_BOT_SECRET."
    cp "$REPO_DIR/.env.control.example" "$REPO_DIR/.env"
    chmod 600 "$REPO_DIR/.env"
else
    info ".env already exists, leaving it untouched."
fi

# ---------------------------------------------------------------------------
# 3. The tunnel (owned by p2p)
# ---------------------------------------------------------------------------
if $SUDO wg show wg0 >/dev/null 2>&1; then
    info "wg0 is up."
    if ping -c1 -W3 10.8.0.2 >/dev/null 2>&1; then
        info "Home server answers on 10.8.0.2."
    else
        warn "wg0 exists but 10.8.0.2 does not answer. Check the home side: systemctl status wg-quick@wg0."
    fi
else
    warn "wg0 is not up. This stack reuses the p2p control tunnel; set it up with"
    warn "~/p2p/install_vps.sh and ~/p2p/wireguard/ first."
fi

# ---------------------------------------------------------------------------
# 4. Validate the compose file
# ---------------------------------------------------------------------------
info "Validating docker-compose.control.yml..."
if docker compose -f "$REPO_DIR/docker-compose.control.yml" config -q 2>/dev/null; then
    info "docker-compose.control.yml is valid."
else
    warn "Could not validate the compose file yet (Docker may need a relogin, or .env is incomplete)."
fi

echo
info "Installation complete."
echo "Next steps:"
echo "  1. Edit $REPO_DIR/.env: TELEGRAM_BOT_TOKEN (from @BotFather) and the"
echo "     DIPLOMACY_BOT_SECRET printed by install_home.sh on the home server."
echo "  2. Make sure TCP ${WEB_PORT:-80} is allowed inbound (UpCloud's network firewall"
echo "     is separate from ufw; the WireGuard notes in ~/p2p/README.md apply)."
if [ "${NEEDS_RELOGIN:-0}" = "1" ]; then
    echo "  3. Log out and back in (or 'newgrp docker')."
    echo "  4. Start:  docker compose -f docker-compose.control.yml up -d"
else
    echo "  3. Start:  docker compose -f docker-compose.control.yml up -d"
fi
echo "  Verify:  curl -sS http://10.8.0.2:8000/healthz      (the API, over the tunnel)"
echo "           curl -sS http://127.0.0.1:${WEB_PORT:-80}/healthz   (nginx)"
