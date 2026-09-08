#!/bin/bash
#
# install_home.sh — install the GAME layer (Postgres + API) on the home server.
#
# Arch Linux, mirroring p2p's install.sh, and it assumes p2p's install.sh has
# already run on this host: that is what set up Docker, the WireGuard tunnel
# to the VPS (wg0, 10.8.0.2), the wg watchdog, and the docker.service drop-in
# that orders Docker after wg-quick@wg0. This script checks for those and
# tells you what is missing rather than duplicating them.
#
# The Telegram bot and the web frontend do NOT run here; see install_vps.sh.
#
# Usage:  ./install_home.sh        (idempotent)
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

info()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33mWARN:\033[0m %s\n' "$*"; }
err()   { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; }

if ! command -v pacman >/dev/null 2>&1; then
    err "This installer targets Arch Linux (pacman not found)."
    exit 1
fi
if [ "$(id -u)" -eq 0 ]; then
    err "Do not run this as root; it uses sudo only where needed."
    exit 1
fi

# ---------------------------------------------------------------------------
# 1. System packages
# ---------------------------------------------------------------------------
PACKAGES=(docker docker-compose docker-buildx git wireguard-tools)
MISSING=()
for pkg in "${PACKAGES[@]}"; do
    pacman -Qi "$pkg" >/dev/null 2>&1 || MISSING+=("$pkg")
done
if [ "${#MISSING[@]}" -gt 0 ]; then
    info "Installing packages: ${MISSING[*]}"
    sudo pacman -S --needed --noconfirm "${MISSING[@]}"
else
    info "All system packages already installed."
fi

sudo systemctl enable --now docker.service
if ! id -nG "$USER" | tr ' ' '\n' | grep -qx docker; then
    info "Adding '$USER' to the 'docker' group."
    sudo usermod -aG docker "$USER"
    NEEDS_RELOGIN=1
fi

# ---------------------------------------------------------------------------
# 2. Environment file + secrets
# ---------------------------------------------------------------------------
ENV_FILE="$REPO_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    info "Creating .env from .env.example"
    cp "$REPO_DIR/.env.example" "$ENV_FILE"
    chmod 600 "$ENV_FILE"
else
    info ".env already exists, leaving values untouched."
fi

# Fill any blank secret with a fresh random value. Never overwrites a set one.
ensure_secret() {
    local key="$1"
    if ! grep -q "^${key}=.\+" "$ENV_FILE" 2>/dev/null; then
        local value
        value="$(openssl rand -hex 32)"
        if grep -q "^${key}=" "$ENV_FILE"; then
            sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
        else
            echo "${key}=${value}" >> "$ENV_FILE"
        fi
        info "Generated ${key}."
        GENERATED+=("$key")
    fi
}
GENERATED=()
ensure_secret POSTGRES_PASSWORD
ensure_secret DIPLOMACY_JWT_SECRET
ensure_secret DIPLOMACY_ADMIN_TOKEN
ensure_secret DIPLOMACY_BOT_SECRET

# ---------------------------------------------------------------------------
# 3. The control tunnel (owned by p2p; verified, not installed, here)
# ---------------------------------------------------------------------------
WG_IP="$(grep -E '^WG_IP=' "$ENV_FILE" | cut -d= -f2- || true)"
WG_IP="${WG_IP:-10.8.0.2}"
if ip -4 addr show wg0 2>/dev/null | grep -q "inet ${WG_IP}/"; then
    info "wg0 is up with ${WG_IP}."
else
    warn "wg0 is not up with ${WG_IP}. The API binds to that address and will"
    warn "restart-loop until it exists. Bring up the p2p control tunnel first:"
    warn "    sudo systemctl enable --now wg-quick@wg0     (see ~/p2p/wireguard/)"
fi
if [ -f /etc/systemd/system/docker.service.d/wireguard.conf ]; then
    info "docker.service is ordered after wg-quick@wg0 (p2p drop-in present)."
else
    warn "Missing /etc/systemd/system/docker.service.d/wireguard.conf."
    warn "Without it a reboot can start Docker before wg0 exists and the API"
    warn "fails to bind. Run ~/p2p/install.sh, or copy the drop-in from"
    warn "~/p2p/systemd/docker-wg-dropin/wireguard.conf and 'systemctl daemon-reload'."
fi

# ---------------------------------------------------------------------------
# 4. Validate the compose file
# ---------------------------------------------------------------------------
info "Validating docker-compose.yml..."
if sg docker -c "cd '$REPO_DIR' && docker compose config -q" 2>/dev/null; then
    info "docker-compose.yml is valid."
else
    warn "Could not validate the compose file yet (Docker may need a relogin first)."
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo
info "Installation complete."
if [ "${#GENERATED[@]}" -gt 0 ]; then
    echo "Copy DIPLOMACY_BOT_SECRET into the VPS .env -- the two must match exactly:"
    echo "    $(grep -E '^DIPLOMACY_BOT_SECRET=' "$ENV_FILE")"
fi
echo "Next steps:"
echo "  1. Edit $ENV_FILE: DIPLOMACY_PASSWORD_RESET_BASE_URL / DIPLOMACY_CORS_ORIGINS"
echo "     with the VPS address (or hostname) the web client is served from."
if [ "${NEEDS_RELOGIN:-0}" = "1" ]; then
    echo "  2. Log out and back in (or 'newgrp docker')."
    echo "  3. Start:   docker compose up -d      (first build takes a few minutes)"
else
    echo "  2. Start:   docker compose up -d      (first build takes a few minutes)"
fi
echo "  Then verify: curl -sS http://127.0.0.1:8000/healthz   and from the VPS:"
echo "               curl -sS http://${WG_IP}:8000/healthz"
