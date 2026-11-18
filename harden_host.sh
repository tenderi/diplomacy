#!/bin/bash
#
# harden_host.sh — operating-system hardening for the VPS. Idempotent; run as
# root (install.sh runs it). Prints what it changes, never a secret.
#
#   1. sshd: keys only, root by key only, no X11/agent forwarding, fewer
#      auth tries, idle sessions dropped. Validated with `sshd -t` before the
#      reload; an invalid config is removed again, so this cannot lock you out.
#   2. The two keys GitHub Actions holds get `restrict` (no forwarding, no
#      pty) and a forced command, so neither can open a shell: the deploy key
#      (comment github-actions-deploy) runs only the host toolkit's
#      deploy_hook.sh, the lead agent's (diplomacy-lead-agent) only its
#      read-only agent_shell.sh. Run after install.sh has installed the toolkit.
#   3. fail2ban for sshd, on top of ufw's rate limit: the scanners that try a
#      few hundred logins a day are banned for an hour.
#   4. unattended-upgrades reboots at 04:30 UTC when an update needs it
#      (kernel, libc). Every container is `restart: always`; the nightly
#      backup runs at 03:17, before it.
#
# Not here, on purpose: ufw (already deny-by-default with 22 rate-limited;
# Docker-published ports bypass it, which is why only Caddy's 80/443 are
# published on a public address -- tests/test_deployment_infrastructure.py
# guards that; a shared host's other rules stay untouched).
#
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root." >&2
    exit 1
fi

# --- 1. sshd ------------------------------------------------------------------
# sshd takes the FIRST value it reads for each keyword, and sshd_config
# includes sshd_config.d/*.conf at its top in name order, so a 10- file wins
# over cloud-init's 50- one and the distribution defaults.
SSHD_DROPIN=/etc/ssh/sshd_config.d/10-diplomacy-hardening.conf
SSHD_WANT='# Managed by diplomacy/harden_host.sh
PermitRootLogin prohibit-password
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitEmptyPasswords no
PubkeyAuthentication yes
X11Forwarding no
AllowAgentForwarding no
MaxAuthTries 3
LoginGraceTime 30
ClientAliveInterval 300
ClientAliveCountMax 2'
if [ "$(cat "$SSHD_DROPIN" 2>/dev/null || true)" != "$SSHD_WANT" ]; then
    printf '%s\n' "$SSHD_WANT" > "$SSHD_DROPIN"
    chmod 644 "$SSHD_DROPIN"
    if sshd -t; then
        systemctl reload ssh 2>/dev/null || systemctl reload sshd
        echo "==> sshd hardened ($SSHD_DROPIN)."
    else
        rm -f "$SSHD_DROPIN"
        echo "==> ERROR: the sshd drop-in did not validate; removed it, sshd unchanged." >&2
        exit 1
    fi
fi

# --- 2. forced commands for the keys GitHub Actions holds ------------------------
# The key itself is added by hand (docs/DEPLOYMENT.md); this pins what it may do.
KEYS=/root/.ssh/authorized_keys
TOOLKIT=/usr/local/lib/diplomacy
force_command() {  # force_command <key comment> <command>
    local comment="$1" want="restrict,command=\"$2\""
    [ -f "$KEYS" ] || return 0
    awk -v c="$comment" -v w="$want" \
        '$NF == c && NF >= 3 {print w, $(NF-2), $(NF-1), $NF; next} {print}' "$KEYS" >"$KEYS.tmp"
    if cmp -s "$KEYS" "$KEYS.tmp"; then
        rm -f "$KEYS.tmp"
    else
        cat "$KEYS.tmp" >"$KEYS" # keeps the file's owner and mode
        rm -f "$KEYS.tmp"
        echo "==> $comment key: restricted to $2."
    fi
}
force_command github-actions-deploy "$TOOLKIT/deploy_hook.sh"
force_command diplomacy-lead-agent "$TOOLKIT/agent_shell.sh"

# --- 3. fail2ban ----------------------------------------------------------------------
if ! command -v fail2ban-client >/dev/null 2>&1; then
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq fail2ban >/dev/null
    echo "==> Installed fail2ban."
fi
F2B_JAIL=/etc/fail2ban/jail.d/diplomacy-sshd.local
F2B_WANT='# Managed by diplomacy/harden_host.sh
[sshd]
enabled = true
backend = systemd
maxretry = 5
findtime = 10m
bantime = 1h'
if [ "$(cat "$F2B_JAIL" 2>/dev/null || true)" != "$F2B_WANT" ]; then
    printf '%s\n' "$F2B_WANT" > "$F2B_JAIL"
    systemctl enable --now fail2ban >/dev/null 2>&1 || true
    systemctl restart fail2ban
    echo "==> fail2ban sshd jail on."
fi

# --- 4. automatic security reboots ----------------------------------------------------
UU=/etc/apt/apt.conf.d/52diplomacy-unattended
UU_WANT='// Managed by diplomacy/harden_host.sh
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "04:30";
Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";'
if [ "$(cat "$UU" 2>/dev/null || true)" != "$UU_WANT" ]; then
    printf '%s\n' "$UU_WANT" > "$UU"
    echo "==> unattended-upgrades reboots at 04:30 UTC when an update needs it."
fi
