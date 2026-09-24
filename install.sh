#!/bin/bash
#
# install.sh — first-time setup of a host for the whole stack (Debian/Ubuntu;
# production is the UpCloud VPS). Idempotent. Installs Docker, adds a swap file
# on small hosts, creates .env with generated secrets, installs rclone and
# schedules the nightly database backup. Starting the stack is ./upgrade.sh.
#
# Usage:  ./install.sh
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

info()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
err()   { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; }

if ! command -v apt-get >/dev/null 2>&1; then
    err "This installer targets Debian/Ubuntu (apt-get not found)."
    exit 1
fi
if [ "$(id -u)" -eq 0 ]; then SUDO=""; else SUDO="sudo"; fi

# ---------------------------------------------------------------------------
# 1. Docker (from Docker's repo; a no-op when already installed)
# ---------------------------------------------------------------------------
$SUDO apt-get update -qq
$SUDO apt-get install -y -qq ca-certificates curl git
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
# 2. Swap. The production VPS has 2 GB of RAM and no swap; Postgres, the API,
#    the bot, nginx and image builds fit, but a build spike should page, not
#    trigger the OOM killer.
# ---------------------------------------------------------------------------
if [ -z "$(swapon --noheadings --show 2>/dev/null)" ]; then
    info "Adding a 2 GB swap file at /swapfile..."
    $SUDO fallocate -l 2G /swapfile
    $SUDO chmod 600 /swapfile
    $SUDO mkswap /swapfile >/dev/null
    $SUDO swapon /swapfile
    grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' | $SUDO tee -a /etc/fstab >/dev/null
else
    info "Swap already configured."
fi

# ---------------------------------------------------------------------------
# 3. .env and secrets, 4. rclone + nightly backup
# ---------------------------------------------------------------------------
./ensure_env.sh
$SUDO ./backup.sh --install

# ---------------------------------------------------------------------------
# 5. OS hardening: sshd, fail2ban, automatic security reboots (harden_host.sh)
# ---------------------------------------------------------------------------
$SUDO ./harden_host.sh

echo
info "Installation complete."
echo "Next steps:"
echo "  1. Put the bot token in $REPO_DIR/.env (TELEGRAM_BOT_TOKEN=...), or let the"
echo "     deploy workflow write it from the repository secret."
echo "  2. For off-host backups: rclone config  (remote 'proton', type protondrive)"
echo "     (docs/DEPLOYMENT.md, Backups). Until then backups stay on this disk."
echo "  3. Allow TCP ${WEB_PORT:-80} inbound (UpCloud's network firewall is separate from ufw)."
[ "${NEEDS_RELOGIN:-0}" = "1" ] && echo "  4. Log out and back in (or 'newgrp docker') for the docker group."
echo "  Start or update:  ./upgrade.sh"
