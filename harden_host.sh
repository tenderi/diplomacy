#!/bin/bash
#
# harden_host.sh — operating-system hardening for the VPS. Idempotent; run as
# root (install.sh runs it). Prints what it changes, never a secret.
#
#   1. sshd: keys only, root by key only, no X11/agent forwarding, fewer
#      auth tries, idle sessions dropped. Validated with `sshd -t` before the
#      reload; an invalid config is removed again, so this cannot lock you out.
#   2. The GitHub Actions deploy key gets `restrict` (no forwarding, no pty):
#      it only ever pipes a script into `bash -s`.
#   3. fail2ban for sshd, on top of ufw's rate limit: the scanners that try a
#      few hundred logins a day are banned for an hour.
#   4. unattended-upgrades reboots at 04:30 UTC when an update needs it
#      (kernel, libc). Every container is `restart: always`; the nightly
#      backup runs at 03:17, before it.
#
# Not here, on purpose: ufw (already deny-by-default with 22 rate-limited;
# Docker-published ports bypass it, which is why only Caddy's 80/443 are
# published on a public address -- tests/test_deployment_infrastructure.py
# guards that), and WireGuard (wg0/33500 carries another project's traffic).
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

# --- 2. restrict the deploy key ----------------------------------------------------
KEYS=/root/.ssh/authorized_keys
if [ -f "$KEYS" ] && grep -qE '^ssh-[a-z0-9-]+ [^ ]+ github-actions-deploy$' "$KEYS"; then
    sed -i -E 's/^(ssh-[a-z0-9-]+ [^ ]+ github-actions-deploy)$/restrict \1/' "$KEYS"
    echo "==> Deploy key restricted (no forwarding, no pty)."
fi

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
