#!/bin/bash
#
# install.sh — first-time setup of a host for the whole stack (Debian/Ubuntu;
# docs/DEPLOYMENT.md). Idempotent. Installs Docker, adds a swap file
# on small hosts, creates .env with generated secrets, installs the host
# toolkit, rclone and the nightly database backup, and hardens the host.
# Starting the stack is ./upgrade.sh.
#
# Usage:  ./install.sh              everything
#         ./install.sh --toolkit    only (re)install the host toolkit: after
#                                   reviewing a change to it, or to
#                                   docker-compose.yml or docker/Caddyfile
#
# The host toolkit is the root-owned copy, in /usr/local/lib/diplomacy, of
# every script that runs as root here (upgrade.sh, ensure_env.sh, backup.sh and
# host/): the deploy key and the lead agent's key can only run its
# deploy_hook.sh and agent_shell.sh. It records the hashes of docker-compose.yml
# and docker/Caddyfile, and a deploy refuses a commit that changes them. So a
# commit on main changes the containers by itself, but the host only after
# the maintainer reviews it and runs this script.
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"
TOOLKIT=/usr/local/lib/diplomacy

mode=full
case "${1:-}" in
    "") ;;
    --toolkit) mode=toolkit ;;
    *)
        echo "install.sh: unknown argument: $1 (./install.sh or ./install.sh --toolkit)" >&2
        exit 2
        ;;
esac

info()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
err()   { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; }

if ! command -v apt-get >/dev/null 2>&1; then
    err "This installer targets Debian/Ubuntu (apt-get not found)."
    exit 1
fi
if [ "$(id -u)" -eq 0 ]; then SUDO=""; else SUDO="sudo"; fi

# ---------------------------------------------------------------------------
# The host toolkit (see the header). Shows what changed since the last install
# and, at a terminal, asks before replacing it.
# ---------------------------------------------------------------------------
install_toolkit() {
    local reviewed=(upgrade.sh ensure_env.sh backup.sh host/ docker-compose.yml docker/Caddyfile)
    local head prev
    head="$(git rev-parse HEAD)"
    prev="$(cat "$TOOLKIT/installed-from" 2>/dev/null || true)"
    if [ -n "$prev" ] && [ "$prev" != "$head" ]; then
        info "Host toolkit: changes since $prev (installed) to $head:"
        git --no-pager diff --stat "$prev" "$head" -- "${reviewed[@]}" || true
        echo "    Full diff: git diff $prev $head -- ${reviewed[*]}"
    fi
    if [ -t 0 ]; then
        read -r -p "Install the host toolkit from $head? [y/N] " answer
        case "$answer" in y | Y | yes) ;; *) err "Not installed."; exit 1 ;; esac
    fi
    $SUDO install -d -m 0755 -o root -g root "$TOOLKIT"
    $SUDO install -m 0755 -o root -g root upgrade.sh ensure_env.sh backup.sh \
        host/deploy_hook.sh host/agent_shell.sh "$TOOLKIT/"
    $SUDO install -m 0644 -o root -g root host/agent_db_role.sql "$TOOLKIT/"
    printf 'DIPLOMACY_DIR=%q\n' "$REPO_DIR" | $SUDO tee "$TOOLKIT/toolkit.env" >/dev/null
    sha256sum docker-compose.yml docker/Caddyfile | $SUDO tee "$TOOLKIT/reviewed.sha256" >/dev/null
    printf '%s\n' "$head" | $SUDO tee "$TOOLKIT/installed-from" >/dev/null
    info "Host toolkit installed in $TOOLKIT from $head."
}

if [ "$mode" = toolkit ]; then
    install_toolkit
    $SUDO "$TOOLKIT/backup.sh" --install
    $SUDO ./harden_host.sh
    if docker compose ps --status running --services 2>/dev/null | grep -qx postgres; then
        docker compose exec -T postgres psql -X -q -v ON_ERROR_STOP=1 -U diplomacy -d diplomacy_db \
            <host/agent_db_role.sql >/dev/null && info "Agent database role up to date."
    fi
    exit 0
fi

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
# 2. Swap. A 2 GB VPS with no swap: Postgres, the API,
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
# 3. .env and secrets, 4. the host toolkit, rclone + nightly backup
# ---------------------------------------------------------------------------
./ensure_env.sh
install_toolkit
$SUDO "$TOOLKIT/backup.sh" --install

# ---------------------------------------------------------------------------
# 5. OS hardening: sshd, the deploy and agent keys' forced commands, fail2ban,
#    automatic security reboots (harden_host.sh)
# ---------------------------------------------------------------------------
$SUDO ./harden_host.sh

echo
info "Installation complete."
echo "Next steps:"
echo "  1. Put the bot token in $REPO_DIR/.env (TELEGRAM_BOT_TOKEN=...), or let the"
echo "     deploy workflow write it from the repository secret."
echo "  2. For off-host backups: rclone config, then BACKUP_RCLONE_REMOTE in .env"
echo "     (docs/DEPLOYMENT.md, Backups). Until then backups stay on this disk."
echo "  3. Allow TCP ${WEB_PORT:-80} inbound (and in your provider's firewall, if it has one)."
[ "${NEEDS_RELOGIN:-0}" = "1" ] && echo "  4. Log out and back in (or 'newgrp docker') for the docker group."
echo "  Start or update:  ./upgrade.sh"
